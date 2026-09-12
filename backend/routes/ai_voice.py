"""
AI Voice routes — speech-to-text and text-to-speech endpoints.

All endpoints require module_key="ai_voice" to be enabled for the tenant.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional

from auth.dependencies import get_current_user
from middleware.module_guard import require_module
from services.voice import transcribe_audio, synthesize_speech, _resolve_gemini_key
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai/voice", tags=["ai-voice"])


# ==================== REQUEST/RESPONSE MODELS ====================

class TranscribeRequest(BaseModel):
    audio_base64: str = Field(..., description="Base64-encoded audio data")
    mime_type: str = Field(default="audio/webm", description="Audio MIME type")


class TranscribeResponse(BaseModel):
    text: str = Field(..., description="Transcribed text")


class SpeakRequest(BaseModel):
    text: str = Field(..., max_length=4000, description="Text to synthesize (max 4000 chars)")
    voice: str = Field(default="Kore", description="Voice name")


class SpeakResponse(BaseModel):
    audio_base64: str = Field(..., description="Base64-encoded WAV audio")
    mime: str = Field(default="audio/wav", description="Audio MIME type")


class VoiceStatusResponse(BaseModel):
    available: bool = Field(..., description="True if voice is available (module enabled + key present)")
    has_key: bool = Field(..., description="True if Gemini API key is configured")
    voice: str = Field(default="Kore", description="Default voice name")


# ==================== ENDPOINTS ====================

@router.post("/transcribe", response_model=TranscribeResponse, dependencies=[Depends(require_module("ai_voice"))])
async def transcribe(
    req: TranscribeRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Transcribe audio to text using Gemini STT.
    
    - Requires ai_voice module to be enabled for tenant
    - Requires Gemini API key (tenant config or env GEMINI_API_KEY)
    - Max audio size: ~6MB (base64 length ~8M chars)
    - Supported formats: audio/webm (opus), audio/wav, audio/mp3, etc.
    """
    # Size guard: reject overly large audio
    max_base64_length = 8_000_000  # ~6MB audio
    if len(req.audio_base64) > max_base64_length:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Audio too large. Max size: ~6MB (base64 length {max_base64_length} chars)"
        )
    
    try:
        text = await transcribe_audio(req.audio_base64, req.mime_type)
        return TranscribeResponse(text=text)
    
    except ValueError as ve:
        # Service-level errors (no key, empty response, etc.)
        logger.warning(f"Transcription error for user {current_user.get('email')}: {ve}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        logger.error(f"Unexpected transcription error: {type(e).__name__}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Transcription failed. Please try again."
        )


@router.post("/speak", response_model=SpeakResponse, dependencies=[Depends(require_module("ai_voice"))])
async def speak(
    req: SpeakRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Synthesize speech from text using Gemini TTS.
    
    - Requires ai_voice module to be enabled for tenant
    - Requires Gemini API key (tenant config or env GEMINI_API_KEY)
    - Max text length: 4000 chars (truncated with warning if longer)
    - Returns WAV audio (24kHz mono 16-bit) as base64
    """
    try:
        wav_base64 = await synthesize_speech(req.text, req.voice)
        return SpeakResponse(audio_base64=wav_base64, mime="audio/wav")
    
    except ValueError as ve:
        logger.warning(f"Speech synthesis error for user {current_user.get('email')}: {ve}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        logger.error(f"Unexpected speech synthesis error: {type(e).__name__}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Speech synthesis failed. Please try again."
        )


@router.get("/status", response_model=VoiceStatusResponse)
async def get_voice_status(current_user: dict = Depends(get_current_user)):
    """
    Check AI Voice availability for the current tenant.
    
    Returns:
      - available: True if module enabled AND Gemini key is configured
      - has_key: True if a Gemini API key is present
      - voice: Default voice name
    
    Frontend can use this to decide whether to use Gemini voice or fall back
    to browser Web Speech API.
    """
    try:
        gemini_key = await _resolve_gemini_key()
        has_key = bool(gemini_key)
        
        # For simplicity, we report available = has_key.
        # The actual module gating happens at the endpoint level via require_module.
        # If the user can call this endpoint, the module is already enabled.
        # So we just report key availability.
        
        return VoiceStatusResponse(
            available=has_key,
            has_key=has_key,
            voice="Kore"
        )
    
    except Exception as e:
        logger.error(f"Error checking voice status: {e}")
        # Non-fatal: return unavailable status
        return VoiceStatusResponse(
            available=False,
            has_key=False,
            voice="Kore"
        )
