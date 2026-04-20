from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, AsyncIterator


class AudioCodec(Enum):
    """Supported audio codec formats."""
    OPUS = "opus"


@dataclass
class AudioFrame:
    """Represents a single audio frame."""
    codec: AudioCodec
    sample_rate: int  # Hz
    channels: int
    bitrate: int  # bps
    data: bytes


class ASRService(ABC):
    """Abstract Speech-to-Text service interface."""

    @abstractmethod
    async def transcribe(self, audio_data: bytes, codec: AudioCodec, sample_rate: int) -> str:
        """Transcribe audio to text.

        Args:
            audio_data: Encoded audio bytes
            codec: Audio codec format
            sample_rate: Sample rate in Hz

        Returns:
            Transcribed text
        """
        raise NotImplementedError


class TTSService(ABC):
    """Abstract Text-to-Speech service interface."""

    @abstractmethod
    async def synthesize(self, text: str) -> bytes:
        """Synthesize text to audio.

        Args:
            text: Text to synthesize

        Returns:
            Audio bytes in OPUS format (16kHz, mono, 24kbps)
        """
        raise NotImplementedError


class MockASRService(ASRService):
    """Mock ASR for testing (returns fixed transcription)."""

    async def transcribe(self, audio_data: bytes, codec: AudioCodec, sample_rate: int) -> str:
        # TODO: Replace with real ASR service (Google Cloud Speech, Whisper, etc.)
        return "[mock transcription from audio]"


class MockTTSService(TTSService):
    """Mock TTS for testing (returns silence)."""

    async def synthesize(self, text: str) -> bytes:
        # TODO: Replace with real TTS service (Google Cloud TTS, festival, etc.)
        # For now, return 1 second of silence in OPUS format
        # In practice, this would be: OPUS encoder output at 16kHz, 24kbps, mono
        return b"\x00" * 100  # Placeholder


class AlephAudioAdapter:
    """
    Bridges device audio ↔ Aleph session orchestration.

    Device sends OPUS audio frames → ASR → text → Aleph turn processing.
    Aleph agent replies → TTS → OPUS audio frames → device playback.
    """

    def __init__(self, engine: Any, asr_service: ASRService | None = None, tts_service: TTSService | None = None):
        """
        Args:
            engine: AlephEngine instance for orchestration
            asr_service: Speech-to-text service (defaults to mock)
            tts_service: Text-to-speech service (defaults to mock)
        """
        self.engine = engine
        self.asr = asr_service or MockASRService()
        self.tts = tts_service or MockTTSService()

    async def process_audio_stream(
        self,
        session_id: str,
        device_id: str,
        audio_frames: AsyncIterator[AudioFrame],
    ) -> AsyncIterator[AudioFrame]:
        """
        Consume device audio frames, perform ASR, route to Aleph, yield TTS response.

        Args:
            session_id: Aleph session ID
            device_id: Device identifier (for logging/tracking)
            audio_frames: Async iterator of AudioFrame from device

        Yields:
            AudioFrame: OPUS audio for device playback (TTS response)
        """
        audio_buffer = bytearray()
        silence_duration = 0.0
        frame_duration = 0.02  # 20ms per frame at typical rate
        silence_threshold_ms = 500  # 500ms silence triggers ASR
        silence_threshold_frames = int(silence_threshold_ms / (frame_duration * 1000))

        try:
            async for frame in audio_frames:
                # Buffer incoming audio
                audio_buffer.extend(frame.data)

                # TODO: Implement proper silence detection (RMS-based)
                # For MVP, just trigger on buffer size or timeout
                if len(audio_buffer) > 20000:  # Roughly 500ms of OPUS
                    # Transcribe buffered audio
                    transcribed_text = await self.asr.transcribe(
                        bytes(audio_buffer),
                        frame.codec,
                        frame.sample_rate,
                    )
                    audio_buffer.clear()

                    if transcribed_text and transcribed_text.strip():
                        # Send turn to Aleph
                        result = self.engine.process_user_turn(
                            transcribed_text,
                            session_id=session_id,
                        )

                        # Extract reply from final event
                        reply = result.get("reply", "")

                        # Synthesize TTS audio
                        if reply:
                            tts_audio = await self.tts.synthesize(reply)

                            # Yield OPUS frame back to device
                            yield AudioFrame(
                                codec=AudioCodec.OPUS,
                                sample_rate=16000,
                                channels=1,
                                bitrate=24000,
                                data=tts_audio,
                            )

        except Exception as e:
            # TODO: Add proper error logging/handling
            print(f"Audio processing error for device {device_id}: {e}")
            raise

    async def transcribe_audio(self, audio_data: bytes, codec: AudioCodec, sample_rate: int) -> str:
        """Transcribe audio bytes to text.

        Args:
            audio_data: Encoded audio bytes
            codec: Audio codec format
            sample_rate: Sample rate in Hz

        Returns:
            Transcribed text
        """
        return await self.asr.transcribe(audio_data, codec, sample_rate)

    async def synthesize_speech(self, text: str) -> AudioFrame:
        """Synthesize text to OPUS audio.

        Args:
            text: Text to synthesize

        Returns:
            AudioFrame in OPUS format (16kHz, mono, 24kbps)
        """
        audio_data = await self.tts.synthesize(text)
        return AudioFrame(
            codec=AudioCodec.OPUS,
            sample_rate=16000,
            channels=1,
            bitrate=24000,
            data=audio_data,
        )

    def _estimate_silence_rms(self, pcm_data: bytes, threshold: int = 500) -> bool:
        """
        Simple RMS-based silence detection for PCM audio.

        TODO: Implement proper silence detection with RMS calculation.
        For MVP, this is a placeholder.

        Args:
            pcm_data: PCM audio bytes (16-bit samples)
            threshold: RMS threshold below which audio is considered silence

        Returns:
            True if audio is silent, False otherwise
        """
        # Placeholder: assume short buffers are silence
        if len(pcm_data) < 160:  # Less than 10ms
            return True
        return False
