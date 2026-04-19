from __future__ import annotations


class EdgeGateway:
    def __init__(self, engine) -> None:
        self.engine = engine

    def submit_text(self, text: str, *, requested_client_id: str | None = None) -> list[dict]:
        return list(self.engine.stream_user_turn(text, requested_client_id=requested_client_id))

