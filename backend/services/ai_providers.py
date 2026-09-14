"""AI provider helpers: OpenAI, Gemini, Emergent LLM, and app-wide AI config."""
import json
import os
import re
import uuid as uuid_module

from database import settings_collection, EMERGENT_LLM_KEY

# Gemini model name (env-overridable for future model upgrades)
GEMINI_TEXT_MODEL = os.environ.get("GEMINI_TEXT_MODEL", "gemini-flash-latest")
# Default Gemini key from env — used as a fallback across ALL AI features
# (chat, WBS, reschedule, voice) when a tenant hasn't set their own in Settings → AI.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")


async def get_ai_config() -> dict:
    """
    Get the app-wide AI configuration.
    Priority:
      1) Per-tenant/app settings from DB (Settings → AI)
      2) EMERGENT_LLM_KEY (if present)
      3) Env GEMINI_API_KEY default (so a key set in backend .env works everywhere)
    """
    settings = await settings_collection.find_one({"type": "ai_config"})
    if settings and settings.get("ai_provider") and settings.get("ai_api_key"):
        return {"provider": settings["ai_provider"], "api_key": settings["ai_api_key"]}
    if EMERGENT_LLM_KEY:
        return {"provider": "emergent", "api_key": EMERGENT_LLM_KEY}
    if GEMINI_API_KEY:
        return {"provider": "gemini", "api_key": GEMINI_API_KEY}
    return {"provider": None, "api_key": None}


async def call_openai_api(api_key: str, system_prompt: str, user_message: str):
    """Helper function to call OpenAI API"""
    import httpx
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    "temperature": 0.3,
                    "response_format": {"type": "json_object"}
                }
            )
            return response
        except httpx.TimeoutException:
            return type('obj', (object,), {'status_code': 408, 'text': 'Request timeout'})()
        except Exception as e:
            return type('obj', (object,), {'status_code': 500, 'text': str(e)})()


async def call_gemini_api(api_key: str, system_prompt: str, user_message: str):
    """Helper function to call Gemini API"""
    import httpx
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_TEXT_MODEL}:generateContent?key={api_key}",
                headers={"Content-Type": "application/json"},
                json={
                    "contents": [{
                        "parts": [{
                            "text": f"{system_prompt}\n\n{user_message}\n\nRespond with valid JSON only."
                        }]
                    }],
                    "generationConfig": {
                        "temperature": 0.3,
                        "responseMimeType": "application/json"
                    }
                }
            )
            return response
        except httpx.TimeoutException:
            return type('obj', (object,), {'status_code': 408, 'text': 'Request timeout'})()
        except Exception as e:
            return type('obj', (object,), {'status_code': 500, 'text': str(e)})()


async def call_emergent_fallback(system_prompt: str, user_message: str):
    """Fallback using Emergent LLM integration"""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage

        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"ai-command-{uuid_module.uuid4()}",
            system_message=system_prompt
        ).with_model("openai", "gpt-4o-mini")

        user_msg = UserMessage(text=user_message + "\n\nRespond with valid JSON only, no markdown formatting.")
        response = await chat.send_message(user_msg)

        if isinstance(response, str):
            cleaned = re.sub(r'^```(?:json)?\s*', '', response.strip())
            cleaned = re.sub(r'\s*```$', '', cleaned)
            response = cleaned.strip()

        return json.loads(response)
    except Exception as e:
        print(f"Emergent fallback error: {type(e).__name__}: {str(e)}")
        return None


def extract_gemini_text(result: dict) -> str:
    """
    Robustly extract text from Gemini API response.
    Handles responses where some parts may only have thoughtSignature.
    Returns the first non-empty text part found.
    """
    try:
        parts = result.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        for part in parts:
            text = part.get("text", "").strip()
            if text:  # Return first non-empty text
                return text
        # If no text found, fall back to first part (original behavior)
        return parts[0].get("text", "") if parts else ""
    except (KeyError, IndexError, TypeError) as e:
        print(f"Gemini text extraction error: {e}")
        return ""
