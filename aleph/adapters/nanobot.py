from __future__ import annotations

from .base import BaseAgentAdapter


class NanobotAdapter(BaseAgentAdapter):
    kind = "nanobot"

    def invoke(self, context) -> dict:
        handler = context.adapter_handler
        if handler is None:
            raise RuntimeError(f"Client '{context.self.client_id}' has no nanobot-compatible handler.")
        return handler(context)

