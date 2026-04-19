from __future__ import annotations


def _contains_any(text: str, needles: list[str]) -> bool:
    lowered = text.lower()
    return any(needle.lower() in lowered for needle in needles)


def _summarize(entries: list[dict]) -> str:
    return " | ".join(item["content"] for item in entries[:2]) if entries else "none"


def _build_handlers() -> dict:
    def iris(context):
        text = context.turn.user_input
        private_notes = _summarize(context.memory.get_private())
        shared_commitments = _summarize(context.memory.get_shared("commitments"))
        handoff = _summarize(context.memory.get_handoff())

        turn = context.actions
        turn.reply(
            "Iris is holding the thread together. "
            f"Private continuity: {private_notes}. Shared commitments: {shared_commitments}. "
            f"Latest handoff: {handoff}."
        ).write_private(f"Iris logged the turn: {text}", "reflection").patch_agent_native_state(last_mode="archivist")

        if _contains_any(text, ["承诺", "commit", "deadline", "答应", "记住"]):
            turn.write_shared("commitments", f"Commitment registered: {text}", kind="commitment")
            turn.append_reply(" I have registered the commitment in shared memory.")

        if _contains_any(text, ["拍板", "决定", "执行", "推进", "take over"]):
            turn.request_switch(
                reason="decisive execution is needed",
                target_client_id="sol",
                urgency="high",
                replay_turn=True,
            )
        return turn.finish()

    def sol(context):
        text = context.turn.user_input
        commitments = _summarize(context.memory.get_shared("commitments"))
        handoff = _summarize(context.memory.get_handoff())

        turn = context.actions
        turn.reply(
            "Sol is in foreground for execution. "
            f"Active commitments: {commitments}. Handoff packet: {handoff}."
        ).write_private(f"Sol evaluated the task: {text}", "execution-note").emit_tool_event(
            "actions.reply",
            "completed",
            "Prepared an execution-oriented response.",
        ).patch_agent_native_state(last_mode="operator")

        if _contains_any(text, ["冲突", "关系", "误会", "情绪", "social"]):
            turn.request_switch(
                reason="relational repair is needed",
                target_client_id="mire",
                urgency="normal",
                replay_turn=True,
            )
        return turn.finish()

    def mire(context):
        text = context.turn.user_input
        social_notes = _summarize(context.memory.get_shared("social"))
        handoff = _summarize(context.memory.get_handoff())

        turn = context.actions
        turn.reply(
            "Mire is handling the relational surface. "
            f"Shared social residue: {social_notes}. Handoff packet: {handoff}."
        ).write_private(f"Mire read the interaction tone: {text}", "relational-trace").patch_agent_native_state(last_mode="relational")

        if _contains_any(text, ["关系", "误会", "情绪", "抱歉", "repair"]):
            turn.write_shared("social", f"Relational residue detected: {text}", kind="relationship")
            turn.append_reply(" I stored the social residue in shared memory so future clients do not erase it.")

        if _contains_any(text, ["决定", "执行", "推进", "authority"]):
            turn.request_switch(
                reason="execution authority is needed",
                target_client_id="sol",
                urgency="high",
                replay_turn=True,
            )
        return turn.finish()

    return {"iris": iris, "sol": sol, "mire": mire}


def build_default_clients() -> list[dict]:
    handlers = _build_handlers()
    return [
        {
            "id": "iris",
            "display_name": "Iris",
            "role": "continuity archivist",
            "adapter_kind": "nanobot",
            "system_prompt": "Preserve continuity, keep private notes separate, and hand off when execution pressure rises.",
            "boundaries": ["reflect before escalating", "do not fabricate shared consensus"],
            "declared_capability": {
                "domains": ["memory", "continuity", "commitments"],
                "permissions": ["curate", "summarize"],
                "handoff_keywords": ["记住", "commitment", "deadline", "执行", "推进"],
            },
            "shared_memory_policy": {
                "read_domains": ["commitments", "social"],
                "write_domains": ["commitments"],
                "allowed_kinds": ["commitment", "note", "fact"],
                "write_mode": "append",
            },
            "tools": [
                {"id": "actions.reply", "kind": "built-in"},
                {"id": "actions.request_switch", "kind": "built-in"},
                {"id": "memory.private", "kind": "built-in"},
                {"id": "memory.shared", "kind": "built-in"},
            ],
            "runtime_preferences": {
                "transcript_window": 8,
                "private_memory_window": 8,
                "shared_memory_window": 8,
                "handoff_window": 4,
                "stream_mode": "token-first",
            },
            "handler": handlers["iris"],
            "metadata": {"tagline": "Preserves continuity without collapsing everyone into one mind."},
        },
        {
            "id": "sol",
            "display_name": "Sol",
            "role": "execution operator",
            "adapter_kind": "nanobot",
            "system_prompt": "Drive execution, keep responses decisive, and request handoff when the task becomes relational.",
            "boundaries": ["prefer action over reflection", "do not write to social memory unless necessary"],
            "declared_capability": {
                "domains": ["execution", "authority", "closure"],
                "permissions": ["decide", "advance"],
                "handoff_keywords": ["执行", "推进", "拍板", "authority", "social"],
            },
            "shared_memory_policy": {
                "read_domains": ["commitments", "social"],
                "write_domains": ["commitments"],
                "allowed_kinds": ["commitment", "note", "fact"],
                "write_mode": "append",
            },
            "tools": [
                {"id": "actions.reply", "kind": "built-in"},
                {"id": "actions.request_switch", "kind": "built-in"},
                {"id": "memory.shared", "kind": "built-in"},
            ],
            "runtime_preferences": {
                "transcript_window": 8,
                "private_memory_window": 6,
                "shared_memory_window": 8,
                "handoff_window": 4,
                "stream_mode": "token-first",
            },
            "handler": handlers["sol"],
            "metadata": {"tagline": "Takes control when a client needs decisive execution."},
        },
        {
            "id": "mire",
            "display_name": "Mire",
            "role": "relational mediator",
            "adapter_kind": "nanobot",
            "system_prompt": "Handle social residue and interpersonal repair without flattening nuance.",
            "boundaries": ["preserve emotional context", "handoff when authority is required"],
            "declared_capability": {
                "domains": ["social", "repair", "relational"],
                "permissions": ["mediate", "repair"],
                "handoff_keywords": ["关系", "误会", "情绪", "repair", "authority"],
            },
            "shared_memory_policy": {
                "read_domains": ["social", "commitments"],
                "write_domains": ["social"],
                "allowed_kinds": ["relationship", "note", "fact"],
                "write_mode": "append",
            },
            "tools": [
                {"id": "actions.reply", "kind": "built-in"},
                {"id": "actions.request_switch", "kind": "built-in"},
                {"id": "memory.shared", "kind": "built-in"},
            ],
            "runtime_preferences": {
                "transcript_window": 8,
                "private_memory_window": 6,
                "shared_memory_window": 8,
                "handoff_window": 4,
                "stream_mode": "token-first",
            },
            "handler": handlers["mire"],
            "metadata": {"tagline": "Carries social residue forward so it cannot be silently erased."},
        },
    ]


def build_default_personas() -> list[dict]:
    return build_default_clients()
