from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts/sync_projects.py"


class SyncProjectsIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.project = self.root / "project"
        self.project.mkdir()
        subprocess.run(["git", "init", "-q", str(self.project)], check=True)
        (self.project / ".agents/skills").mkdir(parents=True)
        self.config = self.root / "targets.json"
        self.config.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "projects": [
                        {
                            "name": "fixture",
                            "path": str(self.project),
                            "ignore_links": True,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp.cleanup()

    def run_sync(self, *args, expected=0):
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--config", str(self.config), *args],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(proc.returncode, expected, proc.stdout + proc.stderr)
        return proc

    def test_sync_check_and_safe_prune(self):
        first = self.run_sync("--json")
        first_payload = json.loads(first.stdout)
        skill_names = sorted(path.name for path in (REPO / "skills").iterdir() if path.is_dir())
        self.assertEqual(first_payload["projects"][0]["sync_summary"]["created"], len(skill_names))
        self.assertEqual(
            len(first_payload["projects"][0]["exclude_added"]), len(skill_names)
        )
        for name in skill_names:
            link = self.project / ".agents/skills" / name
            self.assertTrue(link.is_symlink(), name)
            self.assertEqual(link.resolve(), (REPO / "skills" / name).resolve())

        exclude = Path(
            subprocess.check_output(
                [
                    "git",
                    "-C",
                    str(self.project),
                    "rev-parse",
                    "--path-format=absolute",
                    "--git-path",
                    "info/exclude",
                ],
                text=True,
            ).strip()
        ).read_text(encoding="utf-8")
        for name in skill_names:
            self.assertIn(f"/.agents/skills/{name}", exclude)
        self.run_sync("--check")

        stale = self.project / ".agents/skills/removed-methodology-skill"
        stale.symlink_to(REPO / "skills/removed-methodology-skill")
        foreign_target = self.root / "foreign"
        foreign_target.mkdir()
        foreign = self.project / ".agents/skills/foreign-skill"
        foreign.symlink_to(foreign_target)

        self.run_sync("--check", expected=1)
        self.run_sync("--prune")
        self.assertFalse(stale.is_symlink())
        self.assertTrue(foreign.is_symlink())

    def test_invalid_target_fails_before_writes(self):
        bad = self.root / "bad-targets.json"
        bad.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "projects": [
                        {"name": "missing", "path": str(self.root / "missing")}
                    ],
                }
            ),
            encoding="utf-8",
        )
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--config", str(bad)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("project path does not exist", proc.stdout)


if __name__ == "__main__":
    unittest.main()
