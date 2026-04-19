from __future__ import annotations


class MemoryManager:
    def __init__(self, store) -> None:
        self.store = store

    def load_private(self, session_id: str, client: dict) -> list[dict]:
        return self.store.list_memories(
            {
                "session_id": session_id,
                "layer": "private",
                "owner_client_id": client["id"],
                "limit": client["runtime_preferences"]["private_memory_window"],
            }
        )

    def load_shared(self, session_id: str, client: dict) -> list[dict]:
        return self.store.list_memories(
            {
                "session_id": session_id,
                "layer": "shared",
                "domains": client["shared_memory_policy"]["read_domains"],
                "limit": client["runtime_preferences"]["shared_memory_window"],
            }
        )

    def load_handoff(self, session_id: str, client: dict) -> list[dict]:
        return self.store.list_memories(
            {
                "session_id": session_id,
                "layer": "handoff",
                "owner_client_id": client["id"],
                "limit": client["runtime_preferences"]["handoff_window"],
            }
        )

    def persist_turn_output(self, *, session_id: str, client: dict, output: dict) -> None:
        for memory in output.get("private_memory_writes", []):
            self.store.save_memory(
                {
                    "session_id": session_id,
                    "layer": "private",
                    "owner_client_id": client["id"],
                    "kind": memory["kind"],
                    "content": memory["content"],
                    "metadata": memory.get("metadata", {}),
                }
            )

        shared_policy = client["shared_memory_policy"]
        for memory in output.get("shared_memory_writes", []):
            if memory["domain"] not in shared_policy["write_domains"]:
                raise PermissionError(
                    f"Client '{client['id']}' cannot write shared domain '{memory['domain']}'"
                )
            if memory["kind"] not in shared_policy["allowed_kinds"]:
                raise PermissionError(
                    f"Client '{client['id']}' cannot write shared kind '{memory['kind']}'"
                )
            self.store.save_memory(
                {
                    "session_id": session_id,
                    "layer": "shared",
                    "owner_client_id": client["id"],
                    "domain": memory["domain"],
                    "kind": memory["kind"],
                    "content": memory["content"],
                    "write_mode": memory.get("write_mode", shared_policy["write_mode"]),
                    "metadata": memory.get("metadata", {}),
                }
            )

        for memory in output.get("handoff_memory_writes", []):
            self.store.save_memory(
                {
                    "session_id": session_id,
                    "layer": "handoff",
                    "owner_client_id": memory.get("target_client_id") or client["id"],
                    "kind": memory["kind"],
                    "content": memory["content"],
                    "metadata": memory.get("metadata", {}),
                }
            )

        for note in output.get("runtime_notes", []):
            self.store.save_memory(
                {
                    "session_id": session_id,
                    "layer": "runtime",
                    "owner_client_id": client["id"],
                    "kind": note["kind"],
                    "content": note["content"],
                    "metadata": note.get("metadata", {}),
                }
            )
