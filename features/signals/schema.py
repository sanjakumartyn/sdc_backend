from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator

class SignalBaseSchema(BaseModel):
    title: str = Field(..., max_length=255, description="Short title describing the signal")
    source: str = Field(..., max_length=100, description="Origin source of signal (e.g. EMAIL, WEBPAGE)")
    score: int = Field(50, ge=0, le=100, description="Score scaling from 0 to 100")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Custom details payload dict")


class SignalCreateSchema(SignalBaseSchema):
    """Input payload schema for creating a new Signal."""
    pass


class SignalUpdateSchema(BaseModel):
    """Input payload schema for updating an existing Signal."""
    title: Optional[str] = Field(None, max_length=255)
    source: Optional[str] = Field(None, max_length=100)
    score: Optional[int] = Field(None, ge=0, le=100)
    payload: Optional[Dict[str, Any]] = None
    status: Optional[str] = Field(None, description="Updated processing state (e.g., NEW, PROCESSED, ARCHIVED)")


class SignalSchema(SignalBaseSchema):
    """Output serializable representation of a Signal."""
    id: str
    status: str
    created_at: datetime
    updated_at: datetime

    @field_validator("id", mode="before")
    @classmethod
    def stringify_id(cls, value):
        if value is None:
            return value
        return str(value)

    class Config:
        from_attributes = True  # Pydantic v2 configuration to load from Django DB ORM objects
