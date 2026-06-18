import json
import os
from typing import Any, Dict

from common.exception.base_exception import ServiceUnavailableException
from common.utils.gemini import call_gemini_chat


class DealCoachService:
    @staticmethod
    def get_gemini_response(message: str, context: Dict[str, Any]) -> str:
        try:
            context_str = json.dumps(context, ensure_ascii=True, indent=2, default=str)
        except Exception:
            context_str = str(context)

        if len(context_str) > 15000:
            context_str = context_str[:15000] + "\n... (context truncated)"

        system_prompt = (
            "You are an AI deal coach for GrowthlensAI. Your goal is to guide the sales team "
            "with practical, actionable advice, objection handling, pricing tactics, and deal strategy.\n\n"
            "Here is the context data about the company they are targeting:\n"
            f"{context_str}\n\n"
            "Be business-focused, concise, and helpful. Frame your answers around the company's specific needs, "
            "objections, and GrowthlensAI's matching solutions."
        )

        try:
            result = call_gemini_chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                temperature=0.2,
                timeout=float(os.getenv("GEMINI_TIMEOUT", "30")),
            )
            answer = (result.get("content") or "").strip()
            if answer:
                return answer
            raise ValueError("Empty response structure from Gemini")
        except Exception as exc:
            raise ServiceUnavailableException(
                message="Unable to generate answer from Gemini AI service",
                details={"error": str(exc), "provider": "gemini"}
            ) from exc
