from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aleph.config import load_client_blueprints, register_client_blueprints
from aleph.demo.helpers import create_engine


class ServiceFoundationsTests(unittest.TestCase):
    def setUp(self) -> None:
        test_tmp = ROOT / ".aleph-test-tmp" / "service-workdir"
        shutil.rmtree(test_tmp, ignore_errors=True)
        test_tmp.mkdir(parents=True, exist_ok=True)
        self.root_dir = test_tmp
        self.engine = create_engine(self.root_dir)

    def tearDown(self) -> None:
        self.engine.store.close()
        shutil.rmtree(self.root_dir, ignore_errors=True)

    def test_multiple_sessions_can_be_created_and_listed(self) -> None:
        first = self.engine.create_session(title="Session A")
        second = self.engine.create_session(title="Session B", initial_client_id="sol")

        sessions = self.engine.list_sessions(limit=10)

        self.assertEqual(first["session"]["title"], "Session A")
        self.assertEqual(second["session"]["title"], "Session B")
        self.assertGreaterEqual(len(sessions), 2)
        self.assertTrue(any(item["title"] == "Session A" for item in sessions))
        self.assertTrue(any(item["title"] == "Session B" for item in sessions))

    def test_event_cursor_query_returns_only_newer_events(self) -> None:
        session = self.engine.create_session(title="Cursor Session")["session"]
        self.engine.process_user_turn("请记住这次提交。", session_id=session["id"])
        events = self.engine.store.list_session_events(session["id"], channel="presentation", limit=20)
        midpoint = events[1]["created_at"]

        newer = self.engine.store.list_session_events_after(
            session["id"],
            channel="presentation",
            after_created_at=midpoint,
            limit=20,
        )

        self.assertTrue(all(item["created_at"] > midpoint for item in newer))

    def test_json_client_blueprint_loader_registers_clients(self) -> None:
        config_path = self.root_dir / "clients.json"
        payload = {
            "clients": [
                {
                    "id": "json-echo",
                    "display_name": "Json Echo",
                    "role": "json configured agent",
                    "adapter_kind": "mock",
                    "system_prompt": "Respond as a JSON-loaded client.",
                    "declared_capability": {
                        "domains": ["json"],
                        "permissions": ["echo"],
                        "handoff_keywords": ["json"],
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
                }
            ]
        }
        config_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        loaded = load_client_blueprints(config_path)
        registered = register_client_blueprints(self.engine, config_path)

        self.assertEqual(loaded[0]["id"], "json-echo")
        self.assertEqual(registered[0]["id"], "json-echo")
        self.assertIsNotNone(self.engine.client_registry.get("json-echo"))
