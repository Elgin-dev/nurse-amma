import asyncio
import os

from app.services import speech_service
from app.services.speech_service import SpeechService
from app.services.nlp_extractor import NLPExtractor


def test_speech_service_empty_input():
    result = asyncio.run(
        SpeechService.transcribe_audio_chunk(b"", language="en")
    )

    assert result is None


def test_speech_service_valid_mock_audio(monkeypatch):
    """Test transcription deterministically without loading real Whisper."""
    mock_audio = b"fake_audio_binary_data"
    temporary_paths = []

    class FakeWhisperModel:
        def transcribe(self, audio_path, language="en"):
            temporary_paths.append(audio_path)

            assert language == "en"
            assert os.path.isfile(audio_path)

            with open(audio_path, "rb") as audio_file:
                assert audio_file.read() == mock_audio

            return {"text": "The patient feels feverish"}

    monkeypatch.setattr(
        speech_service,
        "_load_model",
        lambda: FakeWhisperModel(),
    )

    result = asyncio.run(
        SpeechService.transcribe_audio_chunk(
            mock_audio,
            language="en",
        )
    )

    assert result == "The patient feels feverish"
    assert len(temporary_paths) == 1
    assert not os.path.exists(temporary_paths[0])


def test_speech_service_missing_whisper_uses_fallback(monkeypatch):
    """An unavailable optional dependency should not crash the API."""

    def missing_whisper():
        raise ModuleNotFoundError(
            "No module named 'whisper'",
            name="whisper",
        )

    monkeypatch.setattr(
        speech_service,
        "_load_model",
        missing_whisper,
    )

    result = asyncio.run(
        SpeechService.transcribe_audio_chunk(
            b"synthetic audio bytes",
            language="en",
        )
    )

    assert result is None


def test_nlp_extractor_duration_and_severity():
    text = "I have had a severe fever for 3 days and bad headaches"

    details = NLPExtractor.extract_symptom_details(text)

    assert details.duration is not None
    assert details.duration.value == 3
    assert details.duration.unit.value == "days"
    assert details.severity == "severe"
