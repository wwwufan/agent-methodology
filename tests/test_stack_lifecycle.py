"""真实 CLI 生命周期回归；不把文案断言当作 Agent 行为验证。"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "skills/campaign-work-stack/scripts/stack.py"


class StackLifecycleTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / ".git").mkdir()
        self.layout = "workstacks"

    def cli(self, command, *args, campaign="alpha", expected=0):
        result = subprocess.run(
            [sys.executable, "-B", str(SCRIPT), command,
             "--repo-root", str(self.root), "--campaign", campaign, *args],
            cwd=self.root, text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def stack_path(self, campaign="alpha"):
        return self.root / self.layout / campaign / "active-work-stack.json"

    def data(self, campaign="alpha"):
        return json.loads(self.stack_path(campaign).read_text(encoding="utf-8"))

    @property
    def pointer(self):
        return self.root / self.layout / "_current.json"

    def prepare(self, campaign="alpha"):
        ledger = self.stack_path(campaign).with_name("goal-ledger.md")
        ledger.parent.mkdir(parents=True, exist_ok=True)
        ledger.write_text(f"# Test\n\n- campaign_id: {campaign}\n", encoding="utf-8")
        self.cli("ensure", "--activation", "user_declared", campaign=campaign)
        self.cli("push", "--title", "当前阶段", "--criteria", "验收通过", campaign=campaign)
        self.cli("use", campaign=campaign)
        self.cli("verify", campaign=campaign)

    def close(self, frame="F-001", campaign="alpha", expected=0):
        return self.cli("pop", "--frame", frame, "--terminal", "done",
                        "--note", "验收完成，证据：test fixture",
                        campaign=campaign, expected=expected)

    def test_no_stack_does_not_silently_create(self):
        self.cli("survey")
        self.cli("push", "--title", "未批准", expected=2)
        self.cli("capture", "--text", "未批准", expected=2)
        self.cli("verify", expected=2)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), [".git"])

    def test_ensure_requires_explicit_activation(self):
        self.cli("ensure", expected=2)
        self.cli("ensure", "--activation", "auto_orchestration", expected=2)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), [".git"])

    def test_queued_future_phase_does_not_block_current_close(self):
        self.prepare()
        self.cli("push", "--title", "后续阶段待批准", "--criteria", "用户批准")
        pointer_before = self.pointer.read_bytes()
        self.cli("verify")
        self.close()
        self.cli("verify")
        self.assertEqual([f["status"] for f in self.data()["frames"]], ["done", "queued"])
        self.assertEqual(self.pointer.read_bytes(), pointer_before)

    def test_duplicate_pop_does_not_modify_history(self):
        self.prepare()
        self.cli("push", "--title", "后续", "--criteria", "待批准")
        self.close()
        before = self.stack_path().read_bytes()
        view_before = self.stack_path().with_suffix(".md").read_bytes()
        self.close(expected=2)
        self.assertEqual(self.stack_path().read_bytes(), before)
        self.assertEqual(self.stack_path().with_suffix(".md").read_bytes(), view_before)

    def test_pending_capture_blocks_verify_until_resolved(self):
        self.prepare()
        self.cli("capture", "--found-in", "F-001", "--text", "待判定问题")
        self.cli("verify", expected=1)
        self.cli("resolve", "--capture", "C-001", "--disposition", "note",
                 "--pointer", "goal-ledger.md")
        self.cli("verify")
        self.assertEqual(self.data()["frames"][0]["status"], "active")

    def test_exploration_child_closure_restores_parent(self):
        self.prepare()
        self.cli("capture", "--found-in", "F-001", "--text", "需验证假设")
        self.cli("push", "--title", "验证假设", "--criteria", "得到区分证据",
                 "--parent", "F-001", "--activate")
        self.cli("resolve", "--capture", "C-001", "--disposition", "blocks",
                 "--frame", "F-002")
        self.cli("verify")
        self.close("F-002")
        self.cli("verify")
        self.assertEqual([f["status"] for f in self.data()["frames"]], ["active", "done"])

    def test_final_pop_releases_only_pointer_and_keeps_history(self):
        self.prepare()
        before_events = self.data()["event_log"]
        self.close()
        self.assertFalse(self.pointer.exists())
        self.cli("verify")
        self.assertEqual(self.data()["event_log"][:len(before_events)], before_events)
        self.assertEqual(self.data()["frames"][0]["status"], "done")
        self.assertEqual(len(self.data()["pop_log"]), 1)
        self.assertTrue(self.stack_path().with_suffix(".md").exists())

    def test_final_pop_preserves_other_campaign_pointer(self):
        self.prepare()
        self.prepare("zulu")
        before = self.pointer.read_bytes()
        self.close()
        self.assertEqual(self.pointer.read_bytes(), before)
        self.cli("verify", campaign="zulu")

    def test_final_pop_does_not_clear_same_id_at_different_path(self):
        self.prepare()
        # 模拟旧/外部指针；不能仅凭 campaign 同名清除别处的绑定。
        pointer = json.loads(self.pointer.read_text(encoding="utf-8"))
        pointer["stack_path"] = "elsewhere/active-work-stack.json"
        self.pointer.write_text(json.dumps(pointer), encoding="utf-8")
        before = self.pointer.read_bytes()
        self.close()
        self.assertEqual(self.pointer.read_bytes(), before)

    def test_final_pop_works_with_custom_layout(self):
        (self.root / "workstacks").mkdir()
        (self.root / "workstacks/config.json").write_text(
            json.dumps({"workstack_root": "state/queues"}), encoding="utf-8",
        )
        self.layout = "state/queues"
        self.prepare()
        self.close()
        self.assertFalse(self.pointer.exists())
        self.cli("verify")


if __name__ == "__main__":
    unittest.main()
