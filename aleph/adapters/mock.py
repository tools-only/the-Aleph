from __future__ import annotations

from .base import BaseAgentAdapter


class MockAgentAdapter(BaseAgentAdapter):
    kind = "mock"

    def invoke(self, context) -> dict:
        handler = context.adapter_handler
        if handler is not None:
            return handler(context)

        prompt_summary = context.projections.prompt_projection["system_summary"]
        return (
            context.actions.reply(f"Mock adapter replied using compiled prompt: {prompt_summary}")
            .patch_runtime_signals(last_adapter="mock")
            .finish()
        )

