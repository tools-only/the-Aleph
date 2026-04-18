from __future__ import annotations


class ClientSessionManager:
    def __init__(self, store) -> None:
        self.store = store

    def start_foreground_session(
        self,
        *,
        thread_id: str,
        client_id: str,
        reason: str,
        handoff_summary: str = "",
    ) -> dict:
        session = self.store.create_client_session(
            {
                "client_id": client_id,
                "status": "foreground",
                "handoff_summary": handoff_summary,
            }
        )
        self.store.set_foreground_control(
            {
                "thread_id": thread_id,
                "client_id": client_id,
                "session_id": session["id"],
                "reason": reason,
            }
        )
        return session

    def get_foreground(self) -> dict | None:
        control = self.store.get_foreground_control()
        if not control:
            return None
        return control

    def record_user_turn(
        self,
        *,
        client_id: str,
        session_id: str,
        source_event_id: str,
        content: str,
    ) -> dict:
        return self.store.append_client_turn(
            {
                "client_id": client_id,
                "session_id": session_id,
                "role": "user",
                "content": content,
                "source_event_id": source_event_id,
                "visibility": "private",
            }
        )

    def record_assistant_turn(
        self,
        *,
        client_id: str,
        session_id: str,
        source_event_id: str,
        content: str,
        metadata: dict | None = None,
    ) -> dict:
        return self.store.append_client_turn(
            {
                "client_id": client_id,
                "session_id": session_id,
                "role": "assistant",
                "content": content,
                "source_event_id": source_event_id,
                "visibility": "private",
                "metadata": metadata or {},
            }
        )

    def list_recent_turns(self, client_id: str, limit: int = 8) -> list[dict]:
        return self.store.list_client_turns(client_id, limit)

