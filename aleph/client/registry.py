from __future__ import annotations


def normalize_client_definition(client_definition: dict) -> dict:
    declared_capability = client_definition.get("declared_capability", {})
    if not declared_capability:
        declared_capability = {
            "domains": client_definition.get("specialties", []),
            "permissions": client_definition.get("permissions", []),
            "strength": client_definition.get("voice", "balanced"),
            "handoff_keywords": client_definition.get("handoff_keywords", []),
        }

    shared_policy = client_definition.get("shared_memory_policy", {})
    shared_domains = client_definition.get("shared_domains", [])
    if not shared_policy:
        shared_policy = {
            "read_domains": shared_domains,
            "write_domains": shared_domains,
            "allowed_kinds": ["note", "commitment", "relationship", "instruction", "fact"],
            "write_mode": "append",
        }

    tools = client_definition.get("tools")
    if tools is None:
        tools = [
            {"id": "actions.reply", "kind": "built-in"},
            {"id": "actions.request_switch", "kind": "built-in"},
            {"id": "memory.private", "kind": "built-in"},
            {"id": "memory.shared", "kind": "built-in"},
            {"id": "memory.handoff", "kind": "built-in"},
        ]

    handoff_rules = client_definition.get("handoff_rules", {})
    if not handoff_rules:
        handoff_rules = {
            "allow_user_direct_switch": True,
            "allow_client_request_switch": True,
            "rule_tags": client_definition.get("specialties", []),
        }

    runtime_preferences = client_definition.get("runtime_preferences", {})
    if not runtime_preferences:
        runtime_preferences = {
            "transcript_window": 8,
            "private_memory_window": 8,
            "shared_memory_window": 8,
            "handoff_window": 4,
            "stream_mode": "token-first",
        }

    normalized = {
        "id": client_definition["id"],
        "display_name": client_definition.get("display_name", client_definition.get("name", client_definition["id"])),
        "role": client_definition.get("role", client_definition.get("display_name", client_definition["id"])),
        "system_prompt": client_definition.get(
            "system_prompt",
            client_definition.get(
                "role_prompt",
                f"You are {client_definition.get('display_name', client_definition['id'])}. "
                "Stay within your capability profile and request handoff when needed.",
            ),
        ),
        "adapter_kind": client_definition.get("adapter_kind", "nanobot"),
        "boundaries": client_definition.get("boundaries", []),
        "declared_capability": declared_capability,
        "shared_memory_policy": shared_policy,
        "tools": tools,
        "handoff_rules": handoff_rules,
        "runtime_preferences": runtime_preferences,
        "metadata": client_definition.get("metadata", {}),
        "handler": client_definition.get("handler"),
    }
    return normalized


class ClientRegistry:
    def __init__(self, store) -> None:
        self.store = store
        self._handlers: dict[str, object] = {}

    def register(self, client_definition: dict) -> dict:
        normalized = normalize_client_definition(client_definition)
        stored = self.store.save_client_blueprint({key: value for key, value in normalized.items() if key != "handler"})
        self.store.save_client_instance(
            {
                "id": stored["id"],
                "blueprint_id": stored["id"],
                "adapter_kind": stored["adapter_kind"],
                "status": "ready",
                "runtime_signals": {},
                "agent_native_state": {},
                "metadata": {"registered_via": "aleph"},
            }
        )
        self._handlers[stored["id"]] = normalized.get("handler")
        return stored

    def get(self, client_id: str) -> dict | None:
        blueprint = self.store.get_client_blueprint(client_id)
        instance = self.store.get_client_instance(client_id)
        if not blueprint or not instance:
            return None
        return {**blueprint, "instance": instance}

    def list(self) -> list[dict]:
        return [self.get(item["id"]) for item in self.store.list_client_blueprints()]

    def get_handler(self, client_id: str):
        return self._handlers.get(client_id)

