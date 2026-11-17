"""Regression tests for the workflow's theme step, not a recovery build.

Run: uv run --with pyyaml python -m unittest discover -s ci -p 'test_*.py' -v
The small XML files below are explicit test fixtures. They model the Android
checkout layout without downloading or building the Android sources.
"""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

import yaml


ROOT = Path(__file__).resolve().parents[1]


class WorkflowThemeTest(unittest.TestCase):
    def test_theme_step_uses_recovery_checkout(self):
        workflow = yaml.safe_load(
            (ROOT / ".github/workflows/ofox-fuxi.yml").read_text(encoding="utf-8")
        )
        steps = workflow["jobs"]["build"]["steps"]
        step = next(
            item for item in steps
            if '$GITHUB_WORKSPACE/ci/fix_ofox_theme.py' in item.get("run", "")
        )
        command = step["run"].replace(
            "${{ github.event.inputs.MANIFEST_BRANCH }}", "12.1"
        )
        with tempfile.TemporaryDirectory(prefix="ofox-workflow-") as directory:
            workspace = Path(directory)
            (workspace / "ci").mkdir()
            shutil.copy2(ROOT / "ci/fix_ofox_theme.py", workspace / "ci")
            recovery = workspace / "fox_12.1/bootable/recovery"
            theme = recovery / "gui/theme/portrait_hdpi"
            theme.mkdir(parents=True)
            (theme / "ui.xml").write_text(
                '<recovery><details><resolution width="1080" height="1920" />'
                '</details></recovery>\n', encoding="utf-8"
            )
            (theme / "splash.xml").write_text(
                '<recovery><details><resolution width="1080" h="1920"/>'
                '</details><variables>'
                '<variable name="screen_width" value="1080"/>'
                '<variable name="screen_height" value="1920"/>'
                '</variables></recovery>\n', encoding="utf-8"
            )
            environment = dict(os.environ, GITHUB_WORKSPACE=str(workspace))
            first = subprocess.run(
                ["bash", "-e", "-c", command], cwd=workspace, env=environment,
                text=True, capture_output=True, check=False
            )
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            for filename, attribute in (("ui.xml", "height"), ("splash.xml", "h")):
                resolution = ET.parse(theme / filename).find("./details/resolution")
                assert resolution is not None
                self.assertEqual(resolution.attrib["width"], "1080")
                self.assertEqual(resolution.attrib[attribute], "2400")
            variable = ET.parse(theme / "splash.xml").find(
                './variables/variable[@name="screen_height"]'
            )
            assert variable is not None
            self.assertEqual(variable.attrib["value"], "2400")
            before = {name: (theme / name).read_bytes() for name in ("ui.xml", "splash.xml")}
            again = subprocess.run(
                ["bash", "-e", "-c", command], cwd=workspace, env=environment,
                text=True, capture_output=True, check=False
            )
            self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
            self.assertEqual(before, {name: (theme / name).read_bytes() for name in before})


if __name__ == "__main__":
    unittest.main()
