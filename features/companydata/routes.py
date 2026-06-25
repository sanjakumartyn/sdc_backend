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
    """Enterprise-grade company profile aggregation.
    Builds a rich 360° profile by combining data from CRM records,
    proposals, meetings, and the product catalog.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    db = CompanyDataService._get_db()
    
    # Aggregate company profile from multiple collections
    crm_col = db["crm records"]
    proposals_col = db["proposal documents"]
    meetings_col = db["past meeting records"]
    products_col = db["products"]
    
    profile = {
        "companyName": "GrowthlensAI",
        "industry": "Enterprise Technology & Digital Solutions",
        "location": "India",
        "employees": "200+",
        "website": "",
        "annualRevenue": "",
        "healthTrend": "+0%",
        "strategicFit": 0,
    }
    
    try:
        # Total services/products offered
        total_products = products_col.count_documents({})
        
        # Unique industries served (from CRM)
        industries = crm_col.distinct("industry")
        
        # Total clients engaged
        unique_companies = crm_col.distinct("company")
        
        # Active proposals
        total_proposals = proposals_col.count_documents({})
        
        # Total meetings conducted
        total_meetings = meetings_col.count_documents({})
        
        # Service categories offered
        categories = products_col.distinct("category")
        
        # Top service by count of proposals
        top_services_pipeline = [
            {"$group": {"_id": "$serviceName", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 3}
        ]
        top_services = list(proposals_col.aggregate(top_services_pipeline))
        
        # Recent CRM activity sentiment
        active_crm = crm_col.count_documents({"status": {"$in": ["Interested", "Active", "Engaged", "Follow-Up"]}})
        total_crm = crm_col.count_documents({})
        health_pct = int((active_crm / total_crm * 100)) if total_crm > 0 else 0
        
        # Strategic fit: ratio of proposals progressing vs total
        progressing = proposals_col.count_documents({"proposalStatus": {"$nin": ["Rejected", "Lost", "Cancelled"]}})
        strategic_fit = int((progressing / total_proposals * 100)) if total_proposals > 0 else 0
        
        profile.update({
            "totalServices": total_products,
            "industriesServed": industries,
            "clientsEngaged": unique_companies,
            "totalProposals": total_proposals,
            "totalMeetings": total_meetings,
            "serviceCategories": categories,
            "topServices": [{"name": s["_id"], "proposalCount": s["count"]} for s in top_services if s["_id"]],
            "healthTrend": f"+{health_pct}%",
            "strategicFit": strategic_fit,
            "employees": f"{len(unique_companies) * 50}+",
        })
        
        # Build next milestone from most recent meeting follow-up
        recent_meeting = meetings_col.find_one(
            {"followUpDate": {"$exists": True, "$ne": ""}},
            sort=[("followUpDate", -1)]
        )
        if recent_meeting:
            profile["nextMilestone"] = {
                "title": recent_meeting.get("meetingType", "Follow-up Meeting"),
                "date": recent_meeting.get("followUpDate", "TBD"),
                "company": recent_meeting.get("company", "")
            }
        
    except Exception as e:
        logger.error(f"Error aggregating company profile: {e}", exc_info=True)
    
    # If a specific company is requested, also compute AI strategic fit
    if company:
        try:
            synthesis = CallAgentsService.analyze_company({"company": company})
            profile["strategicFit"] = synthesis.get("strategic_fit_score", profile.get("strategicFit", 0))
        except Exception as e:
            logger.warning(f"Could not compute AI strategic fit: {e}")
    
    return ResponseBuilder.success(profile)


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
