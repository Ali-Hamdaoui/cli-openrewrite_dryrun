from __future__ import annotations

import sys
import unittest
from pathlib import Path

from app_runner.classifier import ResultKind
from app_runner.runner import run_until_result
from helpers import workspace_temp_dir


class RunnerTests(unittest.TestCase):
    def test_detects_startup_success_from_process_output(self) -> None:
        command = [
            sys.executable,
            "-c",
            "print('Started DemoApplication in 1.0 seconds', flush=True)",
        ]

        with workspace_temp_dir() as tmp:
            result = run_until_result(
                command=command,
                cwd=Path(tmp),
                timeout_seconds=5,
                stream_output=False,
                stop_after_start=True,
            )

        self.assertTrue(result.succeeded)
        self.assertEqual(result.classification.kind, ResultKind.SUCCESS)

    def test_times_out_when_no_startup_signal_is_seen(self) -> None:
        command = [sys.executable, "-c", "import time; time.sleep(10)"]

        with workspace_temp_dir() as tmp:
            result = run_until_result(
                command=command,
                cwd=Path(tmp),
                timeout_seconds=1,
                stream_output=False,
                stop_after_start=True,
            )

        self.assertFalse(result.succeeded)
        self.assertEqual(result.classification.kind, ResultKind.TIMEOUT)
