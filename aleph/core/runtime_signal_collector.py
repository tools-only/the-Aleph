from __future__ import annotations


class RuntimeSignalCollector:
    def __init__(self, store, telemetry_adapter=None) -> None:
        self.store = store
        self.telemetry_adapter = telemetry_adapter

    def collect(
        self,
        *,
        client_id: str,
        runtime_signals_patch: dict | None = None,
        agent_native_state_patch: dict | None = None,
    ) -> dict:
        updated = self.store.update_client_runtime_state(
            client_id,
            runtime_signals_patch=runtime_signals_patch or {},
            agent_native_state_patch=agent_native_state_patch or {},
        )
        if self.telemetry_adapter is not None:
            self.telemetry_adapter.record_signal(
                client_id=client_id,
                payload=updated["runtime_signals"],
            )
        return updated
