from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aleph.adapters import (
    AlephAudioAdapter,
    ASRService,
    AudioCodec,
    AudioFrame,
    MockASRService,
    MockTTSService,
    TTSService,
)


class RecordingASR(ASRService):
    def __init__(self, transcript: str) -> None:
        self.transcript = transcript
        self.received_frames: list[list[AudioFrame]] = []

    async def transcribe(self, frames: list[AudioFrame]) -> str:
        self.received_frames.append(list(frames))
        return self.transcript


class RecordingTTS(TTSService):
    def __init__(self) -> None:
        self.received_texts: list[str] = []

    async def synthesize(self, text: str) -> list[AudioFrame]:
        self.received_texts.append(text)
        return [
            AudioFrame(
                codec=AudioCodec.OPUS,
                sample_rate=16000,
                channels=1,
                bitrate=24000,
                data=b"\x01\x02\x03",
            )
        ]


class AudioAdapterConstructionTests(unittest.TestCase):
    def test_default_services_are_mocks(self) -> None:
        engine = MagicMock()
        adapter = AlephAudioAdapter(engine)
        self.assertIsInstance(adapter.asr, MockASRService)
        self.assertIsInstance(adapter.tts, MockTTSService)
        self.assertIs(adapter.engine, engine)

    def test_custom_services_override_defaults(self) -> None:
        engine = MagicMock()
        asr = RecordingASR("hello")
        tts = RecordingTTS()
        adapter = AlephAudioAdapter(engine, asr_service=asr, tts_service=tts)
        self.assertIs(adapter.asr, asr)
        self.assertIs(adapter.tts, tts)


class AudioAdapterFlushTests(unittest.IsolatedAsyncioTestCase):
    """Exercise the utterance boundary path directly without timing."""

    async def test_flush_calls_asr_engine_and_tts(self) -> None:
        engine = MagicMock()
        engine.process_user_turn.return_value = {"reply": "hi there"}
        asr = RecordingASR("hello world")
        tts = RecordingTTS()
        adapter = AlephAudioAdapter(engine, asr_service=asr, tts_service=tts)

        utterance = [
            AudioFrame(AudioCodec.OPUS, 16000, 1, 24000, b"\xaa"),
            AudioFrame(AudioCodec.OPUS, 16000, 1, 24000, b"\xbb"),
        ]

        result = [frame async for frame in adapter._flush_utterance("sess-1", utterance)]

        self.assertEqual(len(asr.received_frames), 1)
        self.assertEqual(len(asr.received_frames[0]), 2)
        engine.process_user_turn.assert_called_once_with("hello world", session_id="sess-1")
        self.assertEqual(tts.received_texts, ["hi there"])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].codec, AudioCodec.OPUS)
        self.assertEqual(result[0].data, b"\x01\x02\x03")

    async def test_flush_noop_when_utterance_empty(self) -> None:
        engine = MagicMock()
        adapter = AlephAudioAdapter(engine, asr_service=RecordingASR("x"), tts_service=RecordingTTS())

        result = [frame async for frame in adapter._flush_utterance("sess", [])]

        self.assertEqual(result, [])
        engine.process_user_turn.assert_not_called()

    async def test_flush_skips_empty_transcription(self) -> None:
        engine = MagicMock()
        adapter = AlephAudioAdapter(
            engine,
            asr_service=RecordingASR("   "),
            tts_service=RecordingTTS(),
        )

        frames = [AudioFrame(AudioCodec.OPUS, 16000, 1, 24000, b"\x00")]
        result = [f async for f in adapter._flush_utterance("sess", frames)]

        self.assertEqual(result, [])
        engine.process_user_turn.assert_not_called()

    async def test_flush_skips_empty_reply(self) -> None:
        engine = MagicMock()
        engine.process_user_turn.return_value = {"reply": ""}
        tts = RecordingTTS()
        adapter = AlephAudioAdapter(
            engine,
            asr_service=RecordingASR("hello"),
            tts_service=tts,
        )

        frames = [AudioFrame(AudioCodec.OPUS, 16000, 1, 24000, b"\x00")]
        result = [f async for f in adapter._flush_utterance("sess", frames)]

        self.assertEqual(result, [])
        self.assertEqual(tts.received_texts, [])


class AudioAdapterStreamTests(unittest.IsolatedAsyncioTestCase):
    async def test_stream_emits_tts_after_source_ends(self) -> None:
        engine = MagicMock()
        engine.process_user_turn.return_value = {"reply": "got it"}
        asr = RecordingASR("heard you")
        tts = RecordingTTS()
        adapter = AlephAudioAdapter(engine, asr_service=asr, tts_service=tts)

        async def frame_source():
            yield AudioFrame(AudioCodec.OPUS, 16000, 1, 24000, b"\x10")
            yield AudioFrame(AudioCodec.OPUS, 16000, 1, 24000, b"\x20")
            # Source ends -> remaining utterance is flushed.

        result = [
            frame
            async for frame in adapter.process_frame_stream(
                session_id="sess-9",
                device_id="dev-1",
                frames=frame_source(),
            )
        ]

        engine.process_user_turn.assert_called_once_with("heard you", session_id="sess-9")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].data, b"\x01\x02\x03")

    async def test_empty_frame_marks_end_of_utterance(self) -> None:
        engine = MagicMock()
        engine.process_user_turn.side_effect = [
            {"reply": "reply one"},
            {"reply": "reply two"},
        ]
        asr = RecordingASR("heard first")
        tts = RecordingTTS()
        adapter = AlephAudioAdapter(engine, asr_service=asr, tts_service=tts)

        async def frame_source():
            # First utterance — two frames, then EOU marker.
            yield AudioFrame(AudioCodec.OPUS, 16000, 1, 24000, b"\xaa")
            yield AudioFrame(AudioCodec.OPUS, 16000, 1, 24000, b"\xbb")
            yield AudioFrame(AudioCodec.OPUS, 16000, 1, 24000, b"")
            # Second utterance — one frame, then source ends (implicit flush).
            yield AudioFrame(AudioCodec.OPUS, 16000, 1, 24000, b"\xcc")

        result = [
            frame
            async for frame in adapter.process_frame_stream(
                session_id="sess-10",
                device_id="dev-2",
                frames=frame_source(),
            )
        ]

        # Two separate utterances → two engine calls, two TTS responses.
        self.assertEqual(engine.process_user_turn.call_count, 2)
        self.assertEqual(len(asr.received_frames), 2)
        self.assertEqual(len(asr.received_frames[0]), 2)
        self.assertEqual(len(asr.received_frames[1]), 1)
        self.assertEqual(len(result), 2)


if __name__ == "__main__":
    unittest.main()
