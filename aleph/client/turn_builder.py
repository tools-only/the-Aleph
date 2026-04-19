from __future__ import annotations

from copy import deepcopy


class ClientTurnBuilder:
    def __init__(self, client: dict) -> None:
        self.client = client
        self.output = {
            "reply": "",
            "private_memory_writes": [],
            "shared_memory_writes": [],
            "handoff_memory_writes": [],
            "runtime_notes": [],
            "tool_events": [],
            "switch_request": None,
            "agent_native_state_patch": {},
            "runtime_signals_patch": {},
            "audit_notes": [],
        }

    def reply(self, text: str) -> "ClientTurnBuilder":
        self.output["reply"] = text
        return self

    def append_reply(self, text: str) -> "ClientTurnBuilder":
        self.output["reply"] += text
        return self

    def write_private(self, content: str, kind: str = "note", metadata: dict | None = None) -> "ClientTurnBuilder":
        self.output["private_memory_writes"].append(
            {"content": content, "kind": kind, "metadata": metadata or {}}
        )
        return self

    def write_shared(
        self,
        domain: str,
        content: str,
        kind: str = "note",
        write_mode: str = "append",
        metadata: dict | None = None,
    ) -> "ClientTurnBuilder":
        self.output["shared_memory_writes"].append(
            {
                "domain": domain,
                "content": content,
                "kind": kind,
                "write_mode": write_mode,
                "metadata": metadata or {},
            }
        )
        return self

    def write_handoff(
        self,
        content: str,
        *,
        target_client_id: str | None = None,
        kind: str = "handoff_note",
        metadata: dict | None = None,
    ) -> "ClientTurnBuilder":
        self.output["handoff_memory_writes"].append(
            {
                "content": content,
                "target_client_id": target_client_id,
                "kind": kind,
                "metadata": metadata or {},
            }
        )
        return self

    def runtime_note(self, content: str, kind: str = "note", metadata: dict | None = None) -> "ClientTurnBuilder":
        self.output["runtime_notes"].append(
            {"content": content, "kind": kind, "metadata": metadata or {}}
        )
        return self

    def emit_tool_event(
        self,
        tool_id: str,
        status: str,
        summary: str,
        metadata: dict | None = None,
    ) -> "ClientTurnBuilder":
        self.output["tool_events"].append(
            {
                "tool_id": tool_id,
                "status": status,
                "summary": summary,
                "metadata": metadata or {},
            }
        )
        return self

    def patch_agent_native_state(self, **patch: object) -> "ClientTurnBuilder":
        self.output["agent_native_state_patch"].update(patch)
        return self

    def patch_runtime_signals(self, **patch: object) -> "ClientTurnBuilder":
        self.output["runtime_signals_patch"].update(patch)
        return self

    def request_switch(
        self,
        *,
        reason: str,
        target_client_id: str | None = None,
        urgency: str = "normal",
        replay_turn: bool = True,
    ) -> "ClientTurnBuilder":
        self.output["switch_request"] = {
            "reason": reason,
            "target_client_id": target_client_id,
            "urgency": urgency,
            "replay_turn": replay_turn,
        }
        return self

    def audit(self, note: str) -> "ClientTurnBuilder":
        self.output["audit_notes"].append(note)
        return self

    def finish(self) -> dict:
        return deepcopy(self.output)

