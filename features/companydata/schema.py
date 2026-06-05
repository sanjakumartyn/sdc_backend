from pydantic import BaseModel, ConfigDict
from typing import Dict, Any, Optional

class QuerySchema(BaseModel):
    limit: int = 10
    offset: int = 0
    # Additional generic query parameters could be added here

class UpdateDocumentSchema(BaseModel):
    # Allows any JSON payload
    model_config = ConfigDict(extra="allow")

class DocumentResponseSchema(BaseModel):
    # A generic document representation
    model_config = ConfigDict(extra="allow")
