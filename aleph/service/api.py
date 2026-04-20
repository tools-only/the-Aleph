from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

from aleph.config import register_client_blueprints
from aleph.core.aleph_engine import AlephEngine
from aleph.personas.default_clients import build_default_clients
from aleph.service.logging import configure_logging

try:  # pragma: no cover - optional runtime dependency
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import JSONResponse, StreamingResponse
except ImportError:  # pragma: no cover - optional runtime dependency
    FastAPI = None
    HTTPException = Exception
    Request = object
    JSONResponse = None
    StreamingResponse = None


def _build_engine(root_dir: str | Path, client_config_path: str | Path | None = None) -> AlephEngine:
    root = Path(root_dir)
    root.mkdir(parents=True, exist_ok=True)
    engine = AlephEngine(root_dir=root)
    if client_config_path:
        register_client_blueprints(engine, client_config_path)
    else:
        for client in build_default_clients():
            engine.register_client(client)
    return engine


def create_app(*, root_dir: str | Path = ".", client_config_path: str | Path | None = None):
    if FastAPI is None:  # pragma: no cover - depends on optional dependency
        raise RuntimeError(
            "FastAPI is not installed. Install the 'service' extra to run the Aleph API service."
        )

    logger = configure_logging()
    app = FastAPI(title="Aleph API", version="0.1.0")
    app.state.engine = _build_engine(root_dir=root_dir, client_config_path=client_config_path)
    app.state.logger = logger

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("Unhandled service exception", extra={"path": request.url.path, "method": request.method})
            raise
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        logger.info(
            "request_complete method=%s path=%s status=%s duration_ms=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response

    @app.exception_handler(RuntimeError)
    async def handle_runtime_error(request: Request, exc: RuntimeError):
        logger.error("runtime_error path=%s error=%s", request.url.path, str(exc))
        return JSONResponse(status_code=400, content={"error": "runtime_error", "message": str(exc)})

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/clients")
    async def list_clients():
        return {"clients": app.state.engine.list_clients()}

    @app.get("/sessions")
    async def list_sessions(limit: int = 50):
        return {"sessions": app.state.engine.list_sessions(limit=limit)}

    @app.post("/sessions")
    async def create_session(payload: dict[str, Any] | None = None):
        payload = payload or {}
        state = app.state.engine.create_session(
            initial_client_id=payload.get("initial_client_id"),
            title=payload.get("title", "Aleph Session"),
            metadata=payload.get("metadata"),
        )
        return {"session": state["session"], "clients": state["clients"]}

    @app.get("/sessions/{session_id}")
    async def get_session(session_id: str):
        state = app.state.engine.get_session_state(session_id)
        if not state["session"]:
            raise HTTPException(status_code=404, detail="session_not_found")
        return state

    @app.post("/sessions/{session_id}/turns")
    async def submit_turn(session_id: str, payload: dict[str, Any]):
        state = app.state.engine.get_session_state(session_id)
        if not state["session"]:
            raise HTTPException(status_code=404, detail="session_not_found")
        result = app.state.engine.process_user_turn(
            payload["input_text"],
            requested_client_id=payload.get("requested_client_id"),
            session_id=session_id,
        )
        latest_stream = app.state.engine.store.list_session_events_after(
            session_id,
            channel="presentation",
            after_created_at=None,
            limit=10,
        )
        cursor = latest_stream[-1]["created_at"] if latest_stream else None
        return {
            "session_id": session_id,
            "accepted": True,
            "active_client_id": result["active_client_id"],
            "reply": result["reply"],
            "latency_ms": result["latency_ms"],
            "stream_cursor": cursor,
            "switch_decision": result["switch_decision"],
        }

    @app.get("/sessions/{session_id}/stream")
    async def stream_session(session_id: str, after: str | None = None, poll_interval_ms: int = 500):
        state = app.state.engine.get_session_state(session_id)
        if not state["session"]:
            raise HTTPException(status_code=404, detail="session_not_found")

        async def event_generator():
            cursor = after
            while True:
                events = app.state.engine.store.list_session_events_after(
                    session_id,
                    channel="presentation",
                    after_created_at=cursor,
                    limit=50,
                )
                for event in events:
                    cursor = event["created_at"]
                    yield f"event: {event['event_kind']}\n"
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                await asyncio.sleep(max(poll_interval_ms, 100) / 1000)

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    return app
