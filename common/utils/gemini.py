import os
import time
from typing import Any, Dict, List, Optional

import requests

from common.exception.base_exception import ServiceUnavailableException


DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
DEFAULT_GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def get_gemini_model() -> str:
    return os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL).strip() or DEFAULT_GEMINI_MODEL


def get_gemini_url(model: str) -> str:
    configured_url = os.getenv("GEMINI_API_URL", "").strip()
    if configured_url:
        return configured_url.format(model=model) if "{model}" in configured_url else configured_url
    return DEFAULT_GEMINI_API_URL.format(model=model)


def build_gemini_payload(messages: List[Dict[str, str]], temperature: float) -> Dict[str, Any]:
    system_parts = []
    contents = []

    for message in messages:
        role = (message.get("role") or "user").strip().lower()
        content = str(message.get("content") or "").strip()
        if not content:
            continue

        if role == "system":
            system_parts.append({"text": content})
            continue

        contents.append({
            "role": "model" if role == "assistant" else "user",
            "parts": [{"text": content}],
        })

    payload: Dict[str, Any] = {
        "contents": contents or [{"role": "user", "parts": [{"text": ""}]}],
        "generationConfig": {"temperature": temperature},
    }
    if system_parts:
        payload["systemInstruction"] = {"parts": system_parts}

    return payload


def extract_gemini_content(payload: Dict[str, Any]) -> str:
    if not isinstance(payload, dict):
        return ""

    parts_text = []
    for candidate in payload.get("candidates") or []:
        if not isinstance(candidate, dict):
            continue
        content = candidate.get("content") or {}
        for part in content.get("parts") or []:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                parts_text.append(part["text"])

    return "".join(parts_text).strip()


def call_gemini_chat(
    messages: List[Dict[str, str]],
    temperature: float,
    timeout: Optional[float] = None,
) -> Dict[str, Optional[str]]:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    model = get_gemini_model()
    if not api_key:
        raise ServiceUnavailableException(
            message="Gemini API key is required to generate the response",
            details={"provider": "gemini", "model": model, "error": "gemini_api_key_missing"},
        )

    request_timeout = timeout if timeout is not None else float(os.getenv("GEMINI_TIMEOUT", "30"))
    url = get_gemini_url(model)
    response = None

    max_retries = 3
    retry_delay = 2.0  # seconds

    for attempt in range(max_retries):
        try:
            response = requests.post(
                url,
                headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                json=build_gemini_payload(messages, temperature),
                timeout=request_timeout,
            )
            response.raise_for_status()
            # Request succeeded, break the retry loop
            break
        except requests.HTTPError as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None) or getattr(response, "status_code", None)
            is_retryable = status_code in (429, 500, 502, 503, 504)
            if attempt == max_retries - 1 or not is_retryable:
                if status_code == 404:
                    error = "gemini_model_not_found"
                elif status_code == 413:
                    error = "gemini_payload_too_large"
                else:
                    error = str(exc)
                raise ServiceUnavailableException(
                    message="Unable to reach Gemini",
                    details={"provider": "gemini", "model": model, "error": error},
                ) from exc
            time.sleep(retry_delay)
            retry_delay *= 2.0
        except (requests.Timeout, requests.ConnectionError) as exc:
            if attempt == max_retries - 1:
                raise ServiceUnavailableException(
                    message="Unable to reach Gemini",
                    details={"provider": "gemini", "model": model, "error": str(exc)},
                ) from exc
            time.sleep(retry_delay)
            retry_delay *= 2.0
        except requests.RequestException as exc:
            raise ServiceUnavailableException(
                message="Unable to reach Gemini",
                details={"provider": "gemini", "model": model, "error": str(exc)},
            ) from exc

    try:
        payload = response.json()
    except ValueError:
        content = response.text.strip()
        return {"provider": "gemini", "model": model, "content": content or None}

    return {"provider": "gemini", "model": model, "content": extract_gemini_content(payload)}
