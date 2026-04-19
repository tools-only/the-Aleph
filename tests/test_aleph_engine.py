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

    def test_private_memory_isolated_and_shared_memory_governed(self) -> None:
        self.engine.process_user_turn("请记住，我答应今晚之前给合作方一个版本。")
        self.engine.process_user_turn("你来拍板并且推进这件事。")

        session_id = self.engine.inspect_state()["session"]["id"]
        iris_private = self.engine.store.list_memories(
            {
                "session_id": session_id,
                "layer": "private",
                "owner_client_id": "iris",
                "limit": 20,
            }
        )
        sol_private = self.engine.store.list_memories(
            {
                "session_id": session_id,
                "layer": "private",
                "owner_client_id": "sol",
                "limit": 20,
            }
        )
        shared_commitments = self.engine.store.list_memories(
            {
                "session_id": session_id,
                "layer": "shared",
                "domains": ["commitments"],
                "limit": 20,
            }
        )

        self.assertTrue(any("Iris logged" in item["content"] for item in iris_private))
        self.assertTrue(any("Sol evaluated" in item["content"] for item in sol_private))
        self.assertTrue(any(item["domain"] == "commitments" for item in shared_commitments))
        self.assertFalse(any("Iris logged" in item["content"] for item in sol_private))

    def test_rule_based_handoff_is_logged_and_explainable(self) -> None:
        result = self.engine.process_user_turn("你来拍板并且推进这件事。")

        self.assertTrue(result["switch_decision"]["approved"])
        self.assertEqual(result["active_client_id"], "sol")
        self.assertIn("takes over", result["switch_decision"]["explanation"])
        self.assertIn("Incoming client: Sol", result["switch_decision"]["handoff_summary"])

        latest_switch = self.engine.inspect_state()["switches"][0]
        self.assertEqual(latest_switch["to_client_id"], "sol")
        self.assertIn("execution", latest_switch["reason"])

    def test_stream_protocol_exposes_status_delta_handoff_and_final(self) -> None:
        events = list(self.engine.stream_user_turn("你来拍板并且推进这件事。"))
        kinds = [event["event_kind"] for event in events]

        self.assertIn("status", kinds)
        self.assertIn("handoff", kinds)
        self.assertIn("delta", kinds)
        self.assertIn("final", kinds)

    def test_projection_cache_and_prewarm_jobs_are_created(self) -> None:
        cold = self.engine.process_user_turn("请记住，我答应今晚之前给合作方一个版本。")
        warm = self.engine.process_user_turn("请记住，我答应今晚之前给合作方一个版本。")

        self.assertFalse(cold["cache"]["memory_hit"])
        self.assertTrue(warm["cache"]["memory_hit"])
        self.assertTrue(len(self.engine.inspect_state()["prewarm_jobs"]) >= 1)

    def test_second_adapter_can_be_added_without_rewriting_orchestrator(self) -> None:
        def mock_handler(context):
            return (
                context.actions.reply("Mock adapter handled this turn.")
                .patch_runtime_signals(adapter_path="mock")
                .finish()
            )

        self.engine.register_client(
            {
                "id": "echo",
                "display_name": "Echo",
                "role": "mock runtime agent",
                "adapter_kind": "mock",
                "system_prompt": "Respond through the mock adapter.",
                "declared_capability": {
                    "domains": ["mock", "test"],
                    "permissions": ["echo"],
                    "handoff_keywords": ["mock", "echo"],
                },
                "shared_memory_policy": {
                    "read_domains": [],
                    "write_domains": [],
                    "allowed_kinds": ["note"],
                    "write_mode": "append",
                },
                "runtime_preferences": {
                    "transcript_window": 4,
                    "private_memory_window": 4,
                    "shared_memory_window": 4,
                    "handoff_window": 2,
                    "stream_mode": "token-first",
                },
                "handler": mock_handler,
            }
        )

        result = self.engine.process_user_turn("switch to echo", requested_client_id="echo")
        self.assertEqual(result["active_client_id"], "echo")
        self.assertIn("Mock adapter handled", result["reply"])

    def test_memory_view_blocks_unauthorized_shared_reads(self) -> None:
        def guarded_handler(context):
            with self.assertRaises(PermissionError):
                context.memory.get_shared("social")
            return context.actions.reply("Guarded client stayed inside its boundary.").finish()

        self.engine.register_client(
            {
                "id": "mono",
                "display_name": "Mono",
                "role": "isolated agent",
                "adapter_kind": "nanobot",
                "system_prompt": "Do not read shared memory.",
                "shared_memory_policy": {
                    "read_domains": [],
                    "write_domains": [],
                    "allowed_kinds": ["note"],
                    "write_mode": "append",
                },
                "runtime_preferences": {
                    "transcript_window": 4,
                    "private_memory_window": 4,
                    "shared_memory_window": 4,
                    "handoff_window": 2,
                    "stream_mode": "token-first",
                },
                "handler": guarded_handler,
            }
        )
        result = self.engine.process_user_turn("switch to mono", requested_client_id="mono")
        self.assertEqual(result["active_client_id"], "mono")
        self.assertIn("boundary", result["reply"])
