from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, AsyncIterator

logger = logging.getLogger(__name__)


class AudioCodec(Enum):
    """Supported audio codec formats."""
    OPUS = "opus"
    PCM16 = "pcm16"


@dataclass
class AudioFrame:
    """A single audio frame emitted by a device or returned by TTS."""
    codec: AudioCodec
    sample_rate: int  # Hz
    channels: int
    bitrate: int  # bps (0 for uncompressed PCM)
    data: bytes


class ASRService(ABC):
    """Abstract Speech-to-Text service interface.

    Implementations receive a list of AudioFrame covering a complete utterance
    (as detected by VAD / silence boundary) and return the transcribed text.
    """

    @abstractmethod
    async def transcribe(self, frames: list[AudioFrame]) -> str:
        raise NotImplementedError


class TTSService(ABC):
    """Abstract Text-to-Speech service interface.

    Implementations return a list of AudioFrame (typically in the device's
    preferred codec) that collectively represent the synthesized utterance.
    """

    @abstractmethod
    async def synthesize(self, text: str) -> list[AudioFrame]:
        raise NotImplementedError


class MockASRService(ASRService):
    """Mock ASR returning a fixed string. Replace with a real backend."""

    def __init__(self, transcript: str = "[mock transcription]") -> None:
        self._transcript = transcript

    async def transcribe(self, frames: list[AudioFrame]) -> str:
        # TODO: Integrate real ASR (Google Cloud Speech, Whisper, etc.)
        total_bytes = sum(len(f.data) for f in frames)
        logger.debug("mock_asr_transcribe frames=%d bytes=%d", len(frames), total_bytes)
        return self._transcript


class MockTTSService(TTSService):
    """Mock TTS returning a single zero-filled OPUS placeholder frame."""

    async def synthesize(self, text: str) -> list[AudioFrame]:
        # TODO: Integrate real TTS (Google Cloud TTS, festival, etc.)
        logger.debug("mock_tts_synthesize chars=%d", len(text))
        return [
            AudioFrame(
                codec=AudioCodec.OPUS,
                sample_rate=16000,
                channels=1,
                bitrate=24000,
                data=b"\x00" * 100,
            )
        ]


class AlephAudioAdapter:
    """Bridges device audio frames to Aleph session orchestration.

    Flow (per utterance):
        device OPUS frames  →  end-of-utterance marker  →  ASR.transcribe
        transcribed text    →  engine.process_user_turn (in a worker thread
                                since the engine is synchronous)
        agent reply text    →  TTS.synthesize
        TTS frames          →  device playback
    """

    def __init__(
        self,
        engine: Any,
        asr_service: ASRService | None = None,
        tts_service: TTSService | None = None,
    ) -> None:
        self.engine = engine
        self.asr = asr_service or MockASRService()
        self.tts = tts_service or MockTTSService()

    async def process_frame_stream(
        self,
        session_id: str,
        device_id: str,
        frames: AsyncIterator[AudioFrame],
    ) -> AsyncIterator[AudioFrame]:
        """Consume an async stream of device audio frames and yield TTS frames.

        End-of-utterance is signaled explicitly by an `AudioFrame` with empty
        `data` (zero-length payload). This keeps the adapter codec-agnostic and
        avoids coupling utterance boundary detection to asyncio timing (which
        would risk tearing down the source async-iterator via cancellation).

        TODO: Add a real RMS/WebRTC-style VAD layer on top of this so devices
        can omit the explicit marker once PCM conversion is wired in.
        """
        utterance: list[AudioFrame] = []
        async for frame in frames:
            if not frame.data:
                # Explicit end-of-utterance marker.
                async for reply_frame in self._flush_utterance(session_id, utterance):
                    yield reply_frame
                utterance = []
                continue
            utterance.append(frame)

        # Source exhausted — flush any residual utterance.
        async for reply_frame in self._flush_utterance(session_id, utterance):
            yield reply_frame

    async def _flush_utterance(
        self,
        session_id: str,
        utterance: list[AudioFrame],
    ) -> AsyncIterator[AudioFrame]:
        if not utterance:
            return
        text = await self.asr.transcribe(utterance)
        if not text or not text.strip():
            return

        # engine.process_user_turn is synchronous; offload to a worker thread so
        # the event loop stays responsive for other WebSocket traffic.
        result = await asyncio.to_thread(
            self.engine.process_user_turn,
            text,
            session_id=session_id,
        )
        reply = (result or {}).get("reply", "")
        if not reply:
            return

        for frame in await self.tts.synthesize(reply):
            yield frame

    async def transcribe(self, frames: list[AudioFrame]) -> str:
        """Convenience wrapper around the configured ASR service."""
        return await self.asr.transcribe(frames)

    async def synthesize(self, text: str) -> list[AudioFrame]:
        """Convenience wrapper around the configured TTS service."""
        return await self.tts.synthesize(text)
