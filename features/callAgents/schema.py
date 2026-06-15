from typing import List, Optional

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
    answer: str
