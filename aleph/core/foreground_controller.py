from __future__ import annotations


class ForegroundController:
    def __init__(self, session_manager) -> None:
        self.session_manager = session_manager

    def get_foreground_client_id(self, session: dict) -> str:
        return session["foreground_client_id"]

    def switch_foreground(self, *, session_id: str, client_id: str, reason: str) -> dict:
        return self.session_manager.set_foreground(
            session_id=session_id,
            client_id=client_id,
            reason=reason,
        )
