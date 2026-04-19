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
    engine.bootstrap(initial_client_id="iris", title="Aleph Demo Session")
    return engine


def format_state(state: dict) -> str:
    session = state["session"]
    if not session:
        return "No active session."
    current = next(client for client in state["clients"] if client["id"] == session["foreground_client_id"])
    latest_switch = state["switches"][0] if state["switches"] else None
    cache_status = state["presentation_stream"][0]["payload"].get("cache") if state["presentation_stream"] and state["presentation_stream"][0]["event_kind"] == "final" else None
    return "\n".join(
        [
            f"Session: {session['title']} ({session['id']})",
            f"Foreground client: {current['display_name']} ({current['id']})",
            f"Memory epoch: {session['memory_epoch']} | Tool epoch: {session['tool_epoch']} | Policy epoch: {session['policy_epoch']}",
            (
                f"Latest switch: {latest_switch['from_client_id'] or 'none'} -> {latest_switch['to_client_id']} | {latest_switch['reason']}"
                if latest_switch
                else "Latest switch: none"
            ),
            f"Prewarm jobs: {len(state['prewarm_jobs'])}",
            f"Latest cache status: {cache_status or 'none'}",
        ]
    )
