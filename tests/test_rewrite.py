from __future__ import annotations

import unittest
from pathlib import Path

from app_runner.rewrite import build_rewrite_command, prepare_rewrite_plugin
from helpers import workspace_temp_dir


PLUGIN_TXT = """<plugin>
  <groupId>org.openrewrite.maven</groupId>
  <artifactId>rewrite-maven-plugin</artifactId>
  <version>6.23.0</version>
</plugin>
"""


class RewriteTests(unittest.TestCase):
    def test_injects_plugin_into_project_pom(self) -> None:
        with workspace_temp_dir() as tmp:
            project = Path(tmp)
            (project / "pom.xml").write_text(
                """<project>
  <modelVersion>4.0.0</modelVersion>
  <groupId>com.example</groupId>
  <artifactId>demo</artifactId>
  <version>1.0.0</version>
</project>""",
                encoding="utf-8",
            )
            plugin_txt = project / "rewrite-plugin.txt"
            plugin_txt.write_text(PLUGIN_TXT, encoding="utf-8")

            prep = prepare_rewrite_plugin(project, plugin_txt, module=None, backup=True)
            pom_text = (project / "pom.xml").read_text(encoding="utf-8")

            self.assertTrue((project / "pom.xml.bak").is_file())
            self.assertEqual(prep.plugin_coordinates, ("org.openrewrite.maven", "rewrite-maven-plugin"))
            self.assertIn("<build>", pom_text)
            self.assertIn("<artifactId>rewrite-maven-plugin</artifactId>", pom_text)

    def test_build_rewrite_command_with_module(self) -> None:
        command = build_rewrite_command("mvn", "legacy-app")
        self.assertEqual(command, ["mvn", "-f", str(Path("legacy-app") / "pom.xml"), "rewrite:dryRun"])
