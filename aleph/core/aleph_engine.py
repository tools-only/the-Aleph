from __future__ import annotations

from aleph.adapters import MockAgentAdapter, NanobotAdapter
from aleph.client.registry import ClientRegistry
from aleph.client.session_manager import ClientSessionManager
from aleph.core.edge_gateway import EdgeGateway
from aleph.core.foreground_controller import ForegroundController
from aleph.core.handoff_engine import HandoffEngine
from aleph.core.memory_manager import MemoryManager
from aleph.core.projection_compiler import ProjectionCompiler
from aleph.core.runtime_signal_collector import RuntimeSignalCollector
from aleph.core.session_orchestrator import SessionOrchestrator
from aleph.core.stream_emitter import StreamEmitter
from aleph.core.switch_daemon import SwitchDaemon
from aleph.storage.sqlite_store import SqliteStore


class AlephEngine:
    def __init__(self, *, root_dir=None, store: SqliteStore | None = None, switch_daemon: SwitchDaemon | None = None) -> None:
        self.store = store or SqliteStore(root_dir=root_dir)
        self.switch_daemon = switch_daemon or SwitchDaemon()
        self.client_registry = ClientRegistry(self.store)
        self.client_session_manager = ClientSessionManager(self.store)
        self.memory_manager = MemoryManager(self.store)
        self.projection_compiler = ProjectionCompiler(self.store, self.memory_manager)
        self.foreground_controller = ForegroundController(self.client_session_manager)
        self.stream_emitter = StreamEmitter(self.store)
        self.runtime_signal_collector = RuntimeSignalCollector(self.store)
        self._adapter_registry = {
            "nanobot": NanobotAdapter(),
            "mock": MockAgentAdapter(),
        }
        self.handoff_engine = HandoffEngine(
            store=self.store,
            switch_daemon=self.switch_daemon,
            compiler=self.projection_compiler,
            registry=self.client_registry,
            foreground_controller=self.foreground_controller,
        )
        self.session_orchestrator = SessionOrchestrator(
            store=self.store,
            registry=self.client_registry,
            session_manager=self.client_session_manager,
            foreground_controller=self.foreground_controller,
            compiler=self.projection_compiler,
            memory_manager=self.memory_manager,
            handoff_engine=self.handoff_engine,
            stream_emitter=self.stream_emitter,
            runtime_signal_collector=self.runtime_signal_collector,
            adapter_factory=self.get_adapter,
        )
        self.edge_gateway = EdgeGateway(self)

    def get_adapter(self, kind: str):
        adapter = self._adapter_registry.get(kind)
        if not adapter:
            raise RuntimeError(f"Unsupported adapter kind '{kind}'.")
        return adapter

    def register_client(self, client_definition: dict) -> dict:
        return self.client_registry.register(client_definition)

    def register_persona(self, profile: dict, handler) -> dict:
        definition = dict(profile)
        definition["handler"] = handler
        return self.register_client(definition)

    def list_clients(self) -> list[dict]:
        return self.client_registry.list()

    def list_personas(self) -> list[dict]:
        return self.list_clients()

    def bootstrap(self, *, initial_client_id: str | None = None, title: str = "Aleph Session") -> dict:
        clients = self.list_clients()
        if not clients:
            raise RuntimeError("Cannot bootstrap Aleph without at least one registered client.")
        initial = initial_client_id or clients[0]["id"]
        session = self.session_orchestrator.ensure_session(initial_client_id=initial, title=title)
        return self.inspect_state(session_id=session["id"])

    def create_session(
        self,
        *,
        initial_client_id: str | None = None,
        title: str = "Aleph Session",
        metadata: dict | None = None,
    ) -> dict:
        clients = self.list_clients()
        if not clients:
            raise RuntimeError("Cannot create Aleph session without at least one registered client.")
        initial = initial_client_id or clients[0]["id"]
        session = self.client_session_manager.create_session(
            initial_client_id=initial,
            title=title,
            metadata=metadata,
        )
        return self.inspect_state(session_id=session["id"])

    def list_sessions(self, limit: int = 50) -> list[dict]:
        return self.client_session_manager.list_sessions(limit=limit)

    def get_session_state(self, session_id: str) -> dict:
        return self.inspect_state(session_id=session_id)

    def stream_user_turn(self, user_input: str, *, requested_client_id: str | None = None, session_id: str | None = None):
        session = self.store.get_session(session_id) if session_id else self.client_session_manager.get_active()
        if not session:
            session = self.bootstrap()
            session = self.store.get_session(session["session"]["id"])
        yield from self.session_orchestrator.stream_turn(
            session=session,
            user_input=user_input,
            requested_client_id=requested_client_id,
        )

    def process_user_turn(self, user_input: str, *, requested_client_id: str | None = None, session_id: str | None = None) -> dict:
        events = list(self.stream_user_turn(user_input, requested_client_id=requested_client_id, session_id=session_id))
        final = next((event for event in reversed(events) if event["event_kind"] == "final"), None)
        handoff = next((event for event in reversed(events) if event["event_kind"] == "handoff"), None)
        state = self.inspect_state(session_id=session_id)
        foreground_id = state["session"]["foreground_client_id"] if state["session"] else None
        foreground = self.client_registry.get(foreground_id) if foreground_id else None
        return {
            "active_client_id": foreground_id,
            "active_client_name": foreground["display_name"] if foreground else None,
            "reply": final["payload"]["reply"] if final else "",
            "stream": events,
            "switch_decision": (final["payload"]["switch_decision"] if final else None) or (handoff["payload"] if handoff else None),
            "session": state["session"],
            "cache": final["payload"]["cache"] if final else {},
            "latency_ms": final["payload"]["latency_ms"] if final else None,
        }

    def inspect_state(self, *, session_id: str | None = None) -> dict:
        session = self.store.get_session(session_id) if session_id else self.client_session_manager.get_active()
        if not session:
            return {
                "clients": self.list_clients(),
                "session": None,
                "switches": [],
                "presentation_stream": [],
                "prewarm_jobs": [],
            }
        return {
            "clients": self.list_clients(),
            "session": session,
            "switches": self.store.list_switch_logs(session["id"], 10),
            "presentation_stream": self.store.list_session_events(session["id"], channel="presentation", limit=20),
            "prewarm_jobs": self.store.list_prewarm_jobs(session["id"], 10),
        }
