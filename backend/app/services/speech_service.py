import logging
import os
import tempfile
from typing import Optional

from starlette.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)

# Load Whisper only when speech transcription is requested.
# This keeps the core FastAPI application usable without optional AI packages.
_model = None


def _load_model():
    """Load and cache the Whisper model on first use."""
    global _model

    if _model is None:
        import whisper

        _model = whisper.load_model("base")

    return _model


class SpeechService:
    @staticmethod
    async def transcribe_audio_chunk(
        audio_bytes: bytes,
        language: str = "en",
    ) -> Optional[str]:
        """Transcribe audio, returning None when transcription is unavailable."""
        if not audio_bytes:
            return None

        return await run_in_threadpool(
            _transcribe_audio_chunk_sync,
            audio_bytes,
            language,
        )


def _transcribe_audio_chunk_sync(
    audio_bytes: bytes,
    language: str = "en",
) -> Optional[str]:
    temp_path = None

    try:
        model = _load_model()

        # Save audio temporarily for Whisper processing.
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".wav",
        ) as temp_audio:
            temp_audio.write(audio_bytes)
            temp_path = temp_audio.name

        result = model.transcribe(temp_path, language=language)
        transcript = result.get("text", "").strip()

        return transcript or None

    except ModuleNotFoundError as exc:
        if exc.name == "whisper":
            logger.warning(
                "Whisper is not installed; speech transcription is unavailable."
            )
        else:
            logger.exception("A speech dependency is unavailable.")

        return None

    except Exception:
        logger.exception("Whisper speech processing failed.")
        return None

    finally:
        # Always attempt cleanup, even if model transcription fails.
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                logger.warning("Could not remove temporary audio file.")
