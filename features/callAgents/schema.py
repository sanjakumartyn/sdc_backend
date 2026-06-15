from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class QuestionRequestSchema(BaseModel):
    account_id: Optional[str] = Field(default=None, description="External account identifier")
    company_name: Optional[str] = Field(default=None, description="Company name to query")
    company: Optional[str] = Field(default=None, description="Backward-compatible company name")
    website_url: Optional[str] = Field(default=None, description="Company website URL")
    question: Optional[str] = Field(default=None, description="Optional user/product search question")
    documents: List[str] = Field( 
        default=[],
        description="List of document URLs or document IDs"
    )

    

class QuestionResponseSchema(BaseModel):
    company: str
    company_name: Optional[str] = None
    account_id: Optional[str] = None
    website_url: Optional[str] = None
    question: Optional[str] = None
    documents: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    product_question: Optional[str] = None
    keyword_generation_provider: Optional[str] = None
    keyword_generation_model: Optional[str] = None
    keyword_generation_error: Optional[str] = None
    product_question_generation_error: Optional[str] = None
    upstream: Dict[str, Any]
    company_data: Dict[str, Any] = Field(default_factory=dict)
    ocr_extractions: List[Dict[str, Any]] = Field(default_factory=list)
    synthesized_answer: Optional[str] = None
    synthesis_provider: Optional[str] = None
    synthesis_model: Optional[str] = None
    synthesis_error: Optional[str] = None
