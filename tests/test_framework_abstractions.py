from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aleph.core.foreground_controller import ForegroundController
from aleph.core.runtime_signal_collector import RuntimeSignalCollector
from aleph.core.stream_emitter import StreamEmitter
from aleph.demo.helpers import create_engine
from aleph.domain import AppSpec, ClientBlueprint, HandoffEnvelope, StreamEvent


class FrameworkAbstractionsTests(unittest.TestCase):
    def setUp(self) -> None:
        test_tmp = ROOT / ".aleph-test-tmp" / "framework-workdir"
        shutil.rmtree(test_tmp, ignore_errors=True)
        test_tmp.mkdir(parents=True, exist_ok=True)
        self.root_dir = str(test_tmp)
        self.engine = create_engine(self.root_dir)

    def tearDown(self) -> None:
        self.engine.store.close()
        shutil.rmtree(self.root_dir, ignore_errors=True)

    def test_domain_models_are_serializable(self) -> None:
        app = AppSpec(id="demo-app", name="Demo App")
        blueprint = ClientBlueprint(
            id="iris",
            display_name="Iris",
            role="continuity archivist",
            system_prompt="Keep continuity.",
            adapter_kind="nanobot",
        )
        handoff = HandoffEnvelope(
            from_client_id="iris",
            to_client_id="sol",
            reason="execution needed",
            explanation="Sol takes over for execution.",
            summary="Execution handoff.",
        )
        event = StreamEvent(
            event_kind="status",
            source="iris",
            created_at="2026-04-20T00:00:00Z",
            payload={"message": "working"},
        )

        self.assertEqual(app.to_dict()["id"], "demo-app")
        self.assertEqual(blueprint.to_dict()["adapter_kind"], "nanobot")
        self.assertEqual(handoff.to_dict()["to_client_id"], "sol")
        self.assertEqual(event.to_dict()["payload"]["message"], "working")

    def test_foreground_controller_updates_single_foreground(self) -> None:
        session = self.engine.inspect_state()["session"]
        controller = ForegroundController(self.engine.client_session_manager)

        updated = controller.switch_foreground(
            session_id=session["id"],
            client_id="sol",
            reason="test foreground move",
        )

        self.assertEqual(updated["foreground_client_id"], "sol")
        self.assertEqual(controller.get_foreground_client_id(updated), "sol")

    def test_stream_emitter_persists_framework_stream_event(self) -> None:
        session = self.engine.inspect_state()["session"]
        emitter = StreamEmitter(self.engine.store)

        event = emitter.emit(
            session_id=session["id"],
            event_kind="status",
            payload={"message": "framework event"},
            source="test",
        )

        self.assertEqual(event["event_kind"], "status")
        persisted = self.engine.store.list_session_events(session["id"], channel="presentation", limit=5)
        self.assertTrue(any(item["payload"].get("message") == "framework event" for item in persisted))

    def test_runtime_signal_collector_updates_client_runtime_state(self) -> None:
        collector = RuntimeSignalCollector(self.engine.store)
        updated = collector.collect(
            client_id="iris",
            runtime_signals_patch={"health": "ok", "last_latency_ms": 12.5},
            agent_native_state_patch={"last_mode": "test"},
        )

        self.assertEqual(updated["runtime_signals"]["health"], "ok")
        self.assertEqual(updated["agent_native_state"]["last_mode"], "test")
