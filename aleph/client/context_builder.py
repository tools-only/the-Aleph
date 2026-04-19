from __future__ import annotations

from dataclasses import dataclass

from .turn_builder import ClientTurnBuilder


def _filter_memory(entries: list[dict], query: str | None) -> list[dict]:
    if not query:
        return entries
    needle = query.lower()
    return [
        entry
        for entry in entries
        if needle in f"{entry['kind']} {entry['content']}".lower()
    ]


class MemoryView:
    def __init__(self, client: dict, private_entries: list[dict], shared_entries: list[dict], handoff_entries: list[dict]) -> None:
        self._client = client
        self.recent_private = private_entries
        self.recent_shared = shared_entries
        self.recent_handoff = handoff_entries

    def get_private(self, query: str | None = None) -> list[dict]:
        return _filter_memory(self.recent_private, query)

    def get_shared(self, domain: str, query: str | None = None) -> list[dict]:
        readable = self._client["shared_memory_policy"]["read_domains"]
        if domain not in readable:
            raise PermissionError(
                f"Client '{self._client['id']}' cannot read shared domain '{domain}'"
            )
        scoped = [entry for entry in self.recent_shared if entry["domain"] == domain]
        return _filter_memory(scoped, query)

    def get_handoff(self, query: str | None = None) -> list[dict]:
        return _filter_memory(self.recent_handoff, query)


@dataclass
class ClientSelf:
    client_id: str
    display_name: str
    role: str
    boundaries: list[str]


@dataclass
class SessionState:
    session_id: str
    title: str
    foreground_client_id: str


@dataclass
class TurnState:
    user_input: str
    source_event_id: str


@dataclass
class HistoryState:
    recent_turns: list[dict]
    recent_stream: list[dict]


@dataclass
class ProjectionState:
    prompt_projection: dict
    memory_projection: dict
    tool_projection: dict
    capability_projection: dict
    cache_status: dict


@dataclass
class ClientContext:
    self: ClientSelf
    session: SessionState
    turn: TurnState
    history: HistoryState
    memory: MemoryView
    projections: ProjectionState
    runtime_signals: dict
    agent_native_state: dict
    adapter_handler: object
    actions: ClientTurnBuilder


class ClientContextBuilder:
    def __init__(self, store, session_manager) -> None:
        self.store = store
        self.session_manager = session_manager

    def build(
        self,
        *,
        client: dict,
        session: dict,
        source_event_id: str,
        user_input: str,
        projection: dict,
        adapter_handler,
    ) -> ClientContext:
        runtime_preferences = client["runtime_preferences"]
        recent_turns = self.session_manager.list_recent_turns(
            session["id"],
            client_id=client["id"],
            limit=runtime_preferences["transcript_window"],
        )
        recent_stream = self.store.list_session_events(
            session["id"],
            channel="presentation",
            limit=10,
        )
        memory_projection = projection["memory"]
        return ClientContext(
            self=ClientSelf(
                client_id=client["id"],
                display_name=client["display_name"],
                role=client["role"],
                boundaries=client["boundaries"],
            ),
            session=SessionState(
                session_id=session["id"],
                title=session["title"],
                foreground_client_id=session["foreground_client_id"],
            ),
            turn=TurnState(user_input=user_input, source_event_id=source_event_id),
            history=HistoryState(recent_turns=recent_turns, recent_stream=recent_stream),
            memory=MemoryView(
                client,
                memory_projection["private"],
                memory_projection["shared"],
                memory_projection["handoff"],
            ),
            projections=ProjectionState(
                prompt_projection=projection["prompt"],
                memory_projection=projection["memory"],
                tool_projection=projection["tools"],
                capability_projection=projection["capability"],
                cache_status=projection["cache"],
            ),
            runtime_signals=client["instance"]["runtime_signals"],
            agent_native_state=client["instance"]["agent_native_state"],
            adapter_handler=adapter_handler,
            actions=ClientTurnBuilder(client),
        )

