"""AI provider helpers: OpenAI, Gemini, Emergent LLM, and app-wide AI config."""
import json
import os
import re
import logging
import uuid as uuid_module

from database import settings_collection, EMERGENT_LLM_KEY

logger = logging.getLogger(__name__)

# Gemini model name (env-overridable for future model upgrades).
# A short, ordered fallback list is tried if the primary 404s / is unavailable
# to the project — model availability on the Gemini API changes over time and
# differs per project, so we degrade gracefully instead of hard-failing.
GEMINI_TEXT_MODEL = os.environ.get("GEMINI_TEXT_MODEL", "gemini-flash-latest")
_GEMINI_MODEL_FALLBACKS = [
    GEMINI_TEXT_MODEL,
    "gemini-flash-latest",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
]
# Default Gemini key from env — used as a fallback across ALL AI features
# (chat, WBS, reschedule, voice) when a tenant hasn't set their own in Settings → AI.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")


async def get_ai_config() -> dict:
    """
    Get the app-wide AI configuration.
    Priority:
      1) Per-tenant/app settings from DB (Settings → AI)
      2) EMERGENT_LLM_KEY (if present, checked dynamically)
      3) Env GEMINI_API_KEY default (so a key set in backend .env works everywhere)
    """
    settings = await settings_collection.find_one({"type": "ai_config"})
    if settings and settings.get("ai_provider") and settings.get("ai_api_key"):
        return {"provider": settings["ai_provider"], "api_key": settings["ai_api_key"]}
    # Check EMERGENT_LLM_KEY dynamically from environment
    emergent_key = os.environ.get("EMERGENT_LLM_KEY", "")
    if emergent_key:
        return {"provider": "emergent", "api_key": emergent_key}
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
    """Call the Gemini (Google AI Studio) generateContent API.

    Resilient:
      - 45s timeout (report prompts are long; 15s caused silent timeouts).
      - Tries a short ordered list of model names, so if the configured model
        404s / is unavailable to the project, we fall through to a working one.
      - Logs the actual Gemini error (status + body) so prod logs show the real
        cause instead of a generic 'unable to process' message.

    Returns an httpx-like response object with .status_code / .json() / .text.
    """
    import httpx

    tried = []
    last_response = None
    # Per-attempt timeout (not a single long 45s) so the model-fallback loop
    # can't eat the whole export render budget if a model hangs. A healthy
    # Gemini call returns in 3-10s; this caps each attempt at 18s.
    async with httpx.AsyncClient(timeout=18.0) as client:
        for model in dict.fromkeys([m for m in _GEMINI_MODEL_FALLBACKS if m]):
            tried.append(model)
            try:
                response = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}",
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
            except httpx.TimeoutException:
                logger.warning(f"[Gemini] timeout on model={model}")
                last_response = type('obj', (object,), {'status_code': 408, 'text': 'Request timeout', 'json': lambda self=None: {}})()
                continue
            except Exception as e:
                logger.warning(f"[Gemini] request error on model={model}: {e}")
                last_response = type('obj', (object,), {'status_code': 500, 'text': str(e), 'json': lambda self=None: {}})()
                continue

            if response.status_code == 200:
                if model != GEMINI_TEXT_MODEL:
                    logger.info(f"[Gemini] used fallback model '{model}' (configured '{GEMINI_TEXT_MODEL}' unavailable)")
                return response

            # Non-200: log the real reason. 404/400 (bad/retired model) → try next.
            body = ""
            try:
                body = response.text[:300]
            except Exception:
                pass
            logger.warning(f"[Gemini] model={model} HTTP {response.status_code}: {body}")
            last_response = response
            if response.status_code in (400, 404):
                # Likely bad/unavailable model — try the next candidate.
                continue
            # Auth (401/403) or rate-limit (429) etc. — no point trying other models.
            return response

    logger.error(f"[Gemini] all model attempts failed ({tried})")
    return last_response or type('obj', (object,), {'status_code': 500, 'text': 'No Gemini response', 'json': lambda self=None: {}})()


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
