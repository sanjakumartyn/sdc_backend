import json
from typing import Any, Dict, List, Tuple

from ninja import Router

from common.exception.base_exception import BadRequestException
from common.response.base_response import APIEnvelope
from common.response.response_builder import ResponseBuilder
from features.companyAnalysis.schema import (
    CompanyAnalysisResponseSchema,
    DealCoachRequestSchema,
    DealCoachResponseSchema,
)
from features.companyAnalysis.service import CompanyAnalysisService

router = Router()


@router.post("", response={200: APIEnvelope[CompanyAnalysisResponseSchema]})
def analyze_company(request):
    payload, uploaded_files = _parse_analysis_request(request)
    result = CompanyAnalysisService.analyze(payload, uploaded_files=uploaded_files)
    return ResponseBuilder.success(result)


@router.post("/deal-coach", response={200: APIEnvelope[DealCoachResponseSchema]})
def deal_coach(request, payload: DealCoachRequestSchema):
    result = CompanyAnalysisService.deal_coach(payload.model_dump())
    return ResponseBuilder.success(result)


def _parse_analysis_request(request) -> Tuple[Dict[str, Any], List[Any]]:
    content_type = request.META.get("CONTENT_TYPE", "")

    if content_type.startswith("multipart/form-data"):
        documents = request.POST.getlist("documents")
        if not documents:
            documents = request.POST.getlist("documents[]")

        if len(documents) == 1:
            documents = _parse_documents_value(documents[0])

        uploaded_files = request.FILES.getlist("file")
        uploaded_files.extend(request.FILES.getlist("files"))

        return {
            "account_id": request.POST.get("account_id", ""),
            "company_name": request.POST.get("company_name", ""),
            "company": request.POST.get("company", ""),
            "website_url": request.POST.get("website_url", ""),
            "question": request.POST.get("question", "Create full company analysis dashboard"),
            "documents": documents,
        }, uploaded_files

    try:
        payload = json.loads((request.body or b"{}").decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BadRequestException("Invalid JSON request body") from exc

    if not isinstance(payload, dict):
        raise BadRequestException("Request body must be a JSON object")

    return payload, []


def _parse_documents_value(value: str) -> List[str]:
    value = (value or "").strip()
    if not value:
        return []

    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return [value]

    if isinstance(parsed, list):
        return [str(item) for item in parsed]

    return [value]
