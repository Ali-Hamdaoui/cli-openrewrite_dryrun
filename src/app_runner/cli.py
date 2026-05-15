from __future__ import annotations

import argparse
from pathlib import Path
import shlex
import sys
from datetime import datetime, timezone

from .classifier import Classification, ResultKind
from .detection import BuildTool, ProjectDetectionError, ProjectInfo, detect_project
from .rewrite import RewriteError, build_rewrite_command, prepare_rewrite_plugin
from .runner import RunResult, run_until_result


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        project = detect_project(args.project_path)
    except ProjectDetectionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    command = _build_command(project.command, project.build_tool, args.module, args.main_class)
    if args.rewrite_plugin_txt:
        return _run_rewrite_mode(project, args)

    print(f"Project: {project.path}")
    print(f"Build tool: {project.build_tool.value} ({'wrapper' if project.uses_wrapper else 'system command'})")
    print(f"Command: {_format_command(command)}")
    print(f"Startup timeout: {args.timeout} seconds")
    print()

    result = run_until_result(
        command=command,
        cwd=project.path,
        timeout_seconds=args.timeout,
        stream_output=not args.quiet,
        stop_after_start=args.stop_after_start,
        on_startup_result=None if args.stop_after_start else _print_startup_success,
    )

    _print_final_result(result)
    return 0 if result.succeeded else 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="app-runner",
        description="Run a Spring Boot project by detecting Maven or Gradle and watching startup logs.",
    )
    parser.add_argument("project_path", help="Path to a Java/Spring Boot project")
    parser.add_argument(
        "--timeout",
        type=_positive_int,
        default=120,
        help="Seconds to wait for startup success or failure detection before timing out. Default: 120",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Do not stream application logs; only print app-runner status lines.",
    )
    parser.add_argument(
        "--stop-after-start",
        action="store_true",
        help="Stop the application and exit after startup is detected.",
    )
    parser.add_argument(
        "--module",
        help="Maven module to target in a multi-module project (passed as -f <module>/pom.xml).",
    )
    parser.add_argument(
        "--main-class",
        help="Override Spring Boot main class. For Maven this maps to -Dspring-boot.run.mainClass=...",
    )
    parser.add_argument(
        "--rewrite-plugin-txt",
        help="Path to a .txt file containing the OpenRewrite Maven <plugin> XML to inject into pom.xml.",
    )
    parser.add_argument(
        "--no-pom-backup",
        action="store_true",
        help="Do not create pom.xml.bak before injecting the rewrite plugin.",
    )
    return parser


def _positive_int(raw: str) -> int:
    value = int(raw)
    if value <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return value


def _print_startup_success(classification: Classification) -> None:
    print()
    print("SUCCESS: Application started successfully")
    if classification.line:
        print(f"Matched log: {classification.line}")
    print()


def _print_final_result(result: RunResult) -> None:
    classification = result.classification

    if classification.kind == ResultKind.SUCCESS:
        if result.exit_code == 0:
            print("SUCCESS: Application started and exited cleanly")
        else:
            print("SUCCESS: Application started successfully")
        if classification.line:
            print(f"Matched log: {classification.line}")
        return

    print()
    print(f"FAILURE: {classification.message}")
    print(f"Reason: {classification.kind.value}")
    if classification.line:
        print(f"Matched log: {classification.line}")
    elif main_error := _last_non_empty_line(result):
        print(f"Last log: {main_error}")
    if result.exit_code is not None:
        print(f"Exit code: {result.exit_code}")


def _format_command(command: list[str]) -> str:
    return shlex.join(command)


def _build_command(
    base_command: list[str],
    build_tool: BuildTool,
    module: str | None,
    main_class: str | None,
) -> list[str]:
    command = list(base_command)

    if build_tool == BuildTool.MAVEN:
        executable = command[0]
        goal = command[1] if len(command) > 1 else "spring-boot:run"
        maven_args: list[str] = []
        if module:
            module_pom = Path(module) / "pom.xml"
            maven_args.extend(["-f", str(module_pom)])
        if main_class:
            maven_args.append(f"-Dspring-boot.run.mainClass={main_class}")
        return [executable, *maven_args, goal]

    return command


def _last_non_empty_line(result: RunResult) -> str | None:
    for line in reversed([*result.stderr, *result.stdout]):
        if line.strip():
            return line
    return None


def _run_rewrite_mode(project: ProjectInfo, args: argparse.Namespace) -> int:
    if project.build_tool != BuildTool.MAVEN:
        print("ERROR: rewrite mode currently supports Maven projects only", file=sys.stderr)
        return 2

    plugin_txt_path = Path(args.rewrite_plugin_txt).expanduser().resolve()
    try:
        prep = prepare_rewrite_plugin(
            project_path=project.path,
            plugin_txt_path=plugin_txt_path,
            module=args.module,
            backup=not args.no_pom_backup,
        )
    except RewriteError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    command = build_rewrite_command(project.command[0], args.module)
    print(f"Project: {project.path}")
    print(f"Target pom.xml: {prep.pom_path}")
    print(f"Injected plugin: {prep.plugin_coordinates[0]}:{prep.plugin_coordinates[1]}")
    print(f"Command: {_format_command(command)}")
    print(f"Timeout: {args.timeout} seconds")
    print()

    result = run_until_result(
        command=command,
        cwd=project.path,
        timeout_seconds=args.timeout,
        stream_output=not args.quiet,
        stop_after_start=True,
        on_startup_result=None,
    )
    warnings = _extract_migration_warnings(result)
    report_path = _write_migration_units_file(warnings)
    print(f"Migration warnings file: {report_path}")
    return _print_rewrite_result(result)


def _print_rewrite_result(result: RunResult) -> int:
    if result.exit_code == 0:
        print("SUCCESS: rewrite:dryRun completed")
        return 0

    print("FAILURE: rewrite:dryRun failed")
    if main_error := _last_non_empty_line(result):
        print(f"Last log: {main_error}")
    if result.exit_code is not None:
        print(f"Exit code: {result.exit_code}")
    return 1


def _extract_migration_warnings(result: RunResult) -> list[str]:
    warnings: list[str] = []
    lines = [*result.stdout, *result.stderr]
    capture_context = False

    for raw in lines:
        line = raw.rstrip()
        stripped = line.strip()
        lower = stripped.lower()

        is_warning_line = "[warning]" in lower or lower.startswith("warn")
        is_rewrite_change_line = stripped.startswith("~>") or "would make changes to" in lower
        is_indented_context = capture_context and (raw.startswith(" ") or raw.startswith("\t"))

        if is_warning_line or is_rewrite_change_line:
            warnings.append(stripped if stripped else line)
            capture_context = True
            continue

        if is_indented_context:
            warnings.append(stripped if stripped else line)
            continue

        capture_context = False

    return warnings


def _write_migration_units_file(warnings: list[str]) -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    output_path = repo_root / "migration units.txt"
    timestamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    lines: list[str] = [f"# OpenRewrite dryRun migration warnings ({timestamp})"]
    if warnings:
        lines.extend(warnings)
    else:
        lines.append("No warning lines found in rewrite:dryRun output.")
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path
