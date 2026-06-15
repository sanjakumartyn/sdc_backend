from typing import List, Optional

from pydantic import BaseModel, Field


class CompanyAnalysisRequestSchema(BaseModel):
    account_id: Optional[str] = Field(default=None, description="External account identifier")
    company_name: Optional[str] = Field(default=None, description="Company name to analyze")
    company: Optional[str] = Field(default=None, description="Backward-compatible company name")
    website_url: Optional[str] = Field(default=None, description="Company website URL")
    question: Optional[str] = Field(default="Create full company analysis dashboard")
    documents: List[str] = Field(default_factory=list)


class StrategicFitSchema(BaseModel):
    score: int = Field(..., ge=0, le=100)
    alignment_level: str
    explanation: str


class MeetingPrepSchema(BaseModel):
    key_discussion_topics: List[str] = Field(default_factory=list)
    business_priorities: List[str] = Field(default_factory=list)
    executive_talking_points: List[str] = Field(default_factory=list)
    potential_objections: List[str] = Field(default_factory=list)
    recommended_agenda: List[str] = Field(default_factory=list)
    qbr_summary: str


class IntelligenceOverviewSchema(BaseModel):
    company_overview: str
    industry_position: str
    business_model: str
    strategic_goals: List[str] = Field(default_factory=list)
    expansion_initiatives: List[str] = Field(default_factory=list)
    digital_transformation_efforts: List[str] = Field(default_factory=list)
    sustainability_commitments: List[str] = Field(default_factory=list)


class NeedsPredictionSchema(BaseModel):
    need: str
    confidence: int = Field(..., ge=0, le=100)
    reason: str


class SolutionMappingSchema(BaseModel):
    requirement: str
    novachem_solution: str
    match_percent: int = Field(..., ge=0, le=100)
    deal_value: Optional[str] = None
    reason: str


class CompanyAnalysisResponseSchema(BaseModel):
    company_name: str
    strategic_fit: StrategicFitSchema
    meeting_prep: MeetingPrepSchema
    intelligence_overview: IntelligenceOverviewSchema
    ai_needs_prediction: List[NeedsPredictionSchema] = Field(default_factory=list)
    solution_mapping: List[SolutionMappingSchema] = Field(default_factory=list)


class DealCoachRequestSchema(BaseModel):
    company_name: Optional[str] = None
    company: Optional[str] = None
    account_id: Optional[str] = None
    website_url: Optional[str] = None
    message: str


class DealCoachResponseSchema(BaseModel):
    answer: str
