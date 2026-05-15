from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import shutil


class BuildTool(str, Enum):
    MAVEN = "maven"
    GRADLE = "gradle"


@dataclass(frozen=True)
class ProjectInfo:
    path: Path
    build_tool: BuildTool
    command: list[str]
    uses_wrapper: bool


class ProjectDetectionError(Exception):
    pass


def detect_project(project_path: str | Path) -> ProjectInfo:
    path = Path(project_path).expanduser().resolve()

    if not path.exists():
        raise ProjectDetectionError(f"Project path does not exist: {path}")
    if not path.is_dir():
        raise ProjectDetectionError(f"Project path is not a directory: {path}")

    has_maven = (path / "pom.xml").is_file()
    has_gradle = any(
        (path / filename).is_file()
        for filename in ("build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts")
    )

    if has_maven:
        return _maven_project(path)
    if has_gradle:
        return _gradle_project(path)

    raise ProjectDetectionError(
        "Could not detect Maven or Gradle project. Expected pom.xml, build.gradle, "
        "build.gradle.kts, settings.gradle, or settings.gradle.kts."
    )


def _maven_project(path: Path) -> ProjectInfo:
    wrapper = _wrapper_command(path, "mvnw")
    if wrapper:
        return ProjectInfo(path=path, build_tool=BuildTool.MAVEN, command=[wrapper, "spring-boot:run"], uses_wrapper=True)
    system_maven = _resolve_system_command("mvn")
    return ProjectInfo(path=path, build_tool=BuildTool.MAVEN, command=[system_maven, "spring-boot:run"], uses_wrapper=False)


def _gradle_project(path: Path) -> ProjectInfo:
    wrapper = _wrapper_command(path, "gradlew")
    if wrapper:
        return ProjectInfo(path=path, build_tool=BuildTool.GRADLE, command=[wrapper, "bootRun"], uses_wrapper=True)
    system_gradle = _resolve_system_command("gradle")
    return ProjectInfo(path=path, build_tool=BuildTool.GRADLE, command=[system_gradle, "bootRun"], uses_wrapper=False)


def _wrapper_command(path: Path, base_name: str) -> str | None:
    candidates = [base_name]
    if _is_windows():
        candidates = [f"{base_name}.cmd", f"{base_name}.bat", base_name]

    for candidate in candidates:
        wrapper = path / candidate
        if wrapper.is_file():
            return str(wrapper)

    return None


def _is_windows() -> bool:
    import os

    return os.name == "nt"


def _resolve_system_command(base_name: str) -> str:
    candidates = [base_name]
    if _is_windows():
        candidates = [f"{base_name}.cmd", f"{base_name}.bat", f"{base_name}.exe", base_name]

    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved

    return base_name
