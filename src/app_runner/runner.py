from __future__ import annotations

import queue
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO
from collections.abc import Callable

from .classifier import (
    Classification,
    ResultKind,
    classify_line,
    process_exit_classification,
    timeout_classification,
    unknown_failure_classification,
)


@dataclass
class RunResult:
    classification: Classification
    exit_code: int | None
    stdout: list[str] = field(default_factory=list)
    stderr: list[str] = field(default_factory=list)

    @property
    def succeeded(self) -> bool:
        return self.classification.kind == ResultKind.SUCCESS


def run_until_result(
    command: list[str],
    cwd: Path,
    timeout_seconds: int,
    stream_output: bool = True,
    stop_after_start: bool = False,
    on_startup_result: Callable[[Classification], None] | None = None,
) -> RunResult:
    try:
        process = subprocess.Popen(
            command,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )
    except FileNotFoundError as exc:
        command_name = command[0] if command else "<empty command>"
        return RunResult(
            Classification(ResultKind.DEPENDENCY_ERROR, f"Command not found: {command_name}", str(exc)),
            None,
        )
    except PermissionError as exc:
        command_name = command[0] if command else "<empty command>"
        return RunResult(
            Classification(ResultKind.DEPENDENCY_ERROR, f"Command is not executable: {command_name}", str(exc)),
            None,
        )

    output_queue: queue.Queue[tuple[str, str | None]] = queue.Queue()
    stdout: list[str] = []
    stderr: list[str] = []

    threads = [
        threading.Thread(target=_enqueue_lines, args=("stdout", process.stdout, output_queue), daemon=True),
        threading.Thread(target=_enqueue_lines, args=("stderr", process.stderr, output_queue), daemon=True),
    ]
    for thread in threads:
        thread.start()

    deadline = time.monotonic() + timeout_seconds
    last_failure: Classification | None = None
    startup_success: Classification | None = None

    try:
        while True:
            if startup_success is None and time.monotonic() >= deadline:
                _terminate(process)
                return RunResult(timeout_classification(timeout_seconds), process.poll(), stdout, stderr)

            exit_code = process.poll()
            if exit_code is not None:
                _drain_queue(output_queue, stdout, stderr, stream_output)
                _close_process_streams(process)
                if startup_success is not None:
                    return RunResult(startup_success, exit_code, stdout, stderr)
                if last_failure is not None:
                    return RunResult(last_failure, exit_code, stdout, stderr)
                return RunResult(process_exit_classification(exit_code), exit_code, stdout, stderr)

            try:
                source, line = output_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            if line is None:
                continue

            _record_line(source, line, stdout, stderr, stream_output)
            classification = classify_line(line)
            if classification is None or startup_success is not None:
                continue

            if classification.kind == ResultKind.SUCCESS:
                startup_success = classification
                if on_startup_result is not None:
                    on_startup_result(classification)
                if stop_after_start:
                    _terminate(process)
                    return RunResult(classification, process.poll(), stdout, stderr)
                continue

            last_failure = classification
    except KeyboardInterrupt:
        _terminate(process)
        if startup_success is not None:
            return RunResult(startup_success, process.poll(), stdout, stderr)
        return RunResult(unknown_failure_classification(process.poll()), process.poll(), stdout, stderr)


def _enqueue_lines(source: str, stream: TextIO | None, output_queue: queue.Queue[tuple[str, str | None]]) -> None:
    if stream is None:
        output_queue.put((source, None))
        return

    try:
        for line in stream:
            output_queue.put((source, line.rstrip("\n")))
    finally:
        output_queue.put((source, None))


def _drain_queue(
    output_queue: queue.Queue[tuple[str, str | None]],
    stdout: list[str],
    stderr: list[str],
    stream_output: bool,
) -> None:
    while True:
        try:
            source, line = output_queue.get_nowait()
        except queue.Empty:
            return
        if line is not None:
            _record_line(source, line, stdout, stderr, stream_output)


def _record_line(source: str, line: str, stdout: list[str], stderr: list[str], stream_output: bool) -> None:
    if source == "stderr":
        stderr.append(line)
    else:
        stdout.append(line)

    if stream_output:
        print(line, flush=True)


def _terminate(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        _close_process_streams(process)
        return

    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
    finally:
        _close_process_streams(process)


def _close_process_streams(process: subprocess.Popen[str]) -> None:
    _close_stream(process.stdout)
    _close_stream(process.stderr)


def _close_stream(stream: TextIO | None) -> None:
    if stream is not None and not stream.closed:
        stream.close()
