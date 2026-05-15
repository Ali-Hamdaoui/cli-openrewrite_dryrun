from __future__ import annotations

import os
import unittest

from app_runner.classifier import Classification, ResultKind
from app_runner.cli import _build_command, _extract_migration_warnings
from app_runner.detection import BuildTool
from app_runner.runner import RunResult


class CliTests(unittest.TestCase):
    def test_build_command_adds_maven_module_and_main_class(self) -> None:
        command = _build_command(
            base_command=["mvn", "spring-boot:run"],
            build_tool=BuildTool.MAVEN,
            module="shoppoc-api",
            main_class="com.example.Application",
        )

        self.assertEqual(
            command,
            [
                "mvn",
                "-f",
                os.path.join("shoppoc-api", "pom.xml"),
                "-Dspring-boot.run.mainClass=com.example.Application",
                "spring-boot:run",
            ],
        )

    def test_build_command_keeps_gradle_unchanged(self) -> None:
        command = _build_command(
            base_command=["gradle", "bootRun"],
            build_tool=BuildTool.GRADLE,
            module="ignored",
            main_class="ignored.Main",
        )

        self.assertEqual(command, ["gradle", "bootRun"])

    def test_extract_migration_warnings(self) -> None:
        result = RunResult(
            classification=Classification(ResultKind.PROCESS_EXITED, "done"),
            exit_code=1,
            stdout=[
                "[WARNING] Recipe X suggests change",
                "    org.openrewrite.sample.RecipeA",
                "Normal line",
                "~> src/main/java/App.java",
            ],
            stderr=["WARN another warning", "WARN another warning"],
        )

        warnings = _extract_migration_warnings(result)
        self.assertEqual(
            warnings,
            [
                "[WARNING] Recipe X suggests change",
                "org.openrewrite.sample.RecipeA",
                "~> src/main/java/App.java",
                "WARN another warning",
                "WARN another warning",
            ],
        )
