import json
import os
import re
from decimal import Decimal
from typing import Any, Dict, List, Optional, Sequence

import requests
from pydantic import ValidationError

from common.exception.base_exception import (
    BadRequestException,
    GroqApiKeyMissingException,
    GroqDashboardJsonInvalidException,
    GroqModelNotFoundException,
    GroqPayloadTooLargeException,
    ServiceUnavailableException,
)
from features.callAgents.service import CallAgentsService
from features.companyAnalysis.schema import CompanyAnalysisResponseSchema
from features.companydata.service import CompanyDataService
from features.deals.service import DealService


class CompanyAnalysisService:
    MAX_AGENT_SIGNALS = 3
    MAX_MATCHES = 5
    MAX_OCR_EVIDENCE = 3
    MAX_TEXT_CHARS = 600

    @staticmethod
    def analyze(payload: Dict[str, Any], uploaded_files: Optional[Sequence[Any]] = None) -> Dict[str, Any]:
        context = CompanyAnalysisService._build_context(payload, uploaded_files=uploaded_files)
        CompanyAnalysisService._debug_print("compact_evidence_context", context)
        result = CompanyAnalysisService._call_dashboard_groq(context)
        CompanyAnalysisService._debug_print("groq_parsed_dashboard", result)
        result = CompanyAnalysisService._normalize_dashboard_result(result, context)
        result["company_name"] = result.get("company_name") or context["company_name"]
        CompanyAnalysisService._debug_print("normalized_dashboard", result)

        try:
            validated = CompanyAnalysisResponseSchema(**result)
        except ValidationError as exc:
            raise GroqDashboardJsonInvalidException(
                details={"error": "llm_dashboard_response_invalid", "validation_errors": exc.errors()},
            ) from exc

        response = validated.model_dump()
        CompanyAnalysisService._debug_print("validated_dashboard_response", response)
        return response

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
        CompanyAnalysisService._debug_print("deal_coach_context", context)

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
        raw_question = payload.get("question")
        question = (raw_question or "Create full company analysis dashboard").strip()
        documents = payload.get("documents") or payload.get("document_ids") or []
        if not isinstance(documents, list):
            raise BadRequestException("documents must be a list")

        ocr_extractions = CallAgentsService._extract_uploaded_documents(uploaded_files or [])
        company_data = CompanyAnalysisService._fetch_company_data()
        crm_deals = CompanyAnalysisService._fetch_crm_deals()
        agent_upstream = CallAgentsService._fetch_agent_response(
            account_id=account_id,
            company_name=company_name,
            website_url=website_url,
        )
        case_study_question = CompanyAnalysisService._build_case_study_rag_question(
            company_name=company_name,
            question=(raw_question or "").strip(),
            agent_upstream=agent_upstream,
        )
        CompanyAnalysisService._debug_print("case_study_rag_question", case_study_question)
        case_study_rag = CallAgentsService._fetch_case_study_rag_response(product_question=case_study_question)

        product_question = CompanyAnalysisService._build_product_rag_question(
            company_name=company_name,
            question=(raw_question or "").strip(),
            agent_upstream=agent_upstream,
            case_study_rag=case_study_rag,
        )
        CompanyAnalysisService._debug_print("product_rag_question", product_question)
        product_rag = CallAgentsService._fetch_product_rag_response(product_question=product_question)

        return {
            "company_name": company_name,
            "website_url": website_url,
            "user_question": question,
            "agent_signals": CompanyAnalysisService._extract_agent_signals(agent_upstream),
            "client_products": CompanyAnalysisService._extract_client_products(agent_upstream),
            "product_matches": CompanyAnalysisService._extract_matches(product_rag, "products"),
            "case_study_matches": CompanyAnalysisService._extract_matches(case_study_rag, "caseStudies"),
            "ocr_evidence": CompanyAnalysisService._extract_ocr_evidence(ocr_extractions),
            "company_data_summary": CompanyAnalysisService._summarize_company_data(company_data),
            "crm_deals_summary": CompanyAnalysisService._summarize_crm_deals(crm_deals),
        }

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
    def _dashboard_system_prompt() -> str:
        return (
            "You are a senior enterprise sales intelligence analyst for NovaChem. Return strict JSON only. "
            "Never invent facts, metrics, percentages, company goals, acquisitions, expansion plans, "
            "sustainability targets, or business initiatives. Every recommendation, prediction, score, and "
            "conclusion must be supported by evidence from the supplied context. Distinguish verified evidence "
            "from industry inference and AI prediction in the reason text. If fewer than two evidence points "
            "support strategic fit, set strategic_fit.score to null, alignment_level to insufficient_evidence, "
            "confidence to 0, and explanation to Insufficient evidence found. Strategic fit scoring weights are "
            "industry alignment 30%, sustainability alignment 25%, operational need alignment 25%, and digital "
            "transformation alignment 20%. Confidence scale: 90-100 multiple verified sources, 70-89 strong "
            "evidence, 50-69 partial evidence, 1-49 weak inference, 0 no evidence. Only predict AI needs when "
            "supported by evidence. Only recommend NovaChem solutions when there is a clear connection between "
            "company challenge or objective and product capability. solution_mapping may only use products in "
            "product_matches. Set deal_value to null unless CRM/opportunity evidence explicitly contains a deal "
            "value; product catalog price is not a deal value. Return exactly this shape: "
            "{\"company_name\":\"string\",\"strategic_fit\":{\"score\":null,\"alignment_level\":\"string\","
            "\"explanation\":\"string\",\"confidence\":0,\"evidence\":[{\"source\":\"string\","
            "\"finding\":\"string\"}]},\"meeting_prep\":{\"key_discussion_topics\":[\"string\"],"
            "\"business_priorities\":[\"string\"],\"executive_talking_points\":[\"string\"],"
            "\"potential_objections\":[\"string\"],\"recommended_agenda\":[\"string\"],"
            "\"qbr_summary\":\"string\"},\"intelligence_overview\":{\"company_overview\":\"string\","
            "\"industry_position\":\"string\",\"business_model\":\"string\",\"strategic_goals\":[\"string\"],"
            "\"expansion_initiatives\":[\"string\"],\"digital_transformation_efforts\":[\"string\"],"
            "\"sustainability_commitments\":[\"string\"]},\"ai_needs_prediction\":[{\"need\":\"string\","
            "\"confidence\":0,\"reason\":\"string\",\"evidence\":[{\"source\":\"string\","
            "\"finding\":\"string\"}]}],\"solution_mapping\":[{\"requirement\":\"string\","
            "\"novachem_solution\":\"string\",\"match_percent\":0,\"deal_value\":null,\"reason\":\"string\","
            "\"confidence\":0,\"evidence\":[{\"source\":\"string\",\"finding\":\"string\"}]}]}."
        )

    @staticmethod
    def _call_dashboard_groq(context: Dict[str, Any]) -> Dict[str, Any]:
        result = CompanyAnalysisService._call_groq_chat(
            messages=[
                {"role": "system", "content": CompanyAnalysisService._dashboard_system_prompt()},
                {"role": "user", "content": json.dumps(context, ensure_ascii=True, indent=2, default=str)},
            ],
            temperature=0.2,
        )

        CompanyAnalysisService._debug_print("groq_raw_dashboard_content", result.get("content") or "")
        parsed = CompanyAnalysisService._parse_json_object(result.get("content") or "")
        if not parsed:
            raise GroqDashboardJsonInvalidException(
                details={
                    "provider": result.get("provider"),
                    "model": result.get("model"),
                    "error": "groq_dashboard_json_missing",
                },
            )
        return parsed

    @staticmethod
    def _call_deal_coach_groq(context: Dict[str, Any], message: str) -> Dict[str, Any]:
        return CompanyAnalysisService._call_groq_chat(
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

    @staticmethod
    def _normalize_dashboard_result(result: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(result, dict):
            result = {}
        return {
            "company_name": CompanyAnalysisService._text_or_default(result.get("company_name"), context.get("company_name") or "Unknown company"),
            "strategic_fit": CompanyAnalysisService._normalize_strategic_fit(result.get("strategic_fit"), context),
            "meeting_prep": CompanyAnalysisService._normalize_meeting_prep(result.get("meeting_prep")),
            "intelligence_overview": CompanyAnalysisService._normalize_intelligence_overview(result.get("intelligence_overview")),
            "ai_needs_prediction": CompanyAnalysisService._normalize_needs_prediction(result.get("ai_needs_prediction"), context),
            "solution_mapping": CompanyAnalysisService._normalize_solution_mapping(result.get("solution_mapping"), context),
        }

    @staticmethod
    def _normalize_strategic_fit(value: Any, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        context = context or {}
        evidence = CompanyAnalysisService._strategic_fit_evidence(context)
        if len(evidence) < 2:
            return {
                "score": None,
                "alignment_level": "insufficient_evidence",
                "explanation": "Insufficient evidence found",
                "confidence": 0,
                "evidence": evidence,
            }

        if isinstance(value, dict):
            raw_score = value.get("score") or value.get("strategic_fit_score") or value.get("fit_score") or value.get("percentage")
            score = CompanyAnalysisService._percent(raw_score, default=0) if raw_score not in (None, "") else CompanyAnalysisService._infer_strategic_fit_score(value, context)
            alignment_level = CompanyAnalysisService._text_or_default(value.get("alignment_level") or value.get("alignment") or value.get("level"), CompanyAnalysisService._alignment_level(score))
            explanation = CompanyAnalysisService._text_or_default(
                value.get("explanation") or value.get("reason") or value.get("summary") or CompanyAnalysisService._truthy_flag_explanation(value),
                CompanyAnalysisService._default_strategic_fit_explanation(score, context),
            )
            confidence = CompanyAnalysisService._percent(value.get("confidence") or value.get("confidence_score"), default=CompanyAnalysisService._confidence_from_evidence_count(len(evidence)))
            evidence = CompanyAnalysisService._normalize_evidence_items(value.get("evidence")) or evidence
        else:
            score = CompanyAnalysisService._percent(value, default=0)
            alignment_level = CompanyAnalysisService._alignment_level(score)
            explanation = "Strategic fit score was estimated from the available LLM analysis."
            confidence = CompanyAnalysisService._confidence_from_evidence_count(len(evidence))
        return {"score": score, "alignment_level": alignment_level, "explanation": explanation, "confidence": confidence, "evidence": evidence}

    @staticmethod
    def _normalize_meeting_prep(value: Any) -> Dict[str, Any]:
        if isinstance(value, dict):
            topics = (
                CompanyAnalysisService._string_list(value.get("key_discussion_topics") or value.get("key_topics"))
                or CompanyAnalysisService._collect_nested_key_strings(value, {"topics", "topic", "key_discussion_topics", "key_topics"})
                or CompanyAnalysisService._string_list(value)
            )
            questions = CompanyAnalysisService._collect_nested_key_strings(value, {"questions", "question"})
            priorities = (
                CompanyAnalysisService._string_list(value.get("business_priorities"))
                or CompanyAnalysisService._collect_nested_key_strings(value, {"business_priorities", "priorities"})
            )
            talking_points = CompanyAnalysisService._string_list(value.get("executive_talking_points")) or questions
            agenda = CompanyAnalysisService._string_list(value.get("recommended_agenda")) or CompanyAnalysisService._agenda_from_topics(topics)
            return {
                "key_discussion_topics": topics,
                "business_priorities": priorities,
                "executive_talking_points": talking_points,
                "potential_objections": CompanyAnalysisService._string_list(value.get("potential_objections")),
                "recommended_agenda": agenda,
                "qbr_summary": CompanyAnalysisService._text_or_default(
                    value.get("qbr_summary") or value.get("summary") or CompanyAnalysisService._meeting_summary(topics, questions),
                    "Insufficient evidence to generate a QBR summary.",
                ),
            }
        discussion_topics = CompanyAnalysisService._string_list(value)
        return {
            "key_discussion_topics": discussion_topics,
            "business_priorities": [],
            "executive_talking_points": [],
            "potential_objections": [],
            "recommended_agenda": [],
            "qbr_summary": "Meeting preparation was derived from available signals." if discussion_topics else "Insufficient evidence to generate a QBR summary.",
        }

    @staticmethod
    def _normalize_intelligence_overview(value: Any) -> Dict[str, Any]:
        if isinstance(value, dict):
            return {
                "company_overview": CompanyAnalysisService._text_or_default(value.get("company_overview") or value.get("overview") or value.get("summary"), "Insufficient evidence."),
                "industry_position": CompanyAnalysisService._text_or_default(value.get("industry_position") or value.get("industry"), "Insufficient evidence."),
                "business_model": CompanyAnalysisService._text_or_default(value.get("business_model") or value.get("model"), "Insufficient evidence."),
                "strategic_goals": CompanyAnalysisService._string_list(value.get("strategic_goals") or value.get("key_points")),
                "expansion_initiatives": CompanyAnalysisService._string_list(value.get("expansion_initiatives")),
                "digital_transformation_efforts": CompanyAnalysisService._string_list(value.get("digital_transformation_efforts")),
                "sustainability_commitments": CompanyAnalysisService._string_list(value.get("sustainability_commitments")),
            }
        return {
            "company_overview": CompanyAnalysisService._text_or_default(value, "Insufficient evidence."),
            "industry_position": "Insufficient evidence.",
            "business_model": "Insufficient evidence.",
            "strategic_goals": [],
            "expansion_initiatives": [],
            "digital_transformation_efforts": [],
            "sustainability_commitments": [],
        }

    @staticmethod
    def _normalize_needs_prediction(value: Any, context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        if not isinstance(value, list):
            return []
        needs = []
        for item in value[:CompanyAnalysisService.MAX_MATCHES]:
            if isinstance(item, str):
                continue
            if isinstance(item, dict):
                need = CompanyAnalysisService._text_or_default(item.get("need") or item.get("title") or item.get("signal") or item.get("requirement"), "Unspecified need")
                confidence = CompanyAnalysisService._percent(item.get("confidence") or item.get("confidence_score") or item.get("score"), default=0)
                if confidence <= 0:
                    continue
                evidence = CompanyAnalysisService._normalize_evidence_items(item.get("evidence")) or CompanyAnalysisService._need_evidence(need, context or {})
                if not evidence:
                    continue
                needs.append({
                    "need": need,
                    "confidence": confidence,
                    "reason": CompanyAnalysisService._text_or_default(item.get("reason") or item.get("description") or CompanyAnalysisService._need_reason(need, context or {}), "Insufficient evidence."),
                    "evidence": evidence,
                })
        return needs

    @staticmethod
    def _normalize_solution_mapping(value: Any, context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        context = context or {}
        if not isinstance(value, list):
            value = []
        mappings = []
        product_lookup = CompanyAnalysisService._product_match_lookup(context)
        seen = set()
        for item in value[:CompanyAnalysisService.MAX_MATCHES]:
            if not isinstance(item, dict):
                continue
            product = CompanyAnalysisService._lookup_mapping_product(item, product_lookup)
            if not product or not CompanyAnalysisService._product_allowed_by_company_evidence(product, context):
                continue
            solution = CompanyAnalysisService._product_display_name(product)
            normalized_solution = CompanyAnalysisService._normalize_lookup_key(solution)
            if normalized_solution in seen:
                continue
            seen.add(normalized_solution)
            reason = CompanyAnalysisService._mapping_reason_from_item(item, product, context)
            mappings.append({
                "requirement": CompanyAnalysisService._text_or_default(item.get("requirement") or item.get("need") or item.get("category") or CompanyAnalysisService._product_requirement(product), solution),
                "novachem_solution": solution,
                "match_percent": CompanyAnalysisService._normalized_mapping_match_percent(item, product, context),
                "deal_value": CompanyAnalysisService._supported_deal_value(item.get("deal_value"), context),
                "reason": reason,
                "confidence": CompanyAnalysisService._mapping_confidence(item, product, context),
                "evidence": CompanyAnalysisService._mapping_evidence(product, context),
            })
        return CompanyAnalysisService._append_fallback_solution_mappings(context, mappings, seen)

    @staticmethod
    def _context_supports_deal_values(context: Dict[str, Any]) -> bool:
        return CompanyAnalysisService._contains_deal_value_evidence(context.get("crm_deals_summary"))

    @staticmethod
    def _contains_deal_value_evidence(value: Any) -> bool:
        evidence_keys = {"deal_value", "estimated_deal_value", "contract_value", "opportunity_value", "value", "amount", "budget"}
        if isinstance(value, dict):
            for key, item in value.items():
                if key in evidence_keys and CompanyAnalysisService._optional_text(item):
                    return True
                if CompanyAnalysisService._contains_deal_value_evidence(item):
                    return True
            return False
        if isinstance(value, list):
            return any(CompanyAnalysisService._contains_deal_value_evidence(item) for item in value)
        return False

    @staticmethod
    def _infer_strategic_fit_score(value: Dict[str, Any], context: Dict[str, Any]) -> int:
        truthy_flags = [key for key, item in value.items() if isinstance(item, bool) and item]
        if truthy_flags:
            evidence_bonus = 0
            for key in ("agent_signals", "product_matches", "case_study_matches", "client_products"):
                if context.get(key):
                    evidence_bonus += 5
            return min(85, 55 + (len(truthy_flags) * 10) + evidence_bonus)

        if context.get("agent_signals") and context.get("product_matches"):
            return 70
        if context.get("agent_signals") or context.get("product_matches"):
            return 50
        return 0

    @staticmethod
    def _truthy_flag_explanation(value: Dict[str, Any]) -> str:
        flags = [
            key.replace("_", " ")
            for key, item in value.items()
            if isinstance(item, bool) and item
        ]
        if not flags:
            return ""
        return f"Available analysis indicates {', '.join(flags[:CompanyAnalysisService.MAX_MATCHES])} alignment signals."

    @staticmethod
    def _default_strategic_fit_explanation(score: int, context: Dict[str, Any]) -> str:
        if score <= 0:
            return "Insufficient evidence to explain strategic fit."
        evidence = []
        if context.get("agent_signals"):
            evidence.append("company signals")
        if context.get("product_matches"):
            evidence.append("retrieved product matches")
        if context.get("case_study_matches"):
            evidence.append("case-study evidence")
        if not evidence:
            return "Strategic fit was estimated from available analysis."
        return f"Strategic fit is supported by {', '.join(evidence[:CompanyAnalysisService.MAX_MATCHES])}."

    @staticmethod
    def _collect_nested_key_strings(value: Any, keys: set[str]) -> List[str]:
        items = []

        def collect(current: Any) -> None:
            if len(items) >= CompanyAnalysisService.MAX_MATCHES:
                return
            if isinstance(current, dict):
                for key, item in current.items():
                    normalized_key = str(key).strip().lower()
                    if normalized_key in keys:
                        for text in CompanyAnalysisService._string_list(item):
                            if text and text not in items:
                                items.append(text)
                            if len(items) >= CompanyAnalysisService.MAX_MATCHES:
                                return
                    collect(item)
            elif isinstance(current, list):
                for item in current:
                    collect(item)
                    if len(items) >= CompanyAnalysisService.MAX_MATCHES:
                        return

        collect(value)
        return items[:CompanyAnalysisService.MAX_MATCHES]

    @staticmethod
    def _agenda_from_topics(topics: List[str]) -> List[str]:
        return [f"Discuss {topic}" for topic in topics[:3]]

    @staticmethod
    def _meeting_summary(topics: List[str], questions: List[str]) -> str:
        if topics:
            return f"Meeting prep should focus on {', '.join(topics[:3])}."
        if questions:
            return f"Meeting prep should address {', '.join(questions[:2])}."
        return ""

    @staticmethod
    def _need_reason(need: str, context: Dict[str, Any]) -> str:
        signal = CompanyAnalysisService._first_evidence_summary(context.get("agent_signals"))
        if signal:
            return f"Supported by company signal: {signal}"
        product = CompanyAnalysisService._first_evidence_summary(context.get("product_matches"))
        if product:
            return f"Supported by retrieved product evidence: {product}"
        case_study = CompanyAnalysisService._first_evidence_summary(context.get("case_study_matches"))
        if case_study:
            return f"Supported by case-study evidence: {case_study}"
        return "Insufficient evidence."

    @staticmethod
    def _first_evidence_summary(value: Any) -> str:
        if isinstance(value, list):
            for item in value:
                text = CompanyAnalysisService._first_evidence_summary(item)
                if text:
                    return text
            return ""
        if isinstance(value, dict):
            for key in ("title", "summary", "productName", "product_name", "name", "category", "challenge", "description"):
                text = CompanyAnalysisService._truncate_text(value.get(key))
                if text and text.lower() not in {"none", "n/a", "insufficient evidence"}:
                    return text
        return ""

    @staticmethod
    def _product_match_lookup(context: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        lookup = {}
        for product in context.get("product_matches") or []:
            if not isinstance(product, dict) or product.get("error") or product.get("skipped"):
                continue
            for key in ("productName", "product_name", "name", "title", "productId", "product_id"):
                value = CompanyAnalysisService._truncate_text(product.get(key))
                normalized = CompanyAnalysisService._normalize_lookup_key(value)
                if normalized:
                    lookup[normalized] = product
        return lookup

    @staticmethod
    def _lookup_mapping_product(item: Dict[str, Any], product_lookup: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        for key in ("novachem_solution", "product_name", "productName", "name", "title", "product_id", "productId"):
            normalized = CompanyAnalysisService._normalize_lookup_key(item.get(key))
            if normalized and normalized in product_lookup:
                return product_lookup[normalized]
        return None

    @staticmethod
    def _fallback_solution_mappings(context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return CompanyAnalysisService._append_fallback_solution_mappings(context, [], set())

    @staticmethod
    def _append_fallback_solution_mappings(context: Dict[str, Any], mappings: List[Dict[str, Any]], seen: set[str]) -> List[Dict[str, Any]]:
        products = [
            product
            for product in (context.get("product_matches") or [])
            if isinstance(product, dict)
            and not product.get("error")
            and not product.get("skipped")
            and CompanyAnalysisService._product_display_name(product)
            and CompanyAnalysisService._product_allowed_by_company_evidence(product, context)
        ]
        case_study_products = CompanyAnalysisService._case_study_product_names_from_context(context)
        products.sort(
            key=lambda product: (
                CompanyAnalysisService._normalize_lookup_key(CompanyAnalysisService._product_display_name(product)) not in case_study_products,
                CompanyAnalysisService._product_display_name(product),
            )
        )

        for product in products:
            if len(mappings) >= CompanyAnalysisService.MAX_MATCHES:
                break
            solution = CompanyAnalysisService._product_display_name(product)
            normalized = CompanyAnalysisService._normalize_lookup_key(solution)
            if normalized in seen:
                continue
            seen.add(normalized)
            mappings.append({
                "requirement": CompanyAnalysisService._product_requirement(product),
                "novachem_solution": solution,
                "match_percent": CompanyAnalysisService._fallback_match_percent(product, context),
                "deal_value": None,
                "reason": CompanyAnalysisService._mapping_reason(product, context),
            })
        return mappings

    @staticmethod
    def _product_allowed_by_company_evidence(product: Dict[str, Any], context: Dict[str, Any]) -> bool:
        product_text = CompanyAnalysisService._flatten_text(product).casefold()
        evidence_text = CompanyAnalysisService._company_evidence_text(context)
        water_product_terms = {"water", "wastewater", "aqua", "hydro", "membrane"}
        water_evidence_terms = {"water", "wastewater", "utility", "utilities", "beverage", "bottling", "hydro"}
        emissions_product_terms = {"voc", "emission", "emissions", "airguard", "air guard"}
        emissions_evidence_terms = {"voc", "emission", "emissions", "air quality", "compliance"}
        carbon_product_terms = {"carbon", "net-zero", "net zero"}
        carbon_evidence_terms = {"carbon", "net-zero", "net zero", "emission", "emissions", "sustainability", "esg"}

        if CompanyAnalysisService._contains_any(product_text, water_product_terms):
            return CompanyAnalysisService._contains_any(evidence_text, water_evidence_terms)
        if CompanyAnalysisService._contains_any(product_text, emissions_product_terms):
            return CompanyAnalysisService._contains_any(evidence_text, emissions_evidence_terms)
        if CompanyAnalysisService._contains_any(product_text, carbon_product_terms):
            return CompanyAnalysisService._contains_any(evidence_text, carbon_evidence_terms)
        return True

    @staticmethod
    def _contains_any(text: str, terms: set[str]) -> bool:
        return any(term in text for term in terms)

    @staticmethod
    def _company_evidence_text(context: Dict[str, Any]) -> str:
        return CompanyAnalysisService._flatten_text({
            "agent_signals": context.get("agent_signals"),
            "client_products": context.get("client_products"),
            "ocr_evidence": context.get("ocr_evidence"),
            "company_data_summary": context.get("company_data_summary"),
        }).casefold()

    @staticmethod
    def _flatten_text(value: Any) -> str:
        if isinstance(value, str):
            return value
        try:
            return json.dumps(value, ensure_ascii=True, default=str)
        except TypeError:
            return str(value)

    @staticmethod
    def _product_display_name(product: Dict[str, Any]) -> str:
        for key in ("productName", "product_name", "name", "title"):
            text = CompanyAnalysisService._truncate_text(product.get(key))
            if text:
                return text
        return CompanyAnalysisService._truncate_text(product.get("productId") or product.get("product_id"))

    @staticmethod
    def _product_requirement(product: Dict[str, Any]) -> str:
        for key in ("application", "category", "esgImpact", "description"):
            text = CompanyAnalysisService._truncate_text(product.get(key))
            if text:
                return text
        return CompanyAnalysisService._product_display_name(product)

    @staticmethod
    def _fallback_match_percent(product: Dict[str, Any], context: Dict[str, Any]) -> int:
        name = CompanyAnalysisService._normalize_lookup_key(CompanyAnalysisService._product_display_name(product))
        if name and name in CompanyAnalysisService._case_study_product_names_from_context(context):
            return 90
        if CompanyAnalysisService._product_allowed_by_company_evidence(product, context):
            return 75
        return 0

    @staticmethod
    def _normalized_mapping_match_percent(item: Dict[str, Any], product: Dict[str, Any], context: Dict[str, Any]) -> int:
        raw_value = item.get("match_percent") or item.get("match") or item.get("score") or item.get("confidence")
        score = CompanyAnalysisService._percent(raw_value, default=CompanyAnalysisService._fallback_match_percent(product, context))
        if score < 95:
            return score

        solution = CompanyAnalysisService._product_display_name(product)
        if CompanyAnalysisService._case_study_titles_for_product(solution, context):
            return min(score, 90)
        return min(score, 85)

    @staticmethod
    def _mapping_reason(product: Dict[str, Any], context: Dict[str, Any]) -> str:
        solution = CompanyAnalysisService._product_display_name(product)
        product_summary = CompanyAnalysisService._truncate_text(product.get("description") or product.get("application") or product.get("category")).rstrip(".")
        case_study_titles = CompanyAnalysisService._case_study_titles_for_product(solution, context)
        if case_study_titles and product_summary:
            return f"Retrieved product match: {product_summary}. Prioritized by case-study evidence: {case_study_titles[0]}."
        if case_study_titles:
            return f"Retrieved product match also appears in case-study evidence: {case_study_titles[0]}."
        if product_summary:
            return f"Retrieved product match: {product_summary}."
        return "Matched from retrieved product evidence."

    @staticmethod
    def _mapping_reason_from_item(item: Dict[str, Any], product: Dict[str, Any], context: Dict[str, Any]) -> str:
        raw_reason = item.get("reason") or item.get("description")
        if CompanyAnalysisService._is_negative_evidence_reason(raw_reason) or CompanyAnalysisService._is_generic_mapping_reason(raw_reason):
            raw_reason = None
        fallback_reason = CompanyAnalysisService._mapping_reason(product, context)
        return CompanyAnalysisService._text_or_default(raw_reason or fallback_reason, fallback_reason)

    @staticmethod
    def _is_negative_evidence_reason(value: Any) -> bool:
        text = CompanyAnalysisService._truncate_text(value).casefold()
        if not text:
            return False
        negative_phrases = {
            "no evidence",
            "no direct evidence",
            "no available evidence",
            "no evidence found",
            "insufficient evidence",
            "not enough evidence",
            "cannot map",
            "can't map",
            "unable to map",
        }
        return any(phrase in text for phrase in negative_phrases)

    @staticmethod
    def _is_generic_mapping_reason(value: Any) -> bool:
        text = CompanyAnalysisService._truncate_text(value).casefold()
        if not text:
            return False
        normalized = CompanyAnalysisService._normalize_lookup_key(text)
        generic_exact = {"matched to evidence", "product evidence", "case study evidence", "matched from available evidence"}
        if normalized in generic_exact:
            return True
        generic_patterns = [
            r"\bmatches\b.+\bneeds?\b",
            r"\bmatch(es|ed)?\b.+\brequirements?\b",
            r"\bcan help\b.+\bneeds?\b",
        ]
        return any(re.search(pattern, text) for pattern in generic_patterns)

    @staticmethod
    def _supported_deal_value(value: Any, context: Dict[str, Any]) -> Optional[str]:
        text = CompanyAnalysisService._optional_text(value)
        if not text or not CompanyAnalysisService._context_supports_deal_values(context):
            return None
        crm_text = CompanyAnalysisService._normalize_lookup_key(CompanyAnalysisService._flatten_text(context.get("crm_deals_summary")))
        return text if CompanyAnalysisService._normalize_lookup_key(text) in crm_text else None

    @staticmethod
    def _case_study_product_names_from_context(context: Dict[str, Any]) -> set[str]:
        names = set()
        for case_study in context.get("case_study_matches") or []:
            if not isinstance(case_study, dict):
                continue
            for product in case_study.get("productsUsed") or []:
                normalized = CompanyAnalysisService._normalize_lookup_key(product)
                if normalized:
                    names.add(normalized)
        return names

    @staticmethod
    def _case_study_titles_for_product(product_name: str, context: Dict[str, Any]) -> List[str]:
        normalized_product = CompanyAnalysisService._normalize_lookup_key(product_name)
        titles = []
        for case_study in context.get("case_study_matches") or []:
            if not isinstance(case_study, dict):
                continue
            product_names = {
                CompanyAnalysisService._normalize_lookup_key(product)
                for product in (case_study.get("productsUsed") or [])
            }
            if normalized_product in product_names:
                title = CompanyAnalysisService._truncate_text(case_study.get("title"))
                if title:
                    titles.append(title)
        return titles[:CompanyAnalysisService.MAX_MATCHES]

    @staticmethod
    def _normalize_lookup_key(value: Any) -> str:
        text = CompanyAnalysisService._truncate_text(value).casefold()
        return re.sub(r"[^a-z0-9]+", " ", text).strip()

    @staticmethod
    def _build_rag_question(company_name: str, question: str) -> str:
        if question:
            return f"{question} for {company_name}"
        return f"Find NovaChem products and case studies relevant to {company_name}"

    @staticmethod
    def _build_case_study_rag_question(company_name: str, question: str, agent_upstream: Dict[str, Any]) -> str:
        signal_text = CompanyAnalysisService._signal_search_text(agent_upstream)
        base_question = f"{question} for {company_name}" if question else f"Find NovaChem case studies relevant to {company_name}"
        parts = [f"{base_question}.", "Find case studies with the same client, industry, business challenges, or sustainability/manufacturing signals."]
        if signal_text:
            parts.append(f"Company signals: {signal_text}.")
        return " ".join(parts)

    @staticmethod
    def _build_product_rag_question(company_name: str, question: str, agent_upstream: Dict[str, Any], case_study_rag: Dict[str, Any]) -> str:
        signal_text = CompanyAnalysisService._signal_search_text(agent_upstream)
        case_study_products = CompanyAnalysisService._case_study_product_terms(case_study_rag)
        client_products = CompanyAnalysisService._extract_client_products(agent_upstream)
        base_question = f"{question} for {company_name}" if question else f"Find NovaChem products relevant to {company_name}"
        parts = [
            f"{base_question}.",
            "Find NovaChem products that match explicit company needs, industry, sustainability signals, or matched case-study products.",
            "Avoid generic utilities or water-treatment products unless water, utilities, wastewater, or monitoring evidence is present.",
        ]
        if signal_text:
            parts.append(f"Company signals: {signal_text}.")
        if case_study_products:
            parts.append(f"Matched case-study products to prioritize: {', '.join(case_study_products)}.")
        if client_products:
            parts.append(f"Client's specific products/services to map against: {', '.join(client_products)}.")
        return " ".join(parts)

    @staticmethod
    def _signal_search_text(agent_upstream: Dict[str, Any]) -> str:
        signals = CompanyAnalysisService._extract_agent_signals(agent_upstream)
        phrases = []
        for signal in signals[:CompanyAnalysisService.MAX_AGENT_SIGNALS]:
            if not isinstance(signal, dict):
                continue
            text = " ".join(str(signal.get(key) or "").strip() for key in ("type", "title", "summary", "intent", "source_type") if signal.get(key))
            if text:
                phrases.append(CompanyAnalysisService._truncate_text(text))
        return " | ".join(phrases)

    @staticmethod
    def _case_study_product_terms(case_study_rag: Dict[str, Any]) -> List[str]:
        if not isinstance(case_study_rag, dict):
            return []
        products = []
        seen = set()
        for case_study in (case_study_rag.get("caseStudies") or [])[:CompanyAnalysisService.MAX_MATCHES]:
            if not isinstance(case_study, dict):
                continue
            for product in case_study.get("productsUsed") or []:
                product_name = str(product or "").strip()
                normalized = product_name.casefold()
                if product_name and normalized not in seen:
                    products.append(product_name)
                    seen.add(normalized)
        return products[:CompanyAnalysisService.MAX_MATCHES]

    @staticmethod
    def _extract_agent_signals(agent_upstream: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not isinstance(agent_upstream, dict):
            return []
        signals = []
        seen = set()
        for signal in agent_upstream.get("signals") or []:
            if not isinstance(signal, dict) or not CompanyAnalysisService._agent_signal_is_useful(signal):
                continue
            signal_summary = CompanyAnalysisService._truncate_value(signal)
            signal_key = CompanyAnalysisService._normalize_lookup_key(
                f"{signal_summary.get('type')} {signal_summary.get('title')} {signal_summary.get('summary')}"
            )
            if signal_key and signal_key not in seen:
                signals.append(signal_summary)
                seen.add(signal_key)

        for signal in CompanyAnalysisService._derive_profile_signals(agent_upstream):
            signal_key = CompanyAnalysisService._normalize_lookup_key(f"{signal.get('type')} {signal.get('title')}")
            if signal_key and signal_key not in seen:
                signals.append(signal)
                seen.add(signal_key)

        if signals:
            return signals[:CompanyAnalysisService.MAX_AGENT_SIGNALS]

        return [
            {"source_type": source.get("source_type"), "status": source.get("status"), "content": CompanyAnalysisService._truncate_text(source.get("content"))}
            for source in (agent_upstream.get("sources") or [])[:CompanyAnalysisService.MAX_AGENT_SIGNALS]
            if isinstance(source, dict) and CompanyAnalysisService._source_is_useful(source)
        ]

    @staticmethod
    def _agent_signal_is_useful(signal: Dict[str, Any]) -> bool:
        text = CompanyAnalysisService._flatten_text({
            "type": signal.get("type"),
            "title": signal.get("title"),
            "summary": signal.get("summary"),
            "intent": signal.get("intent"),
            "source_type": signal.get("source_type"),
        })
        if CompanyAnalysisService._is_noisy_agent_text(text):
            return False
        business_terms = {
            "paint",
            "paints",
            "coating",
            "coatings",
            "waterproof",
            "water",
            "wastewater",
            "conservation",
            "utility",
            "utilities",
            "wood",
            "interior",
            "exterior",
            "sustainability",
            "manufacturing",
            "industrial",
            "protective",
            "revenue",
            "profit",
            "margin",
            "demand",
            "cost",
            "growth",
            "expansion",
            "compliance",
            "supply chain",
        }
        return CompanyAnalysisService._contains_any(text.casefold(), business_terms)

    @staticmethod
    def _source_is_useful(source: Dict[str, Any]) -> bool:
        if source.get("status") and str(source.get("status")).lower() != "ok":
            return False
        content = CompanyAnalysisService._truncate_text(source.get("content"))
        return bool(content) and not CompanyAnalysisService._is_noisy_agent_text(content)

    @staticmethod
    def _is_noisy_agent_text(value: Any) -> bool:
        text = CompanyAnalysisService._truncate_text(value).casefold()
        if not text:
            return True
        noisy_phrases = {
            "go to homepage",
            "recently viewed",
            "book of colours",
            "jobs people learning",
            "clear text",
            "couldn",
            "find a match",
            "access denied",
            "page does not exist",
            "resource at",
            "not found",
            "apache sling",
            "uzbekistan vs colombia",
            "iraq vs norway",
            "world cup",
            "linkedin is better on the app",
            "agree & join linkedin",
            "forgot password",
        }
        return any(phrase in text for phrase in noisy_phrases)

    @staticmethod
    def _derive_profile_signals(agent_upstream: Dict[str, Any]) -> List[Dict[str, Any]]:
        company_profile = agent_upstream.get("company_profile") or {}
        if not isinstance(company_profile, dict):
            return []

        company_name = CompanyAnalysisService._truncate_text(
            company_profile.get("company_name") or agent_upstream.get("company_name") or "Company"
        )
        products = CompanyAnalysisService._extract_client_products(agent_upstream)
        source_url = CompanyAnalysisService._profile_source_url(company_profile)
        confidence = CompanyAnalysisService._percent(company_profile.get("confidence_score"), default=80)
        signals = []

        if products:
            product_summary = ", ".join(products[:CompanyAnalysisService.MAX_MATCHES])
            signals.append({
                "type": "product_line",
                "title": f"{company_name} product and service portfolio",
                "summary": f"{company_name} offers {product_summary}.",
                "intent": "solution_fit",
                "impact_score": 85,
                "priority": "high",
                "confidence_score": confidence / 100,
                "source_type": "website",
                "source_url": source_url,
            })

        waterproof_products = [product for product in products if "waterproof" in product.casefold()]
        if waterproof_products:
            signals.append({
                "type": "waterproofing_solution_fit",
                "title": f"{company_name} lists waterproofing offerings",
                "summary": f"Company profile lists waterproofing offerings: {', '.join(waterproof_products[:3])}.",
                "intent": "solution_fit",
                "impact_score": 85,
                "priority": "high",
                "confidence_score": confidence / 100,
                "source_type": "website",
                "source_url": source_url,
            })

        description = CompanyAnalysisService._truncate_text(company_profile.get("description"))
        if description and not CompanyAnalysisService._is_noisy_agent_text(description):
            signals.append({
                "type": "company_profile",
                "title": f"{company_name} company profile",
                "summary": description,
                "intent": "context",
                "impact_score": 70,
                "priority": "medium",
                "confidence_score": confidence / 100,
                "source_type": "website",
                "source_url": source_url,
            })

        return signals[:CompanyAnalysisService.MAX_AGENT_SIGNALS]

    @staticmethod
    def _profile_source_url(company_profile: Dict[str, Any]) -> str:
        if company_profile.get("website"):
            return CompanyAnalysisService._truncate_text(company_profile.get("website"))
        source_urls = company_profile.get("source_urls") or []
        if isinstance(source_urls, list) and source_urls:
            return CompanyAnalysisService._truncate_text(source_urls[0])
        return ""

    @staticmethod
    def _extract_client_products(agent_upstream: Dict[str, Any]) -> List[str]:
        if not isinstance(agent_upstream, dict):
            return []

        company_profile = agent_upstream.get("company_profile") or {}
        if not isinstance(company_profile, dict):
            return []

        products = []
        for key in ("products", "services"):
            items = company_profile.get(key) or []
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        name = item.get("name")
                        if name and isinstance(name, str) and CompanyAnalysisService._profile_item_is_useful(name):
                            products.append(name.strip())
                    elif isinstance(item, str):
                        if CompanyAnalysisService._profile_item_is_useful(item):
                            products.append(item.strip())

        seen = set()
        unique_products = []
        for prod in products:
            if not prod:
                continue
            lower_prod = prod.lower()
            if lower_prod not in seen:
                seen.add(lower_prod)
                unique_products.append(CompanyAnalysisService._truncate_text(prod))

        return unique_products[:CompanyAnalysisService.MAX_MATCHES * 2]

    @staticmethod
    def _profile_item_is_useful(value: Any) -> bool:
        text = CompanyAnalysisService._truncate_text(value)
        normalized = CompanyAnalysisService._normalize_lookup_key(text)
        if not normalized or len(normalized) < 4:
            return False
        noisy_terms = {
            "featured products",
            "everything a home needs",
            "share share",
            "product catalog",
            "browse our",
            "select country",
            "own a custom shade",
            "visualise",
            "designer collections",
            "what our",
            "clients say",
            "with our diverse",
            "shape your dream",
            "go to homepage",
            "recently viewed",
            "view all",
            "sitemap",
            "faqs",
            "find a store",
            "trusted brand",
            "how does",
            "how can i",
            "public notice",
        }
        if any(term in normalized for term in noisy_terms):
            return False
        useful_terms = {
            "paint",
            "paints",
            "texture",
            "textures",
            "wallpaper",
            "wallpapers",
            "waterproof",
            "wood",
            "kitchen",
            "bath",
            "decor",
            "interior",
            "exterior",
            "service",
            "services",
            "solution",
            "solutions",
            "coating",
            "coatings",
        }
        return CompanyAnalysisService._contains_any(normalized, useful_terms)

    @staticmethod
    def _extract_matches(rag_payload: Dict[str, Any], key: str) -> List[Dict[str, Any]]:
        if not isinstance(rag_payload, dict):
            return []
        if rag_payload.get("error"):
            return [{"error": rag_payload.get("error"), "service_url": rag_payload.get("service_url")}]
        if rag_payload.get("skipped"):
            return [{"skipped": rag_payload.get("skipped")}]
        return [CompanyAnalysisService._truncate_value(item) for item in (rag_payload.get(key) or [])[:CompanyAnalysisService.MAX_MATCHES] if isinstance(item, dict)]

    @staticmethod
    def _extract_ocr_evidence(ocr_extractions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        evidence = []
        for extraction in ocr_extractions[:CompanyAnalysisService.MAX_OCR_EVIDENCE]:
            extracted = extraction.get("extracted") if isinstance(extraction, dict) else None
            evidence.append({"file": extraction.get("file"), "content_type": extraction.get("content_type"), "text": CompanyAnalysisService._extract_text(extracted)})
        return evidence

    @staticmethod
    def _summarize_company_data(company_data: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(company_data, dict):
            return {}
        if company_data.get("error"):
            return {"error": company_data.get("error")}
        summary = {}
        for collection_name, records in company_data.items():
            if isinstance(records, list):
                summary[collection_name] = {"count": len(records), "sample": [CompanyAnalysisService._truncate_value(record) for record in records[:2] if isinstance(record, dict)]}
        return summary

    @staticmethod
    def _summarize_crm_deals(crm_deals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [CompanyAnalysisService._truncate_value(deal) for deal in (crm_deals or [])[:CompanyAnalysisService.MAX_MATCHES] if isinstance(deal, dict)]

    @staticmethod
    def _extract_text(value: Any) -> str:
        if isinstance(value, dict):
            for key in ("text", "content", "raw"):
                if key in value:
                    return CompanyAnalysisService._truncate_text(value.get(key))
            return CompanyAnalysisService._truncate_text(json.dumps(value, ensure_ascii=True, default=str))
        return CompanyAnalysisService._truncate_text(value)

    @staticmethod
    def _truncate_value(value: Any) -> Any:
        if isinstance(value, str):
            return CompanyAnalysisService._truncate_text(value)
        if isinstance(value, list):
            return [CompanyAnalysisService._truncate_value(item) for item in value[:CompanyAnalysisService.MAX_MATCHES]]
        if isinstance(value, dict):
            return {key: CompanyAnalysisService._truncate_value(item) for key, item in value.items() if key not in {"source_chunks", "sources", "raw"}}
        return value

    @staticmethod
    def _truncate_text(value: Any) -> str:
        text = str(value or "").strip()
        if len(text) <= CompanyAnalysisService.MAX_TEXT_CHARS:
            return text
        return f"{text[:CompanyAnalysisService.MAX_TEXT_CHARS].rstrip()}..."

    @staticmethod
    def _text_or_default(value: Any, default: str) -> str:
        text = CompanyAnalysisService._truncate_text(value)
        return text or default

    @staticmethod
    def _optional_text(value: Any) -> Optional[str]:
        if value is None:
            return None
        text = CompanyAnalysisService._truncate_text(value)
        if not text:
            return None
        if text.lower() in {"0", "none", "n/a", "unknown", "no match found", "insufficient evidence"}:
            return None
        return text

    @staticmethod
    def _string_list(value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, str):
            text = CompanyAnalysisService._truncate_text(value)
            if not text or text.lower() in {"insufficient evidence", "none", "n/a"}:
                return []
            return [text]
        if isinstance(value, dict):
            text = value.get("topic") or value.get("title") or value.get("signal") or value.get("priority") or value.get("summary") or value.get("description")
            return [CompanyAnalysisService._truncate_text(text)] if text else []
        if not isinstance(value, list):
            return []
        items = []
        for item in value[:CompanyAnalysisService.MAX_MATCHES]:
            if isinstance(item, str):
                text = CompanyAnalysisService._truncate_text(item)
            elif isinstance(item, dict):
                text = CompanyAnalysisService._truncate_text(item.get("topic") or item.get("title") or item.get("signal") or item.get("summary") or item.get("description"))
            else:
                text = CompanyAnalysisService._truncate_text(item)
            if text and text.lower() not in {"insufficient evidence", "none", "n/a"}:
                items.append(text)
        return items

    @staticmethod
    def _percent(value: Any, default: int = 0) -> int:
        if value is None or value == "":
            return default
        try:
            number = float(value.strip().rstrip("%")) if isinstance(value, str) else float(value)
        except (TypeError, ValueError):
            return default
        if 0 < number <= 1:
            number *= 100
        return max(0, min(100, int(round(number))))

    @staticmethod
    def _alignment_level(score: int) -> str:
        if score >= 80:
            return "High Alignment Probability"
        if score >= 50:
            return "Medium Alignment Probability"
        if score > 0:
            return "Low Alignment Probability"
        return "Insufficient Evidence"

    @staticmethod
    def _debug_enabled() -> bool:
        return os.getenv("COMPANY_ANALYSIS_DEBUG", "false").strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _debug_print(stage: str, payload: Any) -> None:
        if not CompanyAnalysisService._debug_enabled():
            return
        try:
            rendered = json.dumps(payload, ensure_ascii=True, indent=2, default=str)
        except TypeError:
            rendered = str(payload)
        print(f"\n[company-analysis] {stage}\n{rendered}\n")

    @staticmethod
    def _call_groq_chat(messages: List[Dict[str, str]], temperature: float) -> Dict[str, Optional[str]]:
        groq_api_key = os.getenv("GROQ_API_KEY", "").strip()
        if not groq_api_key:
            raise GroqApiKeyMissingException()
        groq_url = os.getenv("GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions").strip()
        groq_timeout = float(os.getenv("GROQ_TIMEOUT", "30"))
        model = CompanyAnalysisService._select_groq_model()
        CompanyAnalysisService._debug_print("groq_request", {"url": groq_url, "model": model})
        response = None
        try:
            response = requests.post(
                groq_url,
                headers={"Authorization": f"Bearer {groq_api_key}", "Content-Type": "application/json"},
                json={"model": model, "messages": messages, "temperature": temperature},
                timeout=groq_timeout,
            )
            response.raise_for_status()
        except requests.HTTPError as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None) or getattr(response, "status_code", None)
            if status_code == 404:
                raise GroqModelNotFoundException(details={"model": model}) from exc
            if status_code == 413:
                raise GroqPayloadTooLargeException(details={"model": model}) from exc
            raise ServiceUnavailableException(message="Unable to reach Groq", details={"provider": "groq", "model": model, "error": str(exc)}) from exc
        except requests.RequestException as exc:
            raise ServiceUnavailableException(message="Unable to reach Groq", details={"provider": "groq", "model": model, "error": str(exc)}) from exc
        try:
            payload = response.json()
        except ValueError:
            content = response.text.strip()
            return {"provider": "groq", "model": model, "content": content or None}
        return {"provider": "groq", "model": model, "content": CallAgentsService._extract_groq_content(payload)}

    @staticmethod
    def _select_groq_model() -> str:
        configured_model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant").strip()
        fallback_model = os.getenv("GROQ_FALLBACK_MODEL", "llama-3.1-8b-instant").strip()
        available_models = CompanyAnalysisService._fetch_available_groq_models()
        if configured_model in available_models:
            return configured_model
        if fallback_model and fallback_model in available_models:
            return fallback_model
        raise GroqModelNotFoundException(details={"model": configured_model, "fallback_model": fallback_model or None, "available_model_count": len(available_models)})

    @staticmethod
    def _fetch_available_groq_models() -> set[str]:
        groq_api_key = os.getenv("GROQ_API_KEY", "").strip()
        groq_url = os.getenv("GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions").strip()
        models_url = os.getenv("GROQ_MODELS_URL", "").strip() or CompanyAnalysisService._derive_models_url(groq_url)
        groq_timeout = float(os.getenv("GROQ_TIMEOUT", "30"))
        try:
            response = requests.get(models_url, headers={"Authorization": f"Bearer {groq_api_key}", "Content-Type": "application/json"}, timeout=groq_timeout)
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise ServiceUnavailableException(message="Unable to fetch Groq models", details={"provider": "groq", "error": str(exc)}) from exc
        except ValueError as exc:
            raise ServiceUnavailableException(message="Unable to fetch Groq models", details={"provider": "groq", "error": "groq_models_response_invalid"}) from exc
        models = payload.get("data") if isinstance(payload, dict) else []
        return {model.get("id") for model in models if isinstance(model, dict) and isinstance(model.get("id"), str)}

    @staticmethod
    def _derive_models_url(groq_url: str) -> str:
        suffix = "/chat/completions"
        if groq_url.endswith(suffix):
            return f"{groq_url[:-len(suffix)]}/models"
        return "https://api.groq.com/openai/v1/models"

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
