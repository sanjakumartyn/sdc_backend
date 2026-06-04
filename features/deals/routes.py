from typing import List, Optional, Dict, Any
from ninja import Router
from pydantic import BaseModel
from common.response.base_response import APIEnvelope
from common.response.response_builder import ResponseBuilder
from common.utils.helpers import parse_query_param_int
from features.deals.schema import DealSchema, DealCreateSchema, DealUpdateSchema
from features.deals.service import DealService

router = Router()

# Custom schema representing the paginated items block
class DealPaginationData(BaseModel):
    items: List[DealSchema]
    total: int
    page: int
    limit: int
    pages: int


@router.get("", response={200: APIEnvelope[DealPaginationData]})
def list_deals(
    request, 
    stage: Optional[str] = None, 
    min_value: Optional[float] = None,
    page: int = 1,
    limit: int = 10
):
    """
    Retrieves a paginated list of deals filtered by pipeline stage or minimum deal value.
    (Open Endpoint)
    """
    page_parsed = parse_query_param_int(page, default=1, min_val=1)
    limit_parsed = parse_query_param_int(limit, default=10, min_val=1, max_val=100)
    
    offset = (page_parsed - 1) * limit_parsed
    records, total = DealService.list_deals(
        stage=stage, 
        min_value=min_value, 
        limit=limit_parsed, 
        offset=offset
    )
    
    # Map Django ORM query models to serializable Pydantic schemas
    items = [DealSchema.from_attributes(r) for r in records]
    
    pages = (total + limit_parsed - 1) // limit_parsed if limit_parsed > 0 else 0
    
    payload = {
        "items": items,
        "total": total,
        "page": page_parsed,
        "limit": limit_parsed,
        "pages": pages
    }
    
    return ResponseBuilder.success(payload)


@router.get("/{deal_id}", response={200: APIEnvelope[DealSchema]})
def get_deal(request, deal_id: str):
    """
    Retrieves a single sales deal by its primary key ID.
    (Open Endpoint)
    """
    deal = DealService.get_deal(deal_id)
    return ResponseBuilder.success(DealSchema.from_attributes(deal))


@router.post("", response={201: APIEnvelope[DealSchema]})
def create_deal(request, payload: DealCreateSchema):
    """
    Creates a new sales opportunity deal.
    (Open Endpoint)
    """
    deal = DealService.create_deal(payload.dict())
    return 201, ResponseBuilder.success(DealSchema.from_attributes(deal))


@router.put("/{deal_id}", response={200: APIEnvelope[DealSchema]})
def update_deal(request, deal_id: str, payload: DealUpdateSchema):
    """
    Updates specific attributes of an active deal.
    (Open Endpoint)
    """
    # Filter out empty fields that are not sent in request
    update_data = {k: v for k, v in payload.dict().items() if v is not None}
    
    updated_deal = DealService.update_deal(deal_id, update_data)
    return ResponseBuilder.success(DealSchema.from_attributes(updated_deal))


@router.delete("/{deal_id}", response={200: APIEnvelope[Dict[str, str]]})
def delete_deal(request, deal_id: str):
    """
    Permanently deletes a deal record.
    (Open Endpoint)
    """
    DealService.delete_deal(deal_id)
    return ResponseBuilder.success({"message": f"Deal {deal_id} has been deleted successfully"})
