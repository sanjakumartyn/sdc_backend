from ninja import Router
from features.dashboard.service import DashboardService
from features.callAgents.service import CallAgentsService
from features.callAgents.routes import _parse_question_request
from common.response.response_builder import ResponseBuilder

router = Router()

@router.get("")
def get_dashboard_summary(request):
    """
    Retrieves a temporary dashboard summary.
    """
    return DashboardService.get_summary()

@router.get("/total-revenue")
def get_total_revenue(request):
    """
    Retrieves the total revenue generated from past_sales.
    """
    result = DashboardService.get_total_revenue()
    if result.get("success"):
        return ResponseBuilder.success(result)
    return ResponseBuilder.error(result.get("error", "Failed to retrieve revenue"))

@router.post("/analyze-company")
def analyze_company(request):
    """
    Analyzes a company by orchestrating scraping, OCR, RAG, and LLM synthesis.
    """
    payload, uploaded_files = _parse_question_request(request)
    result = CallAgentsService.analyze_company(payload, uploaded_files=uploaded_files)
    return ResponseBuilder.success(result)
