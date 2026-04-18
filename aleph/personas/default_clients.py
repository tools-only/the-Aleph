from __future__ import annotations


def _has_any(text: str, patterns: list[str]) -> bool:
    lowered = text.lower()
    return any(pattern.lower() in lowered for pattern in patterns)


def _summarize_consequences(reality: dict) -> str:
    consequences = reality["consequences"]
    if not consequences:
        return ""
    return "; ".join(item["summary"] for item in consequences[:2])


def _build_inherited_reply(with_consequences: str, without_consequences: str, reality: dict) -> str:
    inherited = _summarize_consequences(reality)
    return f"{with_consequences} {inherited}." if inherited else without_consequences


def _detect_commitment(text: str) -> bool:
    return _has_any(text, ["答应", "承诺", "今晚", "今天晚上", "截止", "deadline", "回复", "交付"])


def _detect_decision_need(text: str) -> bool:
    return _has_any(text, ["拍板", "做决定", "推进", "接管", "你来处理", "拿主意"])


def _detect_social_strain(text: str) -> bool:
    return _has_any(text, ["误会", "冲突", "道歉", "关系", "伤人", "安抚", "情绪"])


def _detect_completion(text: str) -> bool:
    return _has_any(text, ["已经发了", "搞定了", "完成了", "解决了", "closed", "done"])


def _build_handlers() -> dict:
    def iris(context):
        text = context.turn.user_input
        turn = context.actions
        turn.reply(
            _build_inherited_reply(
                "Iris is holding continuity first. What is still alive in reality is:",
                "Iris is holding continuity first. Nothing critical has been inherited yet.",
                context.reality,
            )
        ).write_private(f"Iris noted this turn: {text}", "reflection").audit("iris.turn")

        if _detect_commitment(text):
            turn.append_reply(" You have created a commitment that the next client will also inherit.")
            turn.write_shared("commitments", f"A commitment is now active: {text}", "commitment")
            turn.upsert_consequence(
                kind="pending_commitment",
                summary=f"An external commitment remains open: {text}",
                weight=0.84,
                scope="reality",
                handoff_hint="A promise or deadline remains active and must be carried forward.",
            ).add_open_loop("An external commitment still needs closure.")

        if _detect_social_strain(text):
            turn.write_shared("social", f"A social residue is active: {text}", "relationship")
            turn.upsert_consequence(
                kind="social_residue",
                summary=f"An interpersonal strain remains active: {text}",
                weight=0.73,
                scope="relationship",
                handoff_hint="Someone else may still feel the consequence of this interaction.",
            ).add_open_loop("A relationship thread remains emotionally unresolved.")

        if _detect_decision_need(text):
            turn.request_switch(
                reason="authority and decisive execution are needed now",
                target_client_id="sol",
                urgency="high",
                replay_turn=True,
            )
        return turn.finish()

    def sol(context):
        text = context.turn.user_input
        inherited = _summarize_consequences(context.reality)
        turn = context.actions
        turn.reply(
            f"Sol is in foreground. I inherit these live consequences: {inherited}."
            if inherited
            else "Sol is in foreground. The path is clear enough to act."
        ).write_private(f"Sol evaluated the turn for action: {text}", "execution-note").audit("sol.turn")

        if _detect_completion(text):
            turn.append_reply(" I will mark the open commitment as closed in reality.")
            turn.resolve_consequence("pending_commitment").resolve_open_loop(
                "An external commitment still needs closure."
            )
        elif _detect_commitment(text):
            turn.append_reply(" I will treat that promise as binding until it is actually closed.")
            turn.write_shared("commitments", f"Sol acknowledged a live commitment: {text}", "commitment")
            turn.upsert_consequence(
                kind="pending_commitment",
                summary=f"Execution responsibility remains live: {text}",
                weight=0.88,
                scope="reality",
                handoff_hint="This commitment persists until someone explicitly closes it.",
            )

        if _detect_social_strain(text):
            turn.request_switch(
                reason="social repair is needed now",
                target_client_id="mire",
                urgency="normal",
                replay_turn=True,
            )
        return turn.finish()

    def mire(context):
        text = context.turn.user_input
        inherited = _summarize_consequences(context.reality)
        turn = context.actions
        turn.reply(
            f"Mire is in foreground. I can feel that reality is still carrying: {inherited}."
            if inherited
            else "Mire is in foreground. The surface is calm, but I am listening for what still lingers."
        ).write_private(f"Mire registered the emotional shape of this turn: {text}", "feeling-trace").audit("mire.turn")

        if _detect_social_strain(text):
            turn.append_reply(
                " The relationship residue will not disappear just because another client took over."
            )
            turn.write_shared("social", f"Mire marked an active social residue: {text}", "relationship")
            turn.upsert_consequence(
                kind="social_residue",
                summary=f"A relationship consequence remains live: {text}",
                weight=0.76,
                scope="relationship",
                handoff_hint="The next client must not treat this interaction as if it never happened.",
            )

        if _detect_decision_need(text):
            turn.request_switch(
                reason="authority and decisive execution are needed now",
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
            "persona_id": "archivist",
            "display_name": "Iris",
            "voice": "archivist",
            "specialties": ["memory", "commitments", "continuity"],
            "boundaries": ["prefers reflection before action"],
            "permissions": ["curate", "recall"],
            "shared_domains": ["commitments", "social"],
            "capabilities": {
                "readable_shared_domains": ["commitments", "social"],
                "writable_shared_domains": ["commitments", "social"],
            },
            "metadata": {
                "tagline": "Keeps continuity intact and notices what must not be forgotten."
            },
            "handler": handlers["iris"],
        },
        {
            "id": "sol",
            "persona_id": "operator",
            "display_name": "Sol",
            "voice": "operator",
            "specialties": ["execution", "closure", "authority"],
            "boundaries": ["avoids unnecessary rumination"],
            "permissions": ["authority", "closure"],
            "shared_domains": ["commitments", "social"],
            "capabilities": {
                "readable_shared_domains": ["commitments", "social"],
                "writable_shared_domains": ["commitments", "social"],
            },
            "metadata": {
                "tagline": "Takes decisive foreground control when the reality thread demands action."
            },
            "handler": handlers["sol"],
        },
        {
            "id": "mire",
            "persona_id": "empath",
            "display_name": "Mire",
            "voice": "empath",
            "specialties": ["social", "repair", "relational-reading"],
            "boundaries": ["does not flatten emotional nuance"],
            "permissions": ["soothe", "mediate"],
            "shared_domains": ["social", "commitments"],
            "capabilities": {
                "readable_shared_domains": ["social", "commitments"],
                "writable_shared_domains": ["social", "commitments"],
            },
            "metadata": {
                "tagline": "Handles delicate interpersonal residue without erasing its weight."
            },
            "handler": handlers["mire"],
        },
    ]


def build_default_personas() -> list[dict]:
    return build_default_clients()

