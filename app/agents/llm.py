"""
Single shared Hugging Face Inference client + helper for asking the model to
triage/explain raw findings from deterministic tools (Bandit, Semgrep, diff
heuristics) in plain English. Every agent that needs an LLM call goes through
here so retries, model choice, and prompt conventions stay in one place.
"""
import json
import logging

from huggingface_hub import InferenceClient

from app.config import settings

logger = logging.getLogger("codeguardian.llm")

_client: InferenceClient | None = None


def get_client() -> InferenceClient:
    global _client
    if _client is None:
        _client = InferenceClient(api_key=settings.huggingface_api_key)
    return _client


def ask_json(system: str, user: str, max_tokens: int = 1024) -> list | dict | None:
    """
    Send a prompt that instructs the model to respond with JSON only, and parse
    the result. Returns None (and logs) if the call fails or the response isn't
    valid JSON, so callers can fall back to the raw, un-triaged findings instead
    of crashing the whole review.
    """
    if not settings.huggingface_api_key:
        logger.warning("HUGGINGFACE_API_KEY not set — skipping LLM triage.")
        return None

    try:
        response = get_client().chat_completion(
            model=settings.huggingface_model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        text = response.choices[0].message.content
        return json.loads(_strip_code_fence(text))
    except Exception:
        logger.exception("LLM triage call failed")
        return None


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.endswith("```"):
            text = text[: -3]
        if text.startswith("json"):
            text = text[4:]
    return text.strip()
