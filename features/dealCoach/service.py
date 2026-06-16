import os
import requests
import json
from typing import Any, Dict
from common.exception.base_exception import ServiceUnavailableException

class DealCoachService:
    @staticmethod
    def get_mistral_response(message: str, context: Dict[str, Any]) -> str:
        # Mistral AI configuration
        api_key = os.getenv("MISTRAL_API_KEY", "PHpbLmkYoIIDD6N4Af1FQXfg3LdtDLeX").strip()
        model = os.getenv("MISTRAL_MODEL", "mistral-large-latest").strip()
        api_url = os.getenv("MISTRAL_API_URL", "https://api.mistral.ai/v1/chat/completions").strip()
        timeout = float(os.getenv("MISTRAL_TIMEOUT", "30"))

        # Format context nicely
        try:
            context_str = json.dumps(context, ensure_ascii=True, indent=2, default=str)
        except Exception:
            context_str = str(context)

        # Truncate if context is too large (Mistral has large context, but let's be safe)
        if len(context_str) > 15000:
            context_str = context_str[:15000] + "\n... (context truncated)"

        system_prompt = (
            "You are an AI deal coach for NovaChem Solutions. Your goal is to guide the sales team "
            "with practical, actionable advice, objection handling, pricing tactics, and deal strategy.\n\n"
            "Here is the context data about the company they are targeting:\n"
            f"{context_str}\n\n"
            "Be business-focused, concise, and helpful. Frame your answers around the company's specific needs, "
            "objections, and NovaChem's matching solutions."
        )

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        request_body = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ],
            "temperature": 0.2
        }

        try:
            response = requests.post(
                api_url,
                headers=headers,
                json=request_body,
                timeout=timeout
            )
            response.raise_for_status()
            response_json = response.json()
            choices = response_json.get("choices") or []
            if choices:
                answer = choices[0].get("message", {}).get("content", "").strip()
                if answer:
                    return answer
            raise ValueError("Empty response structure from Mistral")
        except Exception as exc:
            raise ServiceUnavailableException(
                message="Unable to generate answer from Mistral AI service",
                details={"error": str(exc), "provider": "mistral"}
            ) from exc
