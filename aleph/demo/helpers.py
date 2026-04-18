from __future__ import annotations

from pathlib import Path

from aleph.core.aleph_engine import AlephEngine
from aleph.personas.default_clients import build_default_clients
from aleph.storage.sqlite_store import SqliteStore


def create_engine(root_dir: str | Path) -> AlephEngine:
    root = Path(root_dir)
    root.joinpath("data").mkdir(parents=True, exist_ok=True)
    store = SqliteStore(root_dir=root, db_path=":memory:")
    engine = AlephEngine(root_dir=root, store=store)
    for client in build_default_clients():
        engine.register_client(client)
    engine.bootstrap(
        initial_client_id="iris",
        title="Aleph Demo Thread",
        summary="A single reality is active. Clients may change, but consequences remain.",
        active_scene="The user has entered a fragile situation that may require a handoff.",
    )
    return engine


def format_state(state: dict) -> str:
    foreground = state["foreground"]
    current_client = next(
        (client for client in state["clients"] if foreground and client["id"] == foreground["client_id"]),
        None,
    )
    latest_switch = state["switches"][0] if state["switches"] else None
    consequences = " | ".join(item["summary"] for item in state["reality"]["consequences"]) if state["reality"] else "none"
    open_loops = " | ".join(state["reality"]["thread"]["open_loops"]) if state["reality"] else "none"
    return "\n".join(
        [
            f"Foreground: {current_client['display_name'] if current_client else 'none'} ({foreground['client_id'] if foreground else 'n/a'})",
            f"Scene: {state['reality']['thread']['active_scene'] if state['reality'] else 'n/a'}",
            f"Summary: {state['reality']['thread']['summary'] if state['reality'] else 'n/a'}",
            f"Open loops: {open_loops or 'none'}",
            f"Consequences: {consequences or 'none'}",
            (
                f"Latest switch: {latest_switch['from_client_id'] or 'none'} -> "
                f"{latest_switch['to_client_id']} ({latest_switch['reason']})"
                if latest_switch
                else "Latest switch: none"
            ),
        ]
    )
