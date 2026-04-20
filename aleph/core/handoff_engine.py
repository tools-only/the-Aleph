from __future__ import annotations

from aleph.domain import HandoffEnvelope


class HandoffEngine:
    def __init__(self, *, store, switch_daemon, compiler, registry, foreground_controller) -> None:
        self.store = store
        self.switch_daemon = switch_daemon
        self.compiler = compiler
        self.registry = registry
        self.foreground_controller = foreground_controller

    def decide(
        self,
        *,
        session: dict,
        current_client: dict,
        reason: str,
        trigger: str,
        user_input: str,
        target_client_id: str | None,
    ) -> dict:
        decision = self.switch_daemon.decide(
            {
                "reason": reason,
                "target_client_id": target_client_id,
                "current_client": current_client,
                "clients": self.registry.list(),
                "user_input": user_input,
            }
        )
        if not decision["approved"]:
            return decision

        target_client = self.registry.get(decision["target_client_id"])
        handoff = self.compiler.compile_handoff(
            session=session,
            source_client=current_client,
            target_client=target_client,
            reason=reason,
            user_input=user_input,
        )
        envelope = HandoffEnvelope(
            from_client_id=current_client["id"],
            to_client_id=target_client["id"],
            reason=reason,
            explanation=decision["explanation"],
            summary=handoff["summary"],
            shared_context_refs=handoff.get("shared_facts", []),
            created_at=self.store.now(),
        )
        self.store.save_memory(
            {
                "session_id": session["id"],
                "layer": "handoff",
                "owner_client_id": target_client["id"],
                "kind": "handoff_envelope",
                "content": envelope.summary,
                "metadata": envelope.to_dict(),
            }
        )
        self.store.record_switch(
            {
                "session_id": session["id"],
                "from_client_id": current_client["id"],
                "to_client_id": target_client["id"],
                "reason": reason,
                "trigger": trigger,
                "explanation": decision["explanation"],
                "handoff_summary": envelope.summary,
            }
        )
        self.foreground_controller.switch_foreground(
            session_id=session["id"],
            client_id=target_client["id"],
            reason=reason,
        )
        return {
            **decision,
            "handoff_summary": envelope.summary,
            "handoff_envelope": envelope.to_dict(),
        }
