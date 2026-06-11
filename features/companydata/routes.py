from ninja import Router, Query
from typing import Any, Dict, List

from common.response.base_response import APIEnvelope
from common.response.response_builder import ResponseBuilder
from features.companydata.schema import QuerySchema, UpdateDocumentSchema
from features.companydata.service import CompanyDataService
from features.callAgents.service import CallAgentsService

router = Router()

@router.get("/all", response={200: APIEnvelope[Dict[str, List[Dict[str, Any]]]]})
def get_all_data(request, limit_per_collection: int = 50):
    """
    Retrieve data from all collections in the companydetails database.
    Returns a dictionary mapping collection names to lists of their documents.
    """
    all_data = CompanyDataService.get_all_data(limit_per_collection=limit_per_collection)
    return ResponseBuilder.success(all_data)

@router.get("/company/details", response={200: APIEnvelope[Dict[str, Any]]})
def get_company_details(request, company: str = Query(None)):
    """Retrieve company details, enriching static data with a dynamic strategic fit score.
    If a company name is provided, perform analysis; otherwise return static document.
    """
    # Fetch static company document (if any)
    documents, _ = CompanyDataService.get_documents("companydetails", limit=1)
    company_doc = documents[0] if documents else {}
    if company:
        synthesis = CallAgentsService.analyze_company({"company": company})
        company_doc["strategicFit"] = synthesis.get("strategic_fit_score", 0)
    return ResponseBuilder.success(company_doc)


@router.get("/{collection_name}", response={200: APIEnvelope[Dict[str, Any]]})
def get_documents(request, collection_name: str, query: Query[QuerySchema]):
    """
    Retrieve documents from any specified collection in the companydetails database.
    """
    documents, total_count = CompanyDataService.get_documents(
        collection_name=collection_name,
        limit=query.limit,
        offset=query.offset
    )
    page = (query.offset // query.limit) + 1 if query.limit > 0 else 1
    return ResponseBuilder.paginate(
        items=documents,
        page=page,
        limit=query.limit,
        total=total_count
    )

@router.put("/{collection_name}/{document_id}", response={200: APIEnvelope[Dict[str, Any]]})
def update_document(request, collection_name: str, document_id: str, payload: UpdateDocumentSchema):
    """
    Update a document within the specified collection.
    """
    # model_dump() gives all fields including extras due to ConfigDict(extra="allow")
    update_data = payload.model_dump()
    result = CompanyDataService.update_document(
        collection_name=collection_name, 
        document_id=document_id, 
        update_data=update_data
    )
    return ResponseBuilder.success(result)
