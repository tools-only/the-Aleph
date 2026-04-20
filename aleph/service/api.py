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
    from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
    from fastapi.responses import JSONResponse, StreamingResponse
except ImportError:  # pragma: no cover - optional runtime dependency
    FastAPI = None
    HTTPException = Exception
    Request = object
    BackgroundTasks = object
    JSONResponse = None
    StreamingResponse = None
    WebSocket = object
    WebSocketDisconnect = Exception


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

    @app.on_event("startup")
    async def _bind_event_bus():
        app.state.engine.event_bus.bind_loop(asyncio.get_running_loop())

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

    def _run_turn(engine, session_id: str, input_text: str, requested_client_id: str | None):
        """Synchronous turn runner executed inside a background task thread."""
        engine.process_user_turn(
            input_text,
            requested_client_id=requested_client_id,
            session_id=session_id,
        )

    @app.post("/sessions/{session_id}/turns", status_code=202)
    async def submit_turn(session_id: str, payload: dict[str, Any], background_tasks: BackgroundTasks):
        state = app.state.engine.get_session_state(session_id)
        if not state["session"]:
            raise HTTPException(status_code=404, detail="session_not_found")
        background_tasks.add_task(
            _run_turn,
            app.state.engine,
            session_id,
            payload["input_text"],
            payload.get("requested_client_id"),
        )
        return {"session_id": session_id, "status": "processing"}

    @app.get("/sessions/{session_id}/context")
    async def get_session_context(session_id: str):
        state = app.state.engine.get_session_state(session_id)
        if not state["session"]:
            raise HTTPException(status_code=404, detail="session_not_found")
        return {"context": app.state.engine.get_context_snapshot(session_id)}

    def _apply_callback(engine, session_id: str, payload: dict):
        """Synchronous callback runner executed inside a background task thread."""
        engine.apply_agent_callback(session_id, payload)

    @app.post("/sessions/{session_id}/callback", status_code=202)
    async def agent_callback(session_id: str, payload: dict[str, Any], background_tasks: BackgroundTasks):
        state = app.state.engine.get_session_state(session_id)
        if not state["session"]:
            raise HTTPException(status_code=404, detail="session_not_found")
        background_tasks.add_task(_apply_callback, app.state.engine, session_id, payload)
        return {"session_id": session_id, "status": "accepted"}

    @app.get("/sessions/{session_id}/stream")
    async def stream_session(session_id: str, request: Request):
        state = app.state.engine.get_session_state(session_id)
        if not state["session"]:
            raise HTTPException(status_code=404, detail="session_not_found")

        queue = app.state.engine.event_bus.subscribe(session_id)

        async def event_generator():
            try:
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=30.0)
                        yield f"event: {event['event_kind']}\n"
                        yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                    except asyncio.TimeoutError:
                        yield ": keepalive\n\n"
            finally:
                app.state.engine.event_bus.close(session_id)

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    @app.websocket("/sessions/{session_id}/audio")
    async def websocket_audio(websocket: WebSocket, session_id: str):
        """
        WebSocket endpoint for Stage 2 bidirectional device audio streaming.

        Protocol:
          Device → Cloud:
            Binary frame: [session_id:4][client_id:4][timestamp:8][opus_frame:N]
          Cloud → Device:
            Binary frame: [audio_type:1][opus_frame:N]  (for TTS playback)

        TODO: Full implementation requires ASR/TTS services to be injected.
        For MVP, this skeleton demonstrates the wire protocol pattern.
        """
        state = app.state.engine.get_session_state(session_id)
        if not state["session"]:
            await websocket.close(code=4000, reason="session_not_found")
            return

        await websocket.accept()
        logger.info("websocket_audio_connected session=%s", session_id)

        try:
            while True:
                data = await websocket.receive_bytes()
                if len(data) < 16:
                    # Malformed frame: need at least header (4+4+8 bytes)
                    continue

                # Parse frame header
                # [session_id:4][client_id:4][timestamp:8]
                # import struct
                # session, client, ts = struct.unpack(">HHQ", data[:16])
                # opus_frame = data[16:]

                # TODO: Feed to AlephAudioAdapter.process_audio_stream()
                # TODO: Receive TTS OPUS frame
                # TODO: Send back via websocket.send_bytes()

                # For MVP: echo back a simple response
                logger.debug("websocket_audio_received session=%s bytes=%d", session_id, len(data))
                # Placeholder: send silence back
                await websocket.send_bytes(b"\x00" * 100)

        except WebSocketDisconnect:
            logger.info("websocket_audio_disconnected session=%s", session_id)
        except Exception as e:
            logger.exception("websocket_audio_error session=%s error=%s", session_id, str(e))
            await websocket.close(code=1000)

    return app
