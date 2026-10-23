import pytest
from app.services.speech_service import SpeechService
from app.services.nlp_extractor import NLPExtractor


@pytest.mark.asyncio
async def test_speech_service_empty_input():
    result = await SpeechService.transcribe_audio_chunk(b"", language="en")
    assert result is None


@pytest.mark.asyncio
async def test_speech_service_valid_mock_audio():
    mock_audio = b"fake_audio_binary_data"
    result = await SpeechService.transcribe_audio_chunk(mock_audio, language="en")
    assert result is not None
    assert "feverish" in result.lower() or "patient" in result.lower()


def test_nlp_extractor_duration_and_severity():
    text = "I have had a severe fever for 3 days and bad headaches"
    details = NLPExtractor.extract_symptom_details(text)
    
    assert details.duration is not None
    assert details.duration.value == 3
    assert details.duration.unit.value == "days"
    assert details.severity == "severe"