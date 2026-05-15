from __future__ import annotations

import unittest

from app_runner.classifier import ResultKind, classify_line


class ClassifierTests(unittest.TestCase):
    def test_detects_success(self) -> None:
        result = classify_line("Started DemoApplication in 2.184 seconds (process running for 2.4)")

        self.assertIsNotNone(result)
        self.assertEqual(result.kind, ResultKind.SUCCESS)

    def test_detects_port_in_use(self) -> None:
        result = classify_line("Web server failed to start. Port 8080 was already in use.")

        self.assertIsNotNone(result)
        self.assertEqual(result.kind, ResultKind.PORT_IN_USE)

    def test_detects_main_class_not_found(self) -> None:
        result = classify_line("Unable to find a suitable main class, please add a 'mainClass' property")

        self.assertIsNotNone(result)
        self.assertEqual(result.kind, ResultKind.MAIN_CLASS_NOT_FOUND)

    def test_detects_java_version_mismatch(self) -> None:
        result = classify_line("UnsupportedClassVersionError: class file version is unsupported")

        self.assertIsNotNone(result)
        self.assertEqual(result.kind, ResultKind.JAVA_VERSION_MISMATCH)

    def test_ignores_unrelated_line(self) -> None:
        self.assertIsNone(classify_line("Downloading dependencies..."))
