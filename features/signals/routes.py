from typing import List, Optional, Dict, Any
from ninja import Router
from pydantic import BaseModel
from common.response.base_response import APIEnvelope
from common.response.response_builder import ResponseBuilder
from common.utils.helpers import parse_query_param_int
from features.signals.schema import SignalSchema, SignalCreateSchema, SignalUpdateSchema
from features.signals.service import SignalService

router = Router()

# Custom schema representing the paginated items block
class SignalPaginationData(BaseModel):
    items: List[SignalSchema]
    total: int
    page: int
    limit: int
    pages: int


@router.get("", response={200: APIEnvelope[SignalPaginationData]})
def list_signals(
    request, 
    status: Optional[str] = None, 
    source: Optional[str] = None,
    page: int = 1,
    limit: int = 10
):
    """
    Retrieves a paginated list of signals filtered by status or source.
    (Open Endpoint)
    """
    page_parsed = parse_query_param_int(page, default=1, min_val=1)
    limit_parsed = parse_query_param_int(limit, default=10, min_val=1, max_val=100)
    
    offset = (page_parsed - 1) * limit_parsed
    records, total = SignalService.list_signals(
        status=status, 
        source=source, 
        limit=limit_parsed, 
        offset=offset
    )
    
    # Map Django ORM query models to serializable Pydantic schemas
    items = [SignalSchema.from_attributes(r) for r in records]
    
    pages = (total + limit_parsed - 1) // limit_parsed if limit_parsed > 0 else 0
    
    payload = {
        "items": items,
        "total": total,
        "page": page_parsed,
        "limit": limit_parsed,
        "pages": pages
    }
    
    return ResponseBuilder.success(payload)


@router.get("/{signal_id}", response={200: APIEnvelope[SignalSchema]})
def get_signal(request, signal_id: str):
    """
    Retrieves a single signal by its primary key ID.
    (Open Endpoint)
    """
    signal = SignalService.get_signal(signal_id)
    return ResponseBuilder.success(SignalSchema.from_attributes(signal))


@router.post("", response={201: APIEnvelope[SignalSchema]})
def create_signal(request, payload: SignalCreateSchema):
    """
    Creates a new marketing or transactional signal.
    (Open Endpoint)
    """
    # No authentication: default creator is 'system'
    created_by_user = "system"

    signal_data = payload.dict()
    signal_data.setdefault("payload", {})
    signal_data["payload"]["created_by"] = created_by_user

    signal = SignalService.create_signal(signal_data)
    return 201, ResponseBuilder.success(SignalSchema.from_attributes(signal))


@router.put("/{signal_id}", response={200: APIEnvelope[SignalSchema]})
def update_signal(request, signal_id: str, payload: SignalUpdateSchema):
    """
    Updates specific attributes of a signal.
    (Open Endpoint)
    """
    # Filter out empty fields that are not sent in request
    update_data = {k: v for k, v in payload.dict().items() if v is not None}
    
    updated_signal = SignalService.update_signal(signal_id, update_data)
    return ResponseBuilder.success(SignalSchema.from_attributes(updated_signal))


@router.delete("/{signal_id}", response={200: APIEnvelope[Dict[str, str]]})
def delete_signal(request, signal_id: str):
    """
    Permanently deletes a signal by ID.
    (Open Endpoint)
    """
    SignalService.delete_signal(signal_id)
    return ResponseBuilder.success({"message": f"Signal {signal_id} has been deleted successfully"})
