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
    "gemini-flash-latest",       # self-updating alias → always current flash
    "gemini-3.8-flash",          # current stable flash (verified available)
    "gemini-3.5-flash",          # prior stable flash
    "gemini-flash-lite-latest",  # lightweight alias fallback
]
# Default Gemini key from env — used as a fallback across ALL AI features
# (chat, WBS, reschedule, voice) when a tenant hasn't set their own in Settings → AI.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Default Bedrock model — a current Claude inference profile, admin-editable.
BEDROCK_DEFAULT_MODEL = os.environ.get(
    "BEDROCK_DEFAULT_MODEL", "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
)
BEDROCK_DEFAULT_REGION = os.environ.get("BEDROCK_DEFAULT_REGION", "us-east-1")


async def get_ai_config() -> dict:
    """
    Get the app-wide AI configuration.
    Priority:
      1) Per-tenant/app settings from DB (Settings → AI)
      2) EMERGENT_LLM_KEY (if present, checked dynamically)
      3) Env GEMINI_API_KEY default (so a key set in backend .env works everywhere)

    For Bedrock the returned dict also includes `region` and `model`.
    """
    settings = await settings_collection.find_one({"type": "ai_config"})
    if settings and settings.get("ai_provider") and settings.get("ai_api_key"):
        cfg = {"provider": settings["ai_provider"], "api_key": settings["ai_api_key"]}
        if settings["ai_provider"] == "bedrock":
            cfg["region"] = settings.get("bedrock_region") or BEDROCK_DEFAULT_REGION
            cfg["model"] = settings.get("bedrock_model") or BEDROCK_DEFAULT_MODEL
        return cfg
    # Check EMERGENT_LLM_KEY dynamically from environment
    emergent_key = os.environ.get("EMERGENT_LLM_KEY", "")
    if emergent_key:
        return {"provider": "emergent", "api_key": emergent_key}
    if GEMINI_API_KEY:
        return {"provider": "gemini", "api_key": GEMINI_API_KEY}
    return {"provider": None, "api_key": None}


async def call_bedrock_api(api_key: str, system_prompt: str, user_message: str,
                           json_mode: bool = True, region: str = None, model: str = None):
    """Call Amazon Bedrock via the Converse API using an API-key bearer token.

    Returns an httpx-like response object whose .json() is OpenAI-SHAPED
    ({"choices":[{"message":{"content": <text>}}]}) so existing openai-style
    parsing works unchanged, plus .status_code and .text for error handling.

    json_mode=True appends a 'JSON only' instruction (Converse has no strict JSON
    mode) mirroring the Gemini helper.
    """
    import httpx

    region = region or BEDROCK_DEFAULT_REGION
    model = model or BEDROCK_DEFAULT_MODEL
    user_text = user_message + ("\n\nRespond with valid JSON only, no markdown." if json_mode else "")

    url = f"https://bedrock-runtime.{region}.amazonaws.com/model/{model}/converse"
    body = {
        "messages": [{"role": "user", "content": [{"text": user_text}]}],
        "inferenceConfig": {"temperature": 0.3, "maxTokens": 4096},
    }
    if system_prompt:
        body["system"] = [{"text": system_prompt}]

    def _resp(status, text_val):
        return type("obj", (object,), {
            "status_code": status,
            "text": text_val,
            "json": (lambda self=None, _t=text_val: {"choices": [{"message": {"content": _t}}]}),
        })()

    async with httpx.AsyncClient(timeout=45.0) as client:
        try:
            response = await client.post(
                url,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=body,
            )
        except httpx.TimeoutException:
            return type("obj", (object,), {"status_code": 408, "text": "Bedrock request timed out",
                                           "json": lambda self=None: {}})()
        except Exception as e:
            return type("obj", (object,), {"status_code": 500, "text": f"Bedrock request error: {e}",
                                           "json": lambda self=None: {}})()

        if response.status_code == 200:
            try:
                data = response.json()
                parts = data.get("output", {}).get("message", {}).get("content", [])
                text_out = ""
                for p in parts:
                    if p.get("text"):
                        text_out += p["text"]
                return _resp(200, text_out)
            except Exception as e:
                logger.error(f"[Bedrock] parse error: {e}")
                return type("obj", (object,), {"status_code": 500, "text": f"Bedrock parse error: {e}",
                                               "json": lambda self=None: {}})()

        # Non-200 — surface the real reason.
        body_txt = ""
        try:
            body_txt = response.text[:400]
        except Exception:
            pass
        logger.warning(f"[Bedrock] model={model} region={region} HTTP {response.status_code}: {body_txt}")
        return type("obj", (object,), {"status_code": response.status_code,
                                       "text": body_txt or f"Bedrock HTTP {response.status_code}",
                                       "json": lambda self=None: {}})()


