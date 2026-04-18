from __future__ import annotations


def normalize_client_definition(client_definition: dict) -> dict:
    capabilities = client_definition.get("capabilities", {})
    shared_domains = client_definition.get("shared_domains", client_definition.get("sharedDomains", []))
    isolation = client_definition.get("isolation", {})

    return {
        "id": client_definition["id"],
        "persona_id": client_definition.get("persona_id", client_definition.get("personaId", client_definition["id"])),
        "display_name": client_definition.get(
            "display_name",
            client_definition.get("displayName", client_definition.get("name", client_definition["id"])),
        ),
        "name": client_definition.get(
            "name",
            client_definition.get("display_name", client_definition.get("displayName", client_definition["id"])),
        ),
        "voice": client_definition.get("voice", "neutral"),
        "specialties": client_definition.get("specialties", []),
        "boundaries": client_definition.get("boundaries", []),
        "permissions": client_definition.get("permissions", []),
        "shared_domains": shared_domains,
        "capabilities": {
            "readable_shared_domains": capabilities.get("readable_shared_domains", capabilities.get("readableSharedDomains", shared_domains)),
            "writable_shared_domains": capabilities.get("writable_shared_domains", capabilities.get("writableSharedDomains", shared_domains)),
            "allowed_actions": capabilities.get(
                "allowed_actions",
                capabilities.get(
                    "allowedActions",
                    [
                        "reply",
                        "write_private_memory",
                        "write_shared_memory",
                        "propose_reality_update",
                        "request_switch",
                    ],
                ),
            ),
            "request_only_actions": capabilities.get(
                "request_only_actions",
                capabilities.get(
                    "requestOnlyActions",
                    ["switch_foreground", "resolve_consequence", "write_reality_truth"],
                ),
            ),
            "allowed_tools": capabilities.get(
                "allowed_tools",
                capabilities.get(
                    "allowedTools",
                    ["memory.get_private", "memory.get_shared", "actions.reply", "actions.request_switch"],
                ),
            ),
        },
        "isolation": {
            "transcript_window": isolation.get("transcript_window", isolation.get("transcriptWindow", 8)),
            "private_memory_window": isolation.get("private_memory_window", isolation.get("privateMemoryWindow", 8)),
            "shared_memory_window": isolation.get("shared_memory_window", isolation.get("sharedMemoryWindow", 8)),
            "consequence_window": isolation.get("consequence_window", isolation.get("consequenceWindow", 6)),
            "handoff_window": isolation.get("handoff_window", isolation.get("handoffWindow", 3)),
        },
        "metadata": client_definition.get("metadata", {}),
        "handler": client_definition["handler"],
    }


class ClientRegistry:
    def __init__(self, store) -> None:
        self.store = store
        self._handlers: dict[str, object] = {}

    def register(self, client_definition: dict) -> dict:
        normalized = normalize_client_definition(client_definition)
        self.store.save_client_profile(normalized)
        self._handlers[normalized["id"]] = normalized["handler"]
        return normalized

    def get(self, client_id: str) -> dict | None:
        return self.store.get_client_profile(client_id)

    def list(self) -> list[dict]:
        return self.store.list_client_profiles()

    def get_handler(self, client_id: str):
        return self._handlers.get(client_id)

