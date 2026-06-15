import json
import os
import re
from decimal import Decimal
from typing import Any, Dict, List, Optional, Sequence

from pydantic import ValidationError

from common.exception.base_exception import (
    BadRequestException,
    GroqApiKeyMissingException,
    ServiceUnavailableException,
)
from features.callAgents.service import CallAgentsService
from features.companyAnalysis.schema import CompanyAnalysisResponseSchema
from features.companydata.service import CompanyDataService
from features.deals.service import DealService


class CompanyAnalysisService:
    @staticmethod
    def analyze(payload: Dict[str, Any], uploaded_files: Optional[Sequence[Any]] = None) -> Dict[str, Any]:
        context = CompanyAnalysisService._build_context(payload, uploaded_files=uploaded_files)
        result = CompanyAnalysisService._call_dashboard_groq(context)
        result["company_name"] = result.get("company_name") or context["company_name"]

        try:
            validated = CompanyAnalysisResponseSchema(**result)
        except ValidationError as exc:
            raise ServiceUnavailableException(
                message="Unable to generate the company analysis dashboard",
                details={"error": "groq_dashboard_response_invalid", "validation_errors": exc.errors()},
            ) from exc

        return validated.model_dump()

    @staticmethod
    def deal_coach(payload: Dict[str, Any]) -> Dict[str, str]:
        message = (payload.get("message") or "").strip()
        if not message:
            raise BadRequestException("message is required")

        context = CompanyAnalysisService._build_context(
            {
                "company_name": payload.get("company_name"),
                "company": payload.get("company"),
                "account_id": payload.get("account_id"),
                "website_url": payload.get("website_url"),
                "question": message,
                "documents": [],
            },
            uploaded_files=[],
        )

        result = CompanyAnalysisService._call_deal_coach_groq(context=context, message=message)
        answer = (result.get("content") or "").strip()
        if not answer:
            raise ServiceUnavailableException(
                message="Unable to generate the deal coach answer",
                details={"provider": result.get("provider"), "model": result.get("model"), "error": result.get("error")},
            )

        return {"answer": answer}

    @staticmethod
    def _build_context(payload: Dict[str, Any], uploaded_files: Optional[Sequence[Any]]) -> Dict[str, Any]:
        company_name = (payload.get("company_name") or payload.get("company") or "").strip()
        if not company_name:
            raise BadRequestException("company or company_name is required")

        account_id = (payload.get("account_id") or "").strip()
        website_url = (payload.get("website_url") or "").strip()
        question = (payload.get("question") or "Create full company analysis dashboard").strip()
        documents = payload.get("documents") or payload.get("document_ids") or []
        if not isinstance(documents, list):
            raise BadRequestException("documents must be a list")

        documents = [str(doc).strip() for doc in documents if str(doc).strip()]
        ocr_extractions = CallAgentsService._extract_uploaded_documents(uploaded_files or [])
        company_data = CompanyAnalysisService._fetch_company_data()
        crm_deals = CompanyAnalysisService._fetch_crm_deals()

        agent_upstream = CallAgentsService._fetch_agent_response(
            account_id=account_id,
            company_name=company_name,
            website_url=website_url,
        )
        compact_agent_for_keywords = CallAgentsService._summarize_agent(agent_upstream)
        compact_ocr_for_keywords = CallAgentsService._summarize_ocr_extractions(ocr_extractions)
        compact_company_data_for_keywords = CallAgentsService._truncate_value(company_data)

        keyword_generation = CallAgentsService._generate_keywords(
            company_name=company_name,
            documents=documents,
            user_question=question,
            agent_upstream=compact_agent_for_keywords,
            ocr_extractions=compact_ocr_for_keywords,
            company_data=compact_company_data_for_keywords,
        )
        keywords = keyword_generation.get("keywords") or CallAgentsService._fallback_keywords(company_name, documents)
        product_question = (
            keyword_generation.get("product_question")
            or CallAgentsService._fallback_product_question(company_name, question)
        )

        product_rag = CallAgentsService._fetch_product_rag_response(product_question=product_question)
        case_study_rag = CallAgentsService._fetch_case_study_rag_response(product_question=product_question)

        compact = CallAgentsService._build_compact_synthesis_context(
            company=company_name,
            user_question=question,
            keywords=keywords,
            product_question=product_question,
            agent_upstream=agent_upstream,
            product_rag_upstream=product_rag,
            case_study_rag_upstream=case_study_rag,
            ocr_extractions=ocr_extractions,
            company_data=company_data,
        )
        compact["account_id"] = account_id
        compact["website_url"] = website_url
        compact["documents"] = documents
        compact["crm_deals"] = crm_deals
        return compact

    @staticmethod
    def _fetch_company_data() -> Dict[str, Any]:
        try:
            return CompanyDataService.get_all_data(
                limit_per_collection=int(os.getenv("COMPANY_ANALYSIS_DATA_LIMIT_PER_COLLECTION", "10"))
            )
        except Exception as exc:
            return {"error": "company_data_unavailable", "details": str(exc)}

    @staticmethod
    def _fetch_crm_deals() -> List[Dict[str, Any]]:
        try:
            deals, _ = DealService.list_deals(limit=int(os.getenv("COMPANY_ANALYSIS_DEAL_LIMIT", "10")), offset=0)
        except Exception as exc:
            return [{"error": "crm_deals_unavailable", "details": str(exc)}]

        return [
            {
                "name": deal.name,
                "value": CompanyAnalysisService._serialize_value(deal.value),
                "stage": deal.stage,
                "probability": deal.probability,
                "close_date": deal.close_date.isoformat() if deal.close_date else None,
            }
            for deal in deals
        ]

    @staticmethod
    def _call_dashboard_groq(context: Dict[str, Any]) -> Dict[str, Any]:
        if not os.getenv("GROQ_API_KEY", "").strip():
            raise GroqApiKeyMissingException()

        result = CallAgentsService._call_groq_chat(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You generate enterprise sales intelligence dashboards. Return only strict JSON "
                        "with these top-level keys: company_name, strategic_fit, meeting_prep, "
                        "intelligence_overview, ai_needs_prediction, solution_mapping. Use only provided "
                        "evidence. Do not invent facts. Use empty arrays or concise insufficient-evidence "
                        "text when evidence is missing. Scores must be integers from 0 to 100."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(context, ensure_ascii=True, indent=2, default=str),
                },
            ],
            temperature=0.2,
        )

        if result.get("error"):
            raise ServiceUnavailableException(
                message="Unable to generate the company analysis dashboard",
                details={"provider": result.get("provider"), "model": result.get("model"), "error": result.get("error")},
            )

        parsed = CompanyAnalysisService._parse_json_object(result.get("content") or "")
        if not parsed:
            raise ServiceUnavailableException(
                message="Unable to generate the company analysis dashboard",
                details={"provider": result.get("provider"), "model": result.get("model"), "error": "groq_dashboard_json_missing"},
            )

        return parsed

    @staticmethod
    def _call_deal_coach_groq(context: Dict[str, Any], message: str) -> Dict[str, Any]:
        if not os.getenv("GROQ_API_KEY", "").strip():
            raise GroqApiKeyMissingException()

        result = CallAgentsService._call_groq_chat(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an AI deal coach for NovaChem Solutions. Answer the sales user's "
                        "message using only the provided company, product, case study, CRM, OCR, and "
                        "agent evidence. Be practical, concise, and context-aware."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {"message": message, "context": context},
                        ensure_ascii=True,
                        indent=2,
                        default=str,
                    ),
                },
            ],
            temperature=0.2,
        )

        if result.get("error"):
            raise ServiceUnavailableException(
                message="Unable to generate the deal coach answer",
                details={"provider": result.get("provider"), "model": result.get("model"), "error": result.get("error")},
            )

        return result

    @staticmethod
    def _parse_json_object(content: str) -> Dict[str, Any]:
        content = (content or "").strip()
        if not content:
            return {}

        fenced_match = re.search(r"```(?:json)?\s*(.*?)\s*```", content, flags=re.IGNORECASE | re.DOTALL)
        if fenced_match:
            content = fenced_match.group(1).strip()

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            return {}

        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _serialize_value(value: Any) -> Any:
        if isinstance(value, Decimal):
            return str(value)
        return value
