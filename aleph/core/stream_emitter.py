from __future__ import annotations

from aleph.domain import StreamEvent


class StreamEmitter:
    def __init__(self, store, telemetry_adapter=None) -> None:
        self.store = store
        self.telemetry_adapter = telemetry_adapter

    def emit(
        self,
        *,
        session_id: str,
        event_kind: str,
        payload: dict,
        source: str,
        channel: str = "presentation",
    ) -> dict:
        record = self.store.append_session_event(
            {
                "session_id": session_id,
                "channel": channel,
                "event_kind": event_kind,
                "source": source,
                "payload": payload,
            }
        )
        event = StreamEvent(
            event_kind=event_kind,
            source=source,
            created_at=record["created_at"],
            payload=payload,
            channel=channel,
        )
        if self.telemetry_adapter is not None:
            self.telemetry_adapter.record_stream_event(event.to_dict())
        return event.to_dict()
