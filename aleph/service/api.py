from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

from aleph.adapters.audio_adapter import AlephAudioAdapter, AudioCodec, AudioFrame
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


def create_app(
    *,
    root_dir: str | Path = ".",
    client_config_path: str | Path | None = None,
    audio_adapter: AlephAudioAdapter | None = None,
):
    if FastAPI is None:  # pragma: no cover - depends on optional dependency
        raise RuntimeError(
            "FastAPI is not installed. Install the 'service' extra to run the Aleph API service."
        )

    logger = configure_logging()
    app = FastAPI(title="Aleph API", version="0.1.0")
    app.state.engine = _build_engine(root_dir=root_dir, client_config_path=client_config_path)
    app.state.logger = logger
    app.state.audio_adapter = audio_adapter or AlephAudioAdapter(app.state.engine)

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
        """Stage 2 bidirectional device audio streaming.

        Wire format (MVP):
          Upstream (device → cloud): binary frames, each body is one OPUS packet
            (16 kHz, mono, ~24 kbps). An empty binary frame (zero-length body)
            marks end-of-utterance and triggers ASR → agent turn → TTS.
          Downstream (cloud → device): binary frames, each body is one OPUS
            packet emitted by the TTS service for the agent's reply.

        TODO: Add optional metadata header (session_id / client_id / timestamp)
        once the C++ client is ready to emit it.
        """
        state = app.state.engine.get_session_state(session_id)
        if not state["session"]:
            # 1008 = policy violation (RFC 6455). Used for "session not found"
            # because the WebSocket handshake itself succeeded.
            await websocket.close(code=1008, reason="session_not_found")
            return

        await websocket.accept()
        logger.info("websocket_audio_connected session=%s", session_id)

        adapter: AlephAudioAdapter = app.state.audio_adapter
        device_id = websocket.headers.get("x-device-id", "unknown")

        async def _frame_source():
            while True:
                data = await websocket.receive_bytes()
                yield AudioFrame(
                    codec=AudioCodec.OPUS,
                    sample_rate=16000,
                    channels=1,
                    bitrate=24000,
                    data=data,
                )

        try:
            async for tts_frame in adapter.process_frame_stream(
                session_id=session_id,
                device_id=device_id,
                frames=_frame_source(),
            ):
                await websocket.send_bytes(tts_frame.data)
        except WebSocketDisconnect:
            logger.info("websocket_audio_disconnected session=%s", session_id)
        except Exception:
            logger.exception("websocket_audio_error session=%s", session_id)
            try:
                await websocket.close(code=1011)  # 1011 = internal error
            except Exception:  # pragma: no cover - connection may already be gone
                pass

    return app
