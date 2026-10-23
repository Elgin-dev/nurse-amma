import logging
from typing import Optional
import whisper
import tempfile
import os

logger = logging.getLogger(__name__)

# Load model once during server startup (use 'tiny' or 'base' for fast local performance)
model = whisper.load_model("base")

class SpeechService:
    @staticmethod
    async def transcribe_audio_chunk(
        audio_bytes: bytes, language: str = "en"
    ) -> Optional[str]:
        try:
            if not audio_bytes:
                return None

            # Save incoming audio stream to temporary file for Whisper processing
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_audio:
                temp_audio.write(audio_bytes)
                temp_path = temp_audio.name

            # Transcribe audio using Whisper
            result = model.transcribe(temp_path, language=language)
            
            # Clean up temporary file
            os.remove(temp_path)

            return result.get("text", "").strip()

        except Exception as e:
            logger.error(f"Whisper speech processing error: {e}")
            return None