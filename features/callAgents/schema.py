from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class QuestionRequestSchema(BaseModel):
    company: str = Field(..., min_length=1, description="Company name to query")


class QuestionResponseSchema(BaseModel):
    company: str
    upstream: Dict[str, Any]
    synthesized_answer: Optional[str] = None
    synthesis_provider: Optional[str] = None
    synthesis_model: Optional[str] = None
    synthesis_error: Optional[str] = None
