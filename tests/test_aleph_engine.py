from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aleph.demo.helpers import create_engine


class AlephEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        test_tmp = ROOT / ".aleph-test-tmp" / "workdir"
        shutil.rmtree(test_tmp, ignore_errors=True)
        test_tmp.mkdir(parents=True, exist_ok=True)
        self.root_dir = str(test_tmp)
        self.engine = create_engine(self.root_dir)

    def tearDown(self) -> None:
        self.engine.store.close()
        shutil.rmtree(self.root_dir, ignore_errors=True)

    def test_continuous_reality_survives_client_switch(self) -> None:
        self.engine.process_user_turn("我答应合作方今晚之前发过去。")
        switched = self.engine.process_user_turn("你来拍板并接管。")

        self.assertEqual(switched["active_client_id"], "sol")
        self.assertTrue(switched["switch_decision"]["approved"])
        self.assertIn("inherit", switched["reply"])

        state = self.engine.inspect_state()
        self.assertEqual(state["foreground"]["client_id"], "sol")
        self.assertTrue(
            any(item["kind"] == "pending_commitment" for item in state["reality"]["consequences"])
        )

    def test_private_memory_stays_client_private_while_shared_memory_remains_visible(self) -> None:
        self.engine.process_user_turn("我答应合作方今晚之前发过去。")
        self.engine.process_user_turn("你来拍板并接管。")

        iris_private = self.engine.store.list_memories(
            {"layer": "private", "persona_id": "iris", "limit": 20}
        )
        sol_private = self.engine.store.list_memories(
            {"layer": "private", "persona_id": "sol", "limit": 20}
        )
        sol_shared = self.engine.store.list_memories(
            {"layer": "shared", "domains": ["commitments", "social"], "limit": 20}
        )

        self.assertTrue(any("Iris noted" in item["content"] for item in iris_private))
        self.assertTrue(any("Sol evaluated" in item["content"] for item in sol_private))
        self.assertTrue(any(item["domain"] == "commitments" for item in sol_shared))
        self.assertFalse(any("Iris noted" in item["content"] for item in sol_private))

    def test_switches_are_explainable_and_logged_at_the_client_level(self) -> None:
        result = self.engine.process_user_turn("你来拍板并接管吧，我们得推进。")

        self.assertTrue(result["switch_decision"]["approved"])
        self.assertIn("takes foreground", result["switch_decision"]["explanation"])
        self.assertIn("Incoming client", result["switch_decision"]["handoff_summary"])

        latest_switch = self.engine.inspect_state()["switches"][0]
        self.assertEqual(latest_switch["to_client_id"], "sol")
        self.assertIn("authority", latest_switch["reason"])

    def test_foreground_control_stays_singular_after_multiple_turns(self) -> None:
        self.engine.process_user_turn("我答应合作方今晚之前发过去。")
        self.engine.process_user_turn("你来拍板并接管。")
        self.engine.process_user_turn("我刚刚把话说重了，关系有点僵。")

        foreground = self.engine.store.get_foreground_control()
        self.assertIsNotNone(foreground)
        self.assertIn(foreground["client_id"], ["sol", "mire"])

        row = self.engine.store.connection.execute(
            "SELECT COUNT(*) AS count FROM foreground_control"
        ).fetchone()
        self.assertEqual(row["count"], 1)

    def test_client_contexts_enforce_shared_domain_isolation_beyond_prompt_separation(self) -> None:
        def mono_handler(context):
            with self.assertRaises(PermissionError):
                context.memory.get_shared("social")
            return context.actions.reply("Mono stays within its own boundaries.").finish()

        self.engine.register_client(
            {
                "id": "mono",
                "persona_id": "minimalist",
                "display_name": "Mono",
                "voice": "minimal",
                "specialties": ["focus"],
                "boundaries": ["no social inspection"],
                "permissions": ["focus"],
                "shared_domains": [],
                "capabilities": {
                    "readable_shared_domains": [],
                    "writable_shared_domains": [],
                    "allowed_actions": ["reply"],
                    "request_only_actions": ["switch_foreground"],
                    "allowed_tools": ["actions.reply"],
                },
                "isolation": {
                    "transcript_window": 4,
                    "private_memory_window": 4,
                    "shared_memory_window": 4,
                    "consequence_window": 4,
                    "handoff_window": 2,
                },
                "handler": mono_handler,
            }
        )

        result = self.engine.process_user_turn("切换到 mono。", requested_client_id="mono")
        self.assertEqual(result["active_client_id"], "mono")
        self.assertIn("within its own boundaries", result["reply"])


if __name__ == "__main__":
    unittest.main()
