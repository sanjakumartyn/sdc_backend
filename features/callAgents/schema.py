from typing import List, Optional, Dict, Any

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
    project_id: Optional[str] = Field(
        default="default",
        description="Project ID for RAG endpoints"
    )
    project_key: Optional[str] = Field(
        default="default",
        description="Project key for RAG endpoints"
    )
    filters: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Filters for RAG endpoint queries (e.g., tag-based)"
    )


class RAGProductsRequestSchema(BaseModel):
    """Request schema for RAG products endpoint"""
    question: str
    project_id: str = "product"
    project_key: str = "product"
    filters: Dict[str, Any] = Field(default_factory=dict)


class RAGCaseStudiesRequestSchema(BaseModel):
    """Request schema for RAG case studies endpoint"""
    question: str
    project_id: str = "casestudy"
    project_key: str = "casestudy"
    filters: Dict[str, Any] = Field(default_factory=dict)


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
