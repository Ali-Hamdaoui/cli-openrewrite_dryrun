from __future__ import annotations

import os
import unittest
from pathlib import Path

from app_runner.detection import BuildTool, ProjectDetectionError, detect_project
from helpers import workspace_temp_dir


class DetectionTests(unittest.TestCase):
    def test_detects_maven_and_prefers_wrapper(self) -> None:
        with workspace_temp_dir() as tmp:
            path = Path(tmp)
            (path / "pom.xml").write_text("<project />", encoding="utf-8")
            wrapper_name = "mvnw.cmd" if os.name == "nt" else "mvnw"
            (path / wrapper_name).write_text("", encoding="utf-8")

            project = detect_project(path)

            self.assertEqual(project.build_tool, BuildTool.MAVEN)
            self.assertTrue(project.uses_wrapper)
            self.assertEqual(project.command[-1], "spring-boot:run")

    def test_detects_gradle_and_prefers_wrapper(self) -> None:
        with workspace_temp_dir() as tmp:
            path = Path(tmp)
            (path / "build.gradle").write_text("", encoding="utf-8")
            wrapper_name = "gradlew.cmd" if os.name == "nt" else "gradlew"
            (path / wrapper_name).write_text("", encoding="utf-8")

            project = detect_project(path)

            self.assertEqual(project.build_tool, BuildTool.GRADLE)
            self.assertTrue(project.uses_wrapper)
            self.assertEqual(project.command[-1], "bootRun")

    def test_rejects_unknown_project(self) -> None:
        with workspace_temp_dir() as tmp:
            with self.assertRaises(ProjectDetectionError):
                detect_project(tmp)
