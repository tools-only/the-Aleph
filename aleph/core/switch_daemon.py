from __future__ import annotations

from datetime import datetime, timezone


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


class SwitchDaemon:
    def __init__(self, now=None) -> None:
        self.now = now or _utc_timestamp

    def decide(self, context: dict) -> dict:
        target_client = (
            self._find_target_by_id(context)
            or self._choose_client(context)
        )

        if not target_client:
            return {
                "approved": False,
                "explanation": "No suitable target client is available for handoff.",
                "handoff_summary": "",
            }

        current = context.get("current_client")
        if current and target_client["id"] == current["id"]:
            return {
                "approved": False,
                "explanation": f"{target_client['display_name']} already holds foreground control.",
                "handoff_summary": "",
            }

        handoff_summary = self._build_handoff_summary(context, target_client)
        return {
            "approved": True,
            "target_client_id": target_client["id"],
            "target_persona_id": target_client["persona_id"],
            "explanation": (
                f"{target_client['display_name']} takes foreground because "
                f"{self._explain_reason(context.get('reason'))}."
            ),
            "handoff_summary": handoff_summary,
            "decided_at": self.now(),
        }

    def _find_target_by_id(self, context: dict) -> dict | None:
        target_id = context.get("target_client_id") or context.get("target_persona_id")
        if not target_id:
            return None
        for client in context["clients"]:
            if client["id"] == target_id:
                return client
        return None

    def _choose_client(self, context: dict) -> dict | None:
        reason = (context.get("reason") or "").lower()
        current = context.get("current_client")
        candidates = [
            client
            for client in context["clients"]
            if not current or client["id"] != current["id"]
        ]

        def pick_by(predicate):
            return next((client for client in candidates if predicate(client)), None)

        if any(token in reason for token in ("authority", "permission", "decide", "拍板", "接管")):
            return pick_by(lambda client: "authority" in client["permissions"])
        if any(token in reason for token in ("memory", "history", "recall", "记忆")):
            return pick_by(lambda client: "memory" in client["specialties"])
        if any(token in reason for token in ("social", "relationship", "emotional", "关系", "情绪")):
            return pick_by(lambda client: "social" in client["specialties"])
        return candidates[0] if candidates else None

    def _explain_reason(self, reason: str | None) -> str:
        return reason or "the current situation called for a different perspective"

    def _build_handoff_summary(self, context: dict, target_client: dict) -> str:
        reality = context["reality"]
        inherited = " | ".join(
            (item.get("handoff_hint") or item["summary"])
            for item in reality["consequences"][:3]
        )
        open_loops = " | ".join(reality["thread"]["open_loops"][:3])
        parts = [
            f"Incoming client: {target_client['display_name']}",
            f"Scene: {reality['thread']['active_scene']}",
            f"Reality summary: {reality['thread']['summary']}",
        ]
        if inherited:
            parts.append(f"Inherited consequences: {inherited}")
        if open_loops:
            parts.append(f"Open loops: {open_loops}")
        if context.get("user_input"):
            parts.append(f"User turn to address: {context['user_input']}")
        return "\n".join(parts)

