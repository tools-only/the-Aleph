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
    def __init__(self, client: dict, private_entries: list[dict], shared_entries: list[dict]) -> None:
        self._client = client
        self.recent_private = private_entries
        self.recent_shared = shared_entries

    def get_private(self, query: str | None = None) -> list[dict]:
        return _filter_memory(self.recent_private, query)

    def get_shared(self, domain: str, query: str | None = None) -> list[dict]:
        readable = self._client["capabilities"]["readable_shared_domains"]
        if domain not in readable:
            raise PermissionError(
                f"Client '{self._client['id']}' cannot read shared domain '{domain}'"
            )
        scoped = [entry for entry in self.recent_shared if entry["domain"] == domain]
        return _filter_memory(scoped, query)


@dataclass
class ClientSelf:
    client_id: str
    persona_id: str
    display_name: str
    voice: str
    specialties: list[str]
    boundaries: list[str]
    permissions: list[str]
    shared_domains: list[str]


@dataclass
class ClientSessionState:
    session_id: str
    latest_handoff: dict | None


@dataclass
class ClientTurnState:
    user_input: str
    source_event_id: str


@dataclass
class ClientHistory:
    recent_turns: list[dict]


@dataclass
class ClientContext:
    self: ClientSelf
    session: ClientSessionState
    turn: ClientTurnState
    reality: dict
    history: ClientHistory
    memory: MemoryView
    actions: ClientTurnBuilder
    capabilities: dict


class ClientContextBuilder:
    def __init__(self, store, session_manager) -> None:
        self.store = store
        self.session_manager = session_manager

    def build(
        self,
        *,
        client: dict,
        thread_id: str,
        session_id: str,
        user_input: str,
        source_event_id: str,
        latest_handoff: dict | None,
    ) -> ClientContext:
        turn_builder = ClientTurnBuilder(client)
        reality = self.store.get_reality_projection(thread_id)
        isolation = client["isolation"]
        private_entries = self.store.list_memories(
            {
                "layer": "private",
                "persona_id": client["id"],
                "limit": isolation["private_memory_window"],
            }
        )
        shared_entries = self.store.list_memories(
            {
                "layer": "shared",
                "domains": client["capabilities"]["readable_shared_domains"],
                "limit": isolation["shared_memory_window"],
            }
        )
        recent_turns = self.session_manager.list_recent_turns(
            client["id"], isolation["transcript_window"]
        )

        trimmed_reality = {
            **reality,
            "consequences": reality["consequences"][: isolation["consequence_window"]],
        }

        return ClientContext(
            self=ClientSelf(
                client_id=client["id"],
                persona_id=client["persona_id"],
                display_name=client["display_name"],
                voice=client["voice"],
                specialties=client["specialties"],
                boundaries=client["boundaries"],
                permissions=client["permissions"],
                shared_domains=client["shared_domains"],
            ),
            session=ClientSessionState(session_id=session_id, latest_handoff=latest_handoff),
            turn=ClientTurnState(user_input=user_input, source_event_id=source_event_id),
            reality=trimmed_reality,
            history=ClientHistory(recent_turns=recent_turns),
            memory=MemoryView(client, private_entries, shared_entries),
            actions=turn_builder,
            capabilities=client["capabilities"],
        )

