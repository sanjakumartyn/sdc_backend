from pydantic import BaseModel, HttpUrl

class ExtractRequestSchema(BaseModel):
    """Schema for JSON payload containing a public document URL to be processed by OCR."""
    url: HttpUrl
