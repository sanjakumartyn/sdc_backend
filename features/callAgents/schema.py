from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class QuestionRequestSchema(BaseModel):
    company: str = Field(..., min_length=1, description="Company name to query")
    documents: List[str] = Field( 
        default=[],
        description="List of document URLs or document IDs"
    )

    

class QuestionResponseSchema(BaseModel):
    company: str
    documents: List[str] = Field(default_factory=list)
    upstream: Dict[str, Any]
    company_data: Dict[str, Any] = Field(default_factory=dict)
    ocr_extractions: List[Dict[str, Any]] = Field(default_factory=list)
    synthesized_answer: Optional[str] = None
    synthesis_provider: Optional[str] = None
    synthesis_model: Optional[str] = None
    synthesis_error: Optional[str] = None
