"""
Voice service for AI Voice module.

Provides speech-to-text (transcription) and text-to-speech (synthesis) using
Gemini's audio APIs.

CRITICAL: Uses real Gemini API key only — Emergent LLM key NOT supported for audio.
"""
import httpx
import base64
import io
import os
import wave
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Model names (2026). Overridable via env so future model bumps need no code change.
# STT: dedicated transcription model. TTS: dedicated speech-generation model.
GEMINI_STT_MODEL = os.environ.get("GEMINI_STT_MODEL", "gemini-flash-latest")
GEMINI_TTS_MODEL = os.environ.get("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")


async def _resolve_gemini_key() -> Optional[str]:
    """
    Resolve Gemini API key for voice operations.
    
    Resolution order:
      1. Tenant AI config if provider=="gemini" and has api_key
      2. Environment variable GEMINI_API_KEY
      3. None (voice unavailable)
    
    CRITICAL: The Emergent LLM key MUST NOT be used for audio APIs.
    """
    from database import settings_collection, GEMINI_API_KEY
    
    # Try tenant AI config first
    settings = await settings_collection.find_one({"type": "ai_config"})
    if settings:
        provider = settings.get("ai_provider")
        api_key = settings.get("ai_api_key")
        if provider == "gemini" and api_key:
            return api_key
    
    # Fallback to environment variable
    if GEMINI_API_KEY:
        return GEMINI_API_KEY
    
    return None


async def transcribe_audio(audio_base64: str, mime_type: str) -> str:
    """
    Transcribe audio to text using Gemini STT.
    
    Args:
        audio_base64: Base64-encoded audio data
        mime_type: MIME type (e.g., "audio/webm", "audio/wav")
    
    Returns:
        Transcribed text
    
    Raises:
        ValueError: If no Gemini key available or transcription fails
    """
    gemini_key = await _resolve_gemini_key()
    if not gemini_key:
        raise ValueError("No Gemini API key configured for voice. Add one in Settings → AI or ask an admin.")
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_STT_MODEL}:generateContent"
    
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": "Transcribe this audio to plain text verbatim. Return only the transcription, no commentary."
                    },
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": audio_base64
                        }
                    }
                ]
            }
        ]
    }
    
    headers = {
        "x-goog-api-key": gemini_key,
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(url, json=payload, headers=headers)
            
            if response.status_code != 200:
                error_detail = response.text
                logger.error(f"Gemini STT error {response.status_code}: {error_detail}")
                raise ValueError(f"Gemini transcription failed: {error_detail}")
            
            result = response.json()
            # Robustly extract text: some models return multiple parts where
            # only one carries "text" (others may carry thoughtSignature only).
            text = ""
            try:
                parts = result["candidates"][0]["content"]["parts"]
                for p in parts:
                    if isinstance(p, dict) and p.get("text"):
                        text = p["text"]
                        break
            except (KeyError, IndexError, TypeError):
                text = ""

            if not text or not text.strip():
                raise ValueError("Transcription returned empty text")
            
            return text.strip()
        
        except httpx.TimeoutException:
            raise ValueError("Transcription request timed out")
        except KeyError as e:
            logger.error(f"Unexpected Gemini STT response structure: {e}")
            raise ValueError("Invalid transcription response format")
        except Exception as e:
            logger.error(f"Transcription error: {type(e).__name__}: {str(e)}")
            raise ValueError(f"Transcription failed: {str(e)}")


def _pcm_to_wav(pcm_bytes: bytes, sample_rate: int = 24000, channels: int = 1, sample_width: int = 2) -> bytes:
    """
    Wrap raw PCM audio in a WAV container.
    
    Gemini TTS returns raw PCM (16-bit signed little-endian mono 24kHz).
    Browsers need a proper WAV header to play it.
    
    Args:
        pcm_bytes: Raw PCM audio data
        sample_rate: Sample rate in Hz (24000 for Gemini)
        channels: Number of channels (1 for mono)
        sample_width: Bytes per sample (2 for 16-bit)
    
    Returns:
        Complete WAV file as bytes
    """
    wav_buffer = io.BytesIO()
    
    with wave.open(wav_buffer, 'wb') as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_bytes)
    
    wav_buffer.seek(0)
    return wav_buffer.read()


async def synthesize_speech(text: str, voice: str = "Kore") -> str:
    """
    Synthesize speech from text using Gemini TTS.
    
    Args:
        text: Text to speak (max ~4000 chars)
        voice: Voice name (default "Kore")
    
    Returns:
        Base64-encoded WAV audio file
    
    Raises:
        ValueError: If no Gemini key available or synthesis fails
    """
    gemini_key = await _resolve_gemini_key()
    if not gemini_key:
        raise ValueError("No Gemini API key configured for voice. Add one in Settings → AI or ask an admin.")
    
    # Truncate text if too long (polite)
    max_chars = 4000
    if len(text) > max_chars:
        text = text[:max_chars] + "... (truncated)"
        logger.warning(f"TTS text truncated to {max_chars} chars")
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_TTS_MODEL}:generateContent"
    
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": text
                    }
                ]
            }
        ],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {
                        "voiceName": voice
                    }
                }
            }
        }
    }
    
    headers = {
        "x-goog-api-key": gemini_key,
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(url, json=payload, headers=headers)
            
            if response.status_code != 200:
                error_detail = response.text
                logger.error(f"Gemini TTS error {response.status_code}: {error_detail}")
                raise ValueError(f"Gemini speech synthesis failed: {error_detail}")
            
            result = response.json()
            
            # Extract PCM audio base64
            pcm_base64 = result["candidates"][0]["content"]["parts"][0]["inlineData"]["data"]
            
            # Decode PCM
            pcm_bytes = base64.b64decode(pcm_base64)
            
            # Wrap in WAV container
            wav_bytes = _pcm_to_wav(pcm_bytes, sample_rate=24000, channels=1, sample_width=2)
            
            # Encode back to base64
            wav_base64 = base64.b64encode(wav_bytes).decode('utf-8')
            
            return wav_base64
        
        except httpx.TimeoutException:
            raise ValueError("Speech synthesis request timed out")
        except KeyError as e:
            logger.error(f"Unexpected Gemini TTS response structure: {e}")
            raise ValueError("Invalid synthesis response format")
        except Exception as e:
            logger.error(f"Speech synthesis error: {type(e).__name__}: {str(e)}")
            raise ValueError(f"Speech synthesis failed: {str(e)}")
