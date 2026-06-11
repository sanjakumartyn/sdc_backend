from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class QuestionRequestSchema(BaseModel):
    company: str = Field(..., min_length=1, description="Company name to query")
    documents: List[str] = Field( 
        default=[],
        description="List of document URLs or document IDs"
    )
    question: Optional[str] = Field(
        default=None,
        description="Question/query text for RAG endpoints"
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
    project_id: str = "companyproduct"
    project_key: str = "companyproduct"
    filters: Dict[str, Any] = Field(default_factory=dict)


class RAGCaseStudiesRequestSchema(BaseModel):
    """Request schema for RAG case studies endpoint"""
    question: str
    project_id: str = "casestudies"
    project_key: str = "casestudies"
    filters: Dict[str, Any] = Field(default_factory=dict)


class QuestionResponseSchema(BaseModel):
    company: str
    documents: List[str] = Field(default_factory=list)
    upstream: Dict[str, Any]
    rag_products: Dict[str, Any] = Field(default_factory=dict)
    rag_casestudies: Dict[str, Any] = Field(default_factory=dict)
    ocr_extractions: List[Dict[str, Any]] = Field(default_factory=list)
    synthesized_answer: Optional[str] = None
    synthesis_provider: Optional[str] = None
    synthesis_model: Optional[str] = None
    synthesis_error: Optional[str] = None
