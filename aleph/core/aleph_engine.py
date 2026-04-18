from __future__ import annotations

from aleph.client.context_builder import ClientContextBuilder
from aleph.client.registry import ClientRegistry
from aleph.client.session_manager import ClientSessionManager
from aleph.core.switch_daemon import SwitchDaemon
from aleph.storage.sqlite_store import SqliteStore


class AlephEngine:
    def __init__(self, *, root_dir=None, store: SqliteStore | None = None, switch_daemon: SwitchDaemon | None = None) -> None:
        self.store = store or SqliteStore(root_dir=root_dir)
        self.switch_daemon = switch_daemon or SwitchDaemon()
        self.client_registry = ClientRegistry(self.store)
        self.client_session_manager = ClientSessionManager(self.store)
        self.client_context_builder = ClientContextBuilder(
            self.store, self.client_session_manager
        )

    def register_client(self, client_definition: dict) -> dict:
        return self.client_registry.register(client_definition)

    def register_persona(self, profile: dict, handler) -> dict:
        definition = dict(profile)
        definition["handler"] = handler
        return self.register_client(definition)

    def list_clients(self) -> list[dict]:
        return self.client_registry.list()

    def list_personas(self) -> list[dict]:
        return self.list_clients()

    def bootstrap(
        self,
        *,
        initial_client_id: str | None = None,
        initial_persona_id: str | None = None,
        title: str = "Aleph Reality Thread",
        summary: str = (
            "A single continuous reality is active. Different clients may take foreground, "
            "but reality keeps moving."
        ),
        active_scene: str = "A user has opened a new conversation with Aleph.",
        open_loops: list[str] | None = None,
    ) -> dict:
        thread = self.store.get_latest_reality_thread()
        if not thread:
            thread = self.store.create_reality_thread(
                {
                    "title": title,
                    "summary": summary,
                    "active_scene": active_scene,
                    "open_loops": open_loops or [],
                }
            )

        if not self.client_session_manager.get_foreground():
            target = initial_client_id or initial_persona_id
            if not target:
                clients = self.list_clients()
                if not clients:
                    raise RuntimeError("Cannot bootstrap Aleph without at least one registered client.")
                target = clients[0]["id"]
            self.client_session_manager.start_foreground_session(
                thread_id=thread["id"],
                client_id=target,
                reason="bootstrap",
                handoff_summary="Initial foreground client session.",
            )

        return self.inspect_state()

    def process_user_turn(self, user_input: str, *, requested_client_id: str | None = None, requested_persona_id: str | None = None) -> dict:
        foreground = self.client_session_manager.get_foreground()
        if not foreground:
            raise RuntimeError("Aleph is not bootstrapped.")

        requested = requested_client_id or requested_persona_id
        if requested and requested != foreground["client_id"]:
            self._switch_foreground(
                reason=f"user explicitly summoned {requested}",
                target_client_id=requested,
                trigger="user",
                user_input=user_input,
            )

        current = self.client_session_manager.get_foreground()
        event = self.store.append_reality_event(
            {
                "thread_id": current["thread_id"],
                "type": "user.turn",
                "source": "user",
                "summary": user_input,
                "payload": {"requested_client_id": requested},
            }
        )
        self.client_session_manager.record_user_turn(
            client_id=current["client_id"],
            session_id=current["session_id"],
            source_event_id=event["id"],
            content=user_input,
        )
        return self._run_client_turn(
            client_id=current["client_id"],
            session_id=current["session_id"],
            thread_id=current["thread_id"],
            user_input=user_input,
            source_event_id=event["id"],
            switch_budget=1,
        )

    def _run_client_turn(
        self,
        *,
        client_id: str,
        session_id: str,
        thread_id: str,
        user_input: str,
        source_event_id: str,
        switch_budget: int,
    ) -> dict:
        client = self.client_registry.get(client_id)
        if not client:
            raise RuntimeError(f"Client '{client_id}' is not registered.")
        handler = self.client_registry.get_handler(client_id)
        if not handler:
            raise RuntimeError(f"Client '{client_id}' has no registered handler.")

        window = client["isolation"]["handoff_window"]
        latest_handoff = self.store.list_switch_logs(window)[0] if self.store.list_switch_logs(window) else None
        context = self.client_context_builder.build(
            client=client,
            thread_id=thread_id,
            session_id=session_id,
            user_input=user_input,
            source_event_id=source_event_id,
            latest_handoff=latest_handoff,
        )
        output = handler(context)
        self._persist_client_output(client, session_id, thread_id, source_event_id, output)

        switch_request = output.get("switch_request")
        if switch_request and switch_budget > 0:
            decision = self._switch_foreground(
                reason=switch_request["reason"],
                target_client_id=switch_request.get("target_client_id"),
                trigger="daemon",
                user_input=user_input,
            )
            if decision["approved"] and switch_request.get("replay_turn", True):
                foreground = self.client_session_manager.get_foreground()
                next_result = self._run_client_turn(
                    client_id=foreground["client_id"],
                    session_id=foreground["session_id"],
                    thread_id=foreground["thread_id"],
                    user_input=user_input,
                    source_event_id=source_event_id,
                    switch_budget=0,
                )
                next_result["switch_decision"] = decision
                next_result["prior_client_id"] = client["id"]
                next_result["prior_persona_id"] = client["persona_id"]
                return next_result
            return {
                "active_client_id": client["id"],
                "active_client_name": client["display_name"],
                "active_persona_id": client["persona_id"],
                "active_persona_name": client["display_name"],
                "reply": output["reply"],
                "switch_decision": decision,
                "reality": self.store.get_reality_projection(thread_id),
            }

        return {
            "active_client_id": client["id"],
            "active_client_name": client["display_name"],
            "active_persona_id": client["persona_id"],
            "active_persona_name": client["display_name"],
            "reply": output["reply"],
            "reality": self.store.get_reality_projection(thread_id),
            "switch_decision": None,
        }

    def _persist_client_output(
        self,
        client: dict,
        session_id: str,
        thread_id: str,
        source_event_id: str,
        output: dict,
    ) -> None:
        for memory in output.get("private_memories", []):
            self.store.save_memory(
                {
                    "layer": "private",
                    "persona_id": client["id"],
                    "kind": memory["kind"],
                    "content": memory["content"],
                    "metadata": memory.get("metadata", {}),
                }
            )

        for memory in output.get("shared_memories", []):
            writable = client["capabilities"]["writable_shared_domains"]
            if memory["domain"] not in writable:
                continue
            self.store.save_memory(
                {
                    "layer": "shared",
                    "domain": memory["domain"],
                    "kind": memory["kind"],
                    "content": memory["content"],
                    "metadata": memory.get("metadata", {}),
                }
            )

        for note in output.get("reality_updates", {}).get("reality_notes", []):
            self.store.save_memory(
                {
                    "layer": "reality-note",
                    "kind": note.get("kind", "note"),
                    "content": note["content"],
                    "metadata": {"client_id": client["id"], **note.get("metadata", {})},
                }
            )

        projection = self.store.get_reality_projection(thread_id)
        open_loops = list(projection["thread"]["open_loops"])
        updates = output.get("reality_updates", {})

        for loop in updates.get("open_loops_to_add", []):
            if loop not in open_loops:
                open_loops.append(loop)
        for loop in updates.get("open_loops_to_resolve", []):
            if loop in open_loops:
                open_loops.remove(loop)
        if updates.get("open_loops_to_add") or updates.get("open_loops_to_resolve"):
            self.store.update_reality_thread(thread_id, {"open_loops": open_loops})

        for change in updates.get("consequences", []):
            if change["op"] == "resolve":
                self.store.resolve_consequence(
                    {
                        "thread_id": thread_id,
                        "kind": change.get("kind"),
                        "id": change.get("id"),
                    }
                )
            else:
                payload = dict(change)
                payload.pop("op", None)
                self.store.upsert_consequence(
                    {
                        "thread_id": thread_id,
                        "source_event_id": source_event_id,
                        "metadata": {"client_id": client["id"], **payload.get("metadata", {})},
                        **payload,
                    }
                )

        self.store.append_reality_event(
            {
                "thread_id": thread_id,
                "type": "client.turn",
                "source": client["id"],
                "summary": output["reply"],
                "payload": {
                    "client_id": client["id"],
                    "reply": output["reply"],
                    "requested_switch": output.get("switch_request"),
                },
            }
        )
        self.client_session_manager.record_assistant_turn(
            client_id=client["id"],
            session_id=session_id,
            source_event_id=source_event_id,
            content=output["reply"],
            metadata={"audit_notes": output.get("audit_notes", [])},
        )

        next_projection = self.store.get_reality_projection(thread_id)
        consequence = next_projection["consequences"][0]["summary"] if next_projection["consequences"] else None
        open_loop = next_projection["thread"]["open_loops"][0] if next_projection["thread"]["open_loops"] else None
        if consequence:
            summary = f"Foreground reality still carries: {consequence}"
        elif open_loop:
            summary = f"Foreground reality still carries the loop: {open_loop}"
        else:
            summary = "Foreground reality is stable for now."
        self.store.update_reality_thread(
            thread_id,
            {
                "summary": summary,
                "active_scene": f"Foreground client {client['display_name']} just responded to the user.",
                "metadata": {
                    "foreground_client_id": client["id"],
                    "foreground_persona_id": client["persona_id"],
                },
            },
        )

    def _switch_foreground(
        self,
        *,
        reason: str,
        target_client_id: str | None,
        trigger: str,
        user_input: str,
    ) -> dict:
        control = self.client_session_manager.get_foreground()
        reality = self.store.get_reality_projection(control["thread_id"])
        current_client = self.client_registry.get(control["client_id"])
        clients = self.client_registry.list()
        decision = self.switch_daemon.decide(
            {
                "reason": reason,
                "target_client_id": target_client_id,
                "current_client": current_client,
                "clients": clients,
                "reality": reality,
                "user_input": user_input,
            }
        )
        if not decision["approved"]:
            return decision

        next_client = self.client_registry.get(decision["target_client_id"])
        session = self.client_session_manager.start_foreground_session(
            thread_id=control["thread_id"],
            client_id=next_client["id"],
            reason=reason,
            handoff_summary=decision["handoff_summary"],
        )
        self.store.record_switch(
            {
                "from_client_id": current_client["id"] if current_client else None,
                "to_client_id": next_client["id"],
                "from_persona_id": current_client["persona_id"] if current_client else None,
                "to_persona_id": next_client["persona_id"],
                "reason": reason,
                "explanation": decision["explanation"],
                "handoff_summary": decision["handoff_summary"],
                "trigger": trigger,
            }
        )
        self.store.append_client_turn(
            {
                "client_id": next_client["id"],
                "session_id": session["id"],
                "role": "system",
                "content": decision["handoff_summary"],
                "visibility": "private",
                "metadata": {"kind": "handoff_summary"},
            }
        )
        return decision

    def inspect_state(self) -> dict:
        foreground = self.client_session_manager.get_foreground()
        if not foreground:
            empty = {
                "clients": self.list_clients(),
                "personas": self.list_clients(),
                "foreground": None,
                "reality": None,
                "switches": [],
            }
            return empty
        return {
            "clients": self.list_clients(),
            "personas": self.list_clients(),
            "foreground": foreground,
            "reality": self.store.get_reality_projection(foreground["thread_id"]),
            "switches": self.store.list_switch_logs(5),
        }

