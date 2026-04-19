from __future__ import annotations


class SwitchDaemon:
    def decide(self, context: dict) -> dict:
        target = self._find_target(context)
        current = context.get("current_client")

        if not target:
            return {
                "approved": False,
                "explanation": "No suitable target client is available for handoff.",
            }

        if current and target["id"] == current["id"]:
            return {
                "approved": False,
                "explanation": f"{target['display_name']} already owns foreground control.",
            }

        return {
            "approved": True,
            "target_client_id": target["id"],
            "explanation": (
                f"{target['display_name']} takes over because {self._normalize_reason(context.get('reason'))}."
            ),
        }

    def _find_target(self, context: dict) -> dict | None:
        explicit = context.get("target_client_id")
        if explicit:
            for client in context["clients"]:
                if client["id"] == explicit:
                    return client

        reason_text = f"{context.get('reason', '')} {context.get('user_input', '')}".lower()
        current = context.get("current_client")
        candidates = [
            client
            for client in context["clients"]
            if not current or client["id"] != current["id"]
        ]
        if not candidates:
            return None

        def score(client: dict) -> int:
            capability = client["declared_capability"]
            tags = []
            tags.extend(capability.get("domains", []))
            tags.extend(capability.get("permissions", []))
            tags.extend(capability.get("handoff_keywords", []))
            return sum(1 for tag in tags if str(tag).lower() in reason_text)

        ranked = sorted(candidates, key=score, reverse=True)
        return ranked[0]

    def _normalize_reason(self, reason: str | None) -> str:
        return reason or "the current client explicitly requested help"

