from __future__ import annotations

from hashlib import sha1

from .memory_manager import MemoryManager


class ProjectionCompiler:
    def __init__(self, store, memory_manager: MemoryManager) -> None:
        self.store = store
        self.memory_manager = memory_manager

    def compile(self, *, session: dict, client: dict, user_input: str) -> dict:
        prompt_projection, prompt_hit = self._compile_prompt(session=session, client=client, user_input=user_input)
        memory_projection, memory_hit = self._compile_memory(session=session, client=client)
        tool_projection, tool_hit = self._compile_tools(session=session, client=client)
        capability_projection, capability_hit = self._compile_capability(session=session, client=client)
        return {
            "prompt": prompt_projection,
            "memory": memory_projection,
            "tools": tool_projection,
            "capability": capability_projection,
            "cache": {
                "prompt_hit": prompt_hit,
                "memory_hit": memory_hit,
                "tool_hit": tool_hit,
                "capability_hit": capability_hit,
            },
        }

    def compile_handoff(
        self,
        *,
        session: dict,
        source_client: dict,
        target_client: dict,
        reason: str,
        user_input: str,
    ) -> dict:
        shared_entries = self.memory_manager.load_shared(session["id"], target_client)[:4]
        shared_facts = [entry["content"] for entry in shared_entries]
        summary = (
            f"Incoming client: {target_client['display_name']}\n"
            f"Reason: {reason}\n"
            f"User turn: {user_input}\n"
            f"Previous foreground: {source_client['display_name']}\n"
            f"Shared facts: {' | '.join(shared_facts) if shared_facts else 'none'}"
        )
        return {
            "from_client_id": source_client["id"],
            "to_client_id": target_client["id"],
            "reason": reason,
            "summary": summary,
            "shared_facts": shared_facts,
        }

    def prewarm_candidates(self, *, session: dict, candidates: list[dict], user_input: str, reason: str) -> None:
        for client in candidates[:2]:
            self.compile(session=session, client=client, user_input=user_input)
            self.store.create_prewarm_job(
                {
                    "session_id": session["id"],
                    "client_id": client["id"],
                    "reason": reason,
                    "status": "ready",
                    "payload": {
                        "budget_class": "lightweight",
                        "cancelable": True,
                        "side_effect_free": True,
                    },
                }
            )

    def _cache_fingerprint(self, *, session: dict, client: dict, projection_type: str, extra: str = "") -> tuple[str, dict]:
        envelope = {
            "session_id": session["id"],
            "client_id": client["id"],
            "memory_epoch": session["memory_epoch"],
            "tool_epoch": session["tool_epoch"],
            "policy_epoch": session["policy_epoch"],
            "client_blueprint_version": client["updated_at"],
        }
        raw = "|".join(str(value) for value in [projection_type, *envelope.values(), extra])
        return sha1(raw.encode("utf-8")).hexdigest(), envelope

    def _compile_prompt(self, *, session: dict, client: dict, user_input: str) -> tuple[dict, bool]:
        key, envelope = self._cache_fingerprint(
            session=session,
            client=client,
            projection_type="prompt",
            extra=user_input[:64],
        )
        cached = self.store.get_projection_cache(key)
        if cached:
            return cached["value"], True

        projection = {
            "system_summary": f"{client['display_name']} acts as {client['role']}.",
            "prompt_skeleton": client["system_prompt"],
            "runtime_overlay": {
                "boundaries": client["boundaries"],
                "user_input": user_input,
                "stream_mode": client["runtime_preferences"]["stream_mode"],
            },
        }
        self.store.save_projection_cache(
            {
                "cache_key": key,
                "projection_type": "prompt",
                "session_id": session["id"],
                "client_id": client["id"],
                "value": projection,
                "metadata": envelope,
            }
        )
        return projection, False

    def _compile_memory(self, *, session: dict, client: dict) -> tuple[dict, bool]:
        key, envelope = self._cache_fingerprint(session=session, client=client, projection_type="memory")
        cached = self.store.get_projection_cache(key)
        if cached:
            return cached["value"], True

        projection = {
            "private": self.memory_manager.load_private(session["id"], client),
            "shared": self.memory_manager.load_shared(session["id"], client),
            "handoff": self.memory_manager.load_handoff(session["id"], client),
        }
        self.store.save_projection_cache(
            {
                "cache_key": key,
                "projection_type": "memory",
                "session_id": session["id"],
                "client_id": client["id"],
                "value": projection,
                "metadata": envelope,
            }
        )
        return projection, False

    def _compile_tools(self, *, session: dict, client: dict) -> tuple[dict, bool]:
        key, envelope = self._cache_fingerprint(session=session, client=client, projection_type="tools")
        cached = self.store.get_projection_cache(key)
        if cached:
            return cached["value"], True

        projection = {
            "tool_surface": client["tools"],
            "tool_epoch": session["tool_epoch"],
        }
        self.store.save_projection_cache(
            {
                "cache_key": key,
                "projection_type": "tools",
                "session_id": session["id"],
                "client_id": client["id"],
                "value": projection,
                "metadata": envelope,
            }
        )
        return projection, False

    def _compile_capability(self, *, session: dict, client: dict) -> tuple[dict, bool]:
        key, envelope = self._cache_fingerprint(session=session, client=client, projection_type="capability")
        cached = self.store.get_projection_cache(key)
        if cached:
            return cached["value"], True

        projection = {
            "declared_capability": client["declared_capability"],
            "runtime_signals": client["instance"]["runtime_signals"],
        }
        self.store.save_projection_cache(
            {
                "cache_key": key,
                "projection_type": "capability",
                "session_id": session["id"],
                "client_id": client["id"],
                "value": projection,
                "metadata": envelope,
            }
        )
        return projection, False

