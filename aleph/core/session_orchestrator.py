from __future__ import annotations

from time import perf_counter

from aleph.client.context_builder import ClientContextBuilder


class SessionOrchestrator:
    def __init__(
        self,
        *,
        store,
        registry,
        session_manager,
        foreground_controller,
        compiler,
        memory_manager,
        handoff_engine,
        stream_emitter,
        runtime_signal_collector,
        adapter_factory,
    ) -> None:
        self.store = store
        self.registry = registry
        self.session_manager = session_manager
        self.foreground_controller = foreground_controller
        self.compiler = compiler
        self.memory_manager = memory_manager
        self.handoff_engine = handoff_engine
        self.stream_emitter = stream_emitter
        self.runtime_signal_collector = runtime_signal_collector
        self.adapter_factory = adapter_factory
        self.context_builder = ClientContextBuilder(store, session_manager)

    def ensure_session(self, *, initial_client_id: str, title: str = "Aleph Session") -> dict:
        return self.session_manager.ensure_session(initial_client_id=initial_client_id, title=title)

    def stream_turn(self, *, session: dict, user_input: str, requested_client_id: str | None = None, switch_budget: int = 1):
        current = self.registry.get(self.foreground_controller.get_foreground_client_id(session))
        if requested_client_id and requested_client_id != session["foreground_client_id"]:
            switch_decision = self._switch(
                session=session,
                current_client=current,
                reason=f"user requested {requested_client_id}",
                trigger="user",
                user_input=user_input,
                target_client_id=requested_client_id,
            )
            if switch_decision["approved"]:
                session = self.store.get_session(session["id"])
                current = self.registry.get(self.foreground_controller.get_foreground_client_id(session))
                yield self.stream_emitter.emit(
                    session_id=session["id"],
                    event_kind="handoff",
                    payload=switch_decision,
                    source="daemon",
                )

        source_event = self.store.append_session_event(
            {
                "session_id": session["id"],
                "channel": "internal",
                "event_kind": "turn.received",
                "source": "edge_gateway",
                "payload": {"user_input": user_input, "requested_client_id": requested_client_id},
            }
        )
        self.session_manager.record_user_turn(
            session_id=session["id"],
            client_id=current["id"],
            source_event_id=source_event["id"],
            content=user_input,
        )
        yield self.stream_emitter.emit(
            session_id=session["id"],
            event_kind="status",
            payload={"message": f"{current['display_name']} is compiling runtime context."},
            source=current["id"],
        )

        yield from self._run_client_turn(
            session=self.store.get_session(session["id"]),
            client=current,
            user_input=user_input,
            source_event_id=source_event["id"],
            switch_budget=switch_budget,
        )

    def _run_client_turn(self, *, session: dict, client: dict, user_input: str, source_event_id: str, switch_budget: int):
        self.store.append_session_event(
            {
                "session_id": session["id"],
                "channel": "internal",
                "event_kind": "compile.started",
                "source": client["id"],
                "payload": {"user_input": user_input},
            }
        )
        projection = self.compiler.compile(session=session, client=client, user_input=user_input)
        context = self.context_builder.build(
            client=client,
            session=session,
            source_event_id=source_event_id,
            user_input=user_input,
            projection=projection,
            adapter_handler=self.registry.get_handler(client["id"]),
        )
        adapter = self.adapter_factory(client["adapter_kind"])

        started = perf_counter()
        output = adapter.invoke(context)
        latency_ms = round((perf_counter() - started) * 1000, 2)
        runtime_signals_patch = {
            "last_latency_ms": latency_ms,
            "last_success": True,
            **output.get("runtime_signals_patch", {}),
        }

        self.memory_manager.persist_turn_output(session_id=session["id"], client=client, output=output)
        self.runtime_signal_collector.collect(
            client_id=client["id"],
            runtime_signals_patch=runtime_signals_patch,
            agent_native_state_patch=output.get("agent_native_state_patch", {}),
        )

        for tool_event in output.get("tool_events", []):
            yield self.stream_emitter.emit(
                session_id=session["id"],
                event_kind="tool_event",
                payload=tool_event,
                source=client["id"],
            )

        if output.get("reply"):
            self.session_manager.record_assistant_turn(
                session_id=session["id"],
                client_id=client["id"],
                source_event_id=source_event_id,
                content=output["reply"],
                metadata={"audit_notes": output.get("audit_notes", [])},
            )
            yield self.stream_emitter.emit(
                session_id=session["id"],
                event_kind="delta",
                payload={"text": output["reply"]},
                source=client["id"],
            )

        self._schedule_runtime_acceleration(session=session, client=client, user_input=user_input, output=output)

        switch_request = output.get("switch_request")
        switch_decision = None
        if switch_request and switch_budget > 0:
            switch_decision = self._switch(
                session=self.store.get_session(session["id"]),
                current_client=client,
                reason=switch_request["reason"],
                trigger="client",
                user_input=user_input,
                target_client_id=switch_request.get("target_client_id"),
            )
            if switch_decision["approved"]:
                yield self.stream_emitter.emit(
                    session_id=session["id"],
                    event_kind="handoff",
                    payload=switch_decision,
                    source="daemon",
                )
                if switch_request.get("replay_turn", True):
                    next_session = self.store.get_session(session["id"])
                    next_client = self.registry.get(self.foreground_controller.get_foreground_client_id(next_session))
                    yield self.stream_emitter.emit(
                        session_id=session["id"],
                        event_kind="status",
                        payload={"message": f"{next_client['display_name']} is taking over this turn."},
                        source="daemon",
                    )
                    yield from self._run_client_turn(
                        session=next_session,
                        client=next_client,
                        user_input=user_input,
                        source_event_id=source_event_id,
                        switch_budget=0,
                    )
                    return

        yield self.stream_emitter.emit(
            session_id=session["id"],
            event_kind="final",
            payload={
                "active_client_id": self.store.get_session(session["id"])["foreground_client_id"],
                "reply": output.get("reply", ""),
                "switch_decision": switch_decision,
                "cache": projection["cache"],
                "latency_ms": latency_ms,
            },
            source=client["id"],
        )

    def _switch(
        self,
        *,
        session: dict,
        current_client: dict,
        reason: str,
        trigger: str,
        user_input: str,
        target_client_id: str | None,
    ) -> dict:
        return self.handoff_engine.decide(
            session=session,
            current_client=current_client,
            reason=reason,
            trigger=trigger,
            user_input=user_input,
            target_client_id=target_client_id,
        )

    def _schedule_runtime_acceleration(self, *, session: dict, client: dict, user_input: str, output: dict) -> None:
        self.store.append_session_event(
            {
                "session_id": session["id"],
                "channel": "internal",
                "event_kind": "memory.maintenance_scheduled",
                "source": "aleph",
                "payload": {
                    "side_effect_free": True,
                    "cancelable": True,
                    "budget": "session-light",
                },
            }
        )

        candidates = [client] + [item for item in self.registry.list() if item["id"] != client["id"]]
        requested = (output.get("switch_request") or {}).get("target_client_id")
        if requested:
            candidates.sort(key=lambda item: 0 if item["id"] == requested else (1 if item["id"] == client["id"] else 2))
        self.compiler.prewarm_candidates(
            session=self.store.get_session(session["id"]),
            candidates=candidates,
            user_input=user_input,
            reason="candidate-client-prewarm",
        )
