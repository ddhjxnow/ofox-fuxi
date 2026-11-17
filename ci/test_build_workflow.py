"""Workflow configuration regressions; these tests do not build Android.

Run: uv run --with pyyaml python -m unittest discover -s ci -p 'test_*.py' -v
"""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]


def load_workflow():
    return yaml.safe_load(
        (ROOT / ".github/workflows/ofox-fuxi.yml").read_text(encoding="utf-8")
    )


class BuildConfigurationTest(unittest.TestCase):
    def test_reserved_target_device_dir_is_not_exported(self):
        workflow = load_workflow()
        scopes = [("workflow", workflow.get("env", {}))]
        for name, job in workflow["jobs"].items():
            scopes.append((name, job.get("env", {})))
            scopes.extend(
                (f"{name}/{step.get('name', 'step')}", step.get("env", {}))
                for step in job.get("steps", [])
            )
        for location, environment in scopes:
            with self.subTest(location=location):
                self.assertNotIn(
                    "TARGET_DEVICE_DIR", environment,
                    "Android derives TARGET_DEVICE_DIR; exporting it aborts board_config.mk",
                )


def run_build_step(*, source_rc=0, lunch_rc=0, build_rc=0):
    """Exercise the real shell step with explicitly stubbed Android functions.

    This verifies exit propagation/control flow only, not Android compatibility.
    """
    workflow = load_workflow()
    job = workflow["jobs"]["build"]
    step = next(item for item in job["steps"] if item.get("name") == "编译 recovery")
    command = step["run"]
    # PyYAML's YAML 1.1 loader represents the unquoted `on` key as True.
    trigger = workflow.get("on", workflow.get(True))
    for name, details in trigger["workflow_dispatch"]["inputs"].items():
        command = command.replace(
            "${{ github.event.inputs." + name + " }}", str(details["default"])
        )
    if "${{" in command:
        raise AssertionError("Unresolved workflow expression in build regression test")
    with tempfile.TemporaryDirectory(prefix="ofox-build-control-") as directory:
        workspace = Path(directory)
        source = workspace / "fox_12.1"
        (source / "build").mkdir(parents=True)
        event_log = workspace / "events.log"
        # Explicit shell test fixture, not a downloaded or emulated Android build.
        (source / "build/envsetup.sh").write_text(
            'printf "%s\\n" source >> "$TEST_EVENT_LOG"\n'
            'if [ "$TEST_SOURCE_RC" -ne 0 ]; then return "$TEST_SOURCE_RC"; fi\n'
            'lunch() { printf "%s\\n" lunch >> "$TEST_EVENT_LOG"; '
            'return "$TEST_LUNCH_RC"; }\n'
            'make() { printf "%s\\n" make >> "$TEST_EVENT_LOG"; return 0; }\n'
            'mka() { printf "%s\\n" mka >> "$TEST_EVENT_LOG"; '
            'return "$TEST_BUILD_RC"; }\n', encoding="utf-8"
        )
        environment = dict(os.environ)
        for scope in (workflow.get("env", {}), job.get("env", {}), step.get("env", {})):
            environment.update({name: str(value) for name, value in scope.items()})
        environment.update(
            GITHUB_WORKSPACE=str(workspace), TEST_EVENT_LOG=str(event_log),
            TEST_SOURCE_RC=str(source_rc), TEST_LUNCH_RC=str(lunch_rc),
            TEST_BUILD_RC=str(build_rc),
        )
        result = subprocess.run(
            ["bash", "-e", "-c", command], cwd=workspace, env=environment,
            text=True, capture_output=True, check=False, timeout=15,
        )
        events = event_log.read_text().splitlines() if event_log.exists() else []
        return result, events


class BuildControlFlowTest(unittest.TestCase):
    def test_preparation_failure_stops_before_build(self):
        cases = (
            (23, 0, 23, ["source"]),
            (0, 42, 42, ["source", "lunch"]),
        )
        for source_rc, lunch_rc, expected_rc, expected_events in cases:
            with self.subTest(source_rc=source_rc, lunch_rc=lunch_rc):
                result, events = run_build_step(source_rc=source_rc, lunch_rc=lunch_rc)
                self.assertEqual(result.returncode, expected_rc, result.stdout + result.stderr)
                self.assertEqual(events, expected_events)

    def test_build_status_is_preserved(self):
        for build_rc in (0, 17):
            with self.subTest(build_rc=build_rc):
                result, events = run_build_step(build_rc=build_rc)
                self.assertEqual(result.returncode, build_rc, result.stdout + result.stderr)
                self.assertEqual(events[-1], "mka")
                self.assertIn(f"build_rc={build_rc}", result.stdout)


if __name__ == "__main__":
    unittest.main()
