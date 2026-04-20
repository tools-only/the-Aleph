from __future__ import annotations


class ClientSessionManager:
    def __init__(self, store) -> None:
        self.store = store

    def create_session(self, *, initial_client_id: str, title: str = "Aleph Session", metadata: dict | None = None) -> dict:
        return self.store.create_session(
            {
                "title": title,
                "foreground_client_id": initial_client_id,
                "foreground_reason": "bootstrap",
                "metadata": metadata or {},
            }
        )

    def ensure_session(self, *, initial_client_id: str, title: str = "Aleph Session") -> dict:
        existing = self.store.get_latest_session()
        if existing:
            return existing
        return self.create_session(initial_client_id=initial_client_id, title=title)

    def get_active(self) -> dict | None:
        return self.store.get_latest_session()

    def get_session(self, session_id: str) -> dict | None:
        return self.store.get_session(session_id)

    def list_sessions(self, limit: int = 50) -> list[dict]:
        return self.store.list_sessions(limit=limit)

    def set_foreground(self, *, session_id: str, client_id: str, reason: str) -> dict:
        return self.store.set_foreground_client(session_id, client_id, reason)

    def record_user_turn(self, *, session_id: str, client_id: str, source_event_id: str, content: str) -> dict:
        return self.store.append_session_turn(
            {
                "session_id": session_id,
                "client_id": client_id,
                "role": "user",
                "content": content,
                "source_event_id": source_event_id,
                "visibility": "private",
            }
        )

    def record_assistant_turn(
        self,
        *,
        session_id: str,
        client_id: str,
        source_event_id: str,
        content: str,
        metadata: dict | None = None,
    ) -> dict:
        return self.store.append_session_turn(
            {
                "session_id": session_id,
                "client_id": client_id,
                "role": "assistant",
                "content": content,
                "source_event_id": source_event_id,
                "visibility": "private",
                "metadata": metadata or {},
            }
        )

    def list_recent_turns(self, session_id: str, *, client_id: str | None = None, limit: int = 8) -> list[dict]:
        return self.store.list_session_turns(session_id, client_id=client_id, limit=limit)