def extract_bedrock_text(response) -> str:
    """Extract text from a call_bedrock_api response (OpenAI-shaped)."""
    try:
        return response.json()["choices"][0]["message"]["content"] or ""
    except Exception:
        return ""


async def call_openai_api(api_key: str, system_prompt: str, user_message: str, json_mode: bool = True):
    """Helper function to call OpenAI API.

    json_mode=True (default): forces a JSON object response — used by the
      structured endpoints (command parsing, WBS generation, analyses, etc.).
    json_mode=False: free-form text — used by the conversational CHAT endpoint,
      which returns natural language (optionally with a fenced ```action``` block).
      Forcing json_object there would corrupt the reply.
    """
    import httpx
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            payload = {
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                "temperature": 0.3,
            }
            if json_mode:
                payload["response_format"] = {"type": "json_object"}
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json=payload
            )
            return response
        except httpx.TimeoutException:
            return type('obj', (object,), {'status_code': 408, 'text': 'Request timeout'})()
        except Exception as e:
            return type('obj', (object,), {'status_code': 500, 'text': str(e)})()


async def call_gemini_api(api_key: str, system_prompt: str, user_message: str, json_mode: bool = True):
    """Call the Gemini (Google AI Studio) generateContent API.

    Resilient:
      - 45s timeout (report prompts are long; 15s caused silent timeouts).
      - Tries a short ordered list of model names, so if the configured model
        404s / is unavailable to the project, we fall through to a working one.
      - Logs the actual Gemini error (status + body) so prod logs show the real
        cause instead of a generic 'unable to process' message.

    json_mode=True (default): forces `responseMimeType=application/json` and asks
      for JSON only — used by the structured endpoints (command parsing, WBS
      generation, analyses, retrospectives, etc.).
    json_mode=False: free-form text — used by the conversational CHAT endpoint.
      Forcing JSON there makes Gemini return a JSON blob (or empty/invalid text),
      which is why chat failed when a tenant used a Gemini key. In text mode we
      omit responseMimeType and the 'JSON only' instruction so Gemini returns a
      normal conversational reply (optionally with a fenced ```action``` block).

    Returns an httpx-like response object with .status_code / .json() / .text.
    """
    import httpx

    # Build request body depending on desired output format.
    if json_mode:
        prompt_text = f"{system_prompt}\n\n{user_message}\n\nRespond with valid JSON only."
        generation_config = {"temperature": 0.3, "responseMimeType": "application/json"}
    else:
        prompt_text = f"{system_prompt}\n\n{user_message}"
        generation_config = {"temperature": 0.3}

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
                                "text": prompt_text
                            }]
                        }],
                        "generationConfig": generation_config
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



async def call_ai_text(system_prompt: str, user_message: str, json_mode: bool = True):
    """Unified AI entry point: resolve the workspace provider and return plain text.

    Dispatches to openai / gemini / bedrock / emergent based on get_ai_config(),
    with Emergent as the safety-net fallback. Returns (text, provider_used) where
    text is a string or None on total failure. Best-effort — never raises.

    New code should prefer this helper so ALL providers (incl. Bedrock) are
    supported uniformly.
    """
    try:
        cfg = await get_ai_config()
    except Exception:
        cfg = {"provider": None, "api_key": None}
    provider = cfg.get("provider")
    api_key = cfg.get("api_key")

    try:
        if provider == "openai" and api_key:
            r = await call_openai_api(api_key, system_prompt, user_message, json_mode=json_mode)
            if getattr(r, "status_code", 500) == 200:
                return r.json()["choices"][0]["message"]["content"], "openai"
        elif provider == "gemini" and api_key:
            r = await call_gemini_api(api_key, system_prompt, user_message, json_mode=json_mode)
            if getattr(r, "status_code", 500) == 200:
                return extract_gemini_text(r.json()), "gemini"
        elif provider == "bedrock" and api_key:
            r = await call_bedrock_api(api_key, system_prompt, user_message, json_mode=json_mode,
                                       region=cfg.get("region"), model=cfg.get("model"))
            if getattr(r, "status_code", 500) == 200:
                return extract_bedrock_text(r), "bedrock"
    except Exception as e:
        logger.warning(f"[call_ai_text] provider {provider} failed: {e}")

    # Safety net: Emergent LLM (returns parsed JSON or None).
    fb = await call_emergent_fallback(system_prompt, user_message)
    if fb is not None:
        return (json.dumps(fb) if not isinstance(fb, str) else fb), "emergent"
    return None, None
