from __future__ import annotations

from copy import deepcopy


class ClientTurnBuilder:
    def __init__(self, client: dict) -> None:
        self.client = client
        self.output = {
            "reply": "",
            "private_memories": [],
            "shared_memories": [],
            "reality_updates": {
                "reality_notes": [],
                "consequences": [],
                "open_loops_to_add": [],
                "open_loops_to_resolve": [],
            },
            "switch_request": None,
            "audit_notes": [],
        }

    def reply(self, text: str) -> "ClientTurnBuilder":
        self.output["reply"] = text
        return self

    def append_reply(self, text: str) -> "ClientTurnBuilder":
        self.output["reply"] += text
        return self

    def write_private(
        self,
        content: str,
        kind: str = "note",
        metadata: dict | None = None,
    ) -> "ClientTurnBuilder":
        self.output["private_memories"].append(
            {"content": content, "kind": kind, "metadata": metadata or {}}
        )
        return self

    def write_shared(
        self,
        domain: str,
        content: str,
        kind: str = "note",
        metadata: dict | None = None,
    ) -> "ClientTurnBuilder":
        self.output["shared_memories"].append(
            {
                "domain": domain,
                "content": content,
                "kind": kind,
                "metadata": metadata or {},
            }
        )
        return self

    def note_reality(
        self,
        content: str,
        kind: str = "note",
        metadata: dict | None = None,
    ) -> "ClientTurnBuilder":
        self.output["reality_updates"]["reality_notes"].append(
            {"content": content, "kind": kind, "metadata": metadata or {}}
        )
        return self

    def add_open_loop(self, loop: str) -> "ClientTurnBuilder":
        self.output["reality_updates"]["open_loops_to_add"].append(loop)
        return self

    def resolve_open_loop(self, loop: str) -> "ClientTurnBuilder":
        self.output["reality_updates"]["open_loops_to_resolve"].append(loop)
        return self

    def upsert_consequence(self, **payload: object) -> "ClientTurnBuilder":
        self.output["reality_updates"]["consequences"].append({"op": "upsert", **payload})
        return self

    def resolve_consequence(self, kind_or_payload: str | dict) -> "ClientTurnBuilder":
        payload = {"kind": kind_or_payload} if isinstance(kind_or_payload, str) else dict(kind_or_payload)
        self.output["reality_updates"]["consequences"].append({"op": "resolve", **payload})
        return self

    def request_switch(
        self,
        *,
        reason: str,
        target_client_id: str | None = None,
        target_persona_id: str | None = None,
        urgency: str = "normal",
        replay_turn: bool = True,
    ) -> "ClientTurnBuilder":
        self.output["switch_request"] = {
            "target_client_id": target_client_id or target_persona_id,
            "reason": reason,
            "urgency": urgency,
            "replay_turn": replay_turn,
        }
        return self

    def audit(self, note: str) -> "ClientTurnBuilder":
        self.output["audit_notes"].append(note)
        return self

    def finish(self) -> dict:
        return deepcopy(self.output)

