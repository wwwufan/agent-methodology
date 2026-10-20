"""三角色省略模型后的 bootstrap、doctor 与编排门禁回归测试。"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BOOTSTRAP = REPO / "scripts/bootstrap_project.py"
CHECK = REPO / "skills/single-phase-execution-loop/scripts/check_codex_backend.py"
ROLES = ("designer", "executor", "reviewer")


class ModelInheritanceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)

    def run_json(self, script, *args, expected=0):
        proc = subprocess.run(
            [sys.executable, "-B", str(script), *map(str, args)],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(proc.returncode, expected, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def bootstrap(self, *args):
        return self.run_json(
            BOOTSTRAP, self.project, "--backend", "both", "--skip-operations",
            "--codex-bin", "/nonexistent/codex", "--json", *args,
        )

    def check(self, *args, expected=0):
        return self.run_json(
            CHECK, "--repo-root", self.project,
            "--codex-bin", "/nonexistent/codex", *args, expected=expected,
        )

    def test_bootstrap_and_gate_without_cli_or_model(self):
        self.bootstrap()
        for role in ROLES:
            payload = tomllib.loads((self.project / f".codex/agents/{role}.toml").read_text())
            self.assertNotIn("model", payload)
            self.assertEqual(payload["model_reasoning_effort"], "medium")
            self.assertTrue(payload["developer_instructions"])
            self.assertEqual(payload["sandbox_mode"],
                             "workspace-write" if role == "executor" else "read-only")
            self.assertEqual(payload["approval_policy"],
                             "on-request" if role == "executor" else "never")
            frontmatter = (self.project / f".cursor/agents/{role}.md").read_text().split("---")[1]
            self.assertFalse(any(line.startswith("model:") for line in frontmatter.splitlines()))
        report = self.check()
        self.assertEqual(report["status"], "ready")
        self.assertIsNone(report["active_model"])
        self.assertEqual(report["model_binding"], "backend_managed_inheritance")
        self.assertTrue(all(row["model"] is None for row in report["roles"].values()))

    def test_parent_model_can_change_without_rewriting_roles(self):
        self.bootstrap()
        before = {p: p.read_bytes() for p in (self.project / ".codex/agents").glob("*.toml")}
        for model in ("parent-a", "parent-b"):
            report = self.check("--active-model", model, "--available-model", model)
            self.assertEqual(report["status"], "ready")
            self.assertEqual(report["active_model"], model)
        self.assertTrue(all(p.read_bytes() == content for p, content in before.items()))

    def test_deprecated_model_flags_do_not_pin_models(self):
        report = self.bootstrap("--model", "old-codex", "--cursor-model", "old-cursor",
                                "--cursor-executor-model", "old-executor")
        self.assertTrue(report["warnings"])
        self.check()
        for role in ROLES:
            self.assertNotIn("model", tomllib.loads(
                (self.project / f".codex/agents/{role}.toml").read_text()))

    def test_explicit_model_even_empty_is_rejected(self):
        self.bootstrap()
        path = self.project / ".codex/agents/designer.toml"
        original = path.read_text()
        for model in ("fixed-model", ""):
            path.write_text(f'model = "{model}"\n' + original)
            report = self.check(expected=1)
            self.assertEqual(report["reason_class"], "model-binding")

    def test_sandbox_and_contract_are_still_required(self):
        self.bootstrap()
        path = self.project / ".codex/agents/reviewer.toml"
        original = path.read_text()
        path.write_text(original.replace('sandbox_mode = "read-only"',
                                         'sandbox_mode = "workspace-write"'))
        self.assertIn("read-only", self.check(expected=1)["reason"])
        path.write_text(original.split("developer_instructions")[0])
        self.assertEqual(self.check(expected=1)["reason_class"], "role-config")

    def test_missing_registration_and_path_escape_are_rejected(self):
        self.bootstrap()
        registry = self.project / ".codex/config.toml"
        original = registry.read_text()
        registry.write_text(original.replace("[agents.designer]", "[agents.other]"))
        self.assertEqual(self.check(expected=1)["reason_class"], "role-config")
        registry.write_text(original.replace("agents/designer.toml", "../outside.toml"))
        self.assertIn("越出", self.check(expected=1)["reason"])

    def test_project_wide_model_override_is_rejected(self):
        self.bootstrap()
        registry = self.project / ".codex/config.toml"
        registry.write_text('[agents]\ndefault_subagent_model = "fixed"\n' + registry.read_text())
        self.assertIn("default_subagent_model", self.check(expected=1)["reason"])

    def test_doctor_accepts_inherited_model(self):
        self.bootstrap()
        spec = importlib.util.spec_from_file_location("model_inheritance_doctor",
                                                      REPO / "scripts/doctor.py")
        doctor = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(doctor)
        rows = doctor._group6(self.project, REPO)
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(row["level"] == "ok" for row in rows), rows)
        path = self.project / ".codex/agents/designer.toml"
        path.write_text('model = "fixed"\n' + path.read_text())
        self.assertTrue(any(row["level"] == "fail" for row in doctor._group6(self.project, REPO)))

    def test_bootstrap_does_not_overwrite_existing_roles(self):
        self.bootstrap()
        path = self.project / ".codex/agents/designer.toml"
        content = path.read_text() + "\n# project customization\n"
        path.write_text(content)
        self.bootstrap()
        self.assertEqual(path.read_text(), content)


if __name__ == "__main__":
    unittest.main()
