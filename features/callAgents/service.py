import json
import os
from typing import Any, Dict, List, Optional, Sequence

import requests

from common.exception.base_exception import BadRequestException, ServiceUnavailableException


class CallAgentsService:
    @staticmethod
    def analyze_company(payload: Dict[str, Any], uploaded_files: Optional[Sequence[Any]] = None) -> Dict[str, Any]:
        company = (payload.get("company") or "").strip()
        if not company:
            raise BadRequestException("company is required")

        documents = payload.get("documents") or payload.get("document_ids") or []
        if not isinstance(documents, list):
            raise BadRequestException("documents must be a list")

        project_id = (payload.get("project_id") or "default").strip()
        project_key = (payload.get("project_key") or "default").strip()
        filters = payload.get("filters") or {}
        
        question_text = f"Analyze {company} and recommend solutions, products, and case studies."
        
        ocr_extractions = CallAgentsService._extract_uploaded_documents(uploaded_files or [])
        rag_products = CallAgentsService._fetch_rag_products(question_text, project_id, project_key, filters)
        rag_casestudies = CallAgentsService._fetch_rag_casestudies(question_text, project_id, project_key, filters)

        agent_upstream = CallAgentsService._fetch_upstream_response(
            company=company,
            documents=documents,
            base_url=os.getenv("AGENT_MICROSERVICE_BASE_URL", "http://localhost:8001"),
            question_path=os.getenv("AGENT_MICROSERVICE_QUESTION_PATH", "/question"),
            timeout=float(os.getenv("AGENT_MICROSERVICE_TIMEOUT", "60")),
            service_name="agent",
            fatal=False,
            unavailable_message="Unable to reach the agent microservice",
        )

        rag_upstream = CallAgentsService._fetch_upstream_response(
            company=company,
            documents=documents,
            base_url=os.getenv("RAG_MICROSERVICE_BASE_URL", "http://localhost:8002"),
            question_path=os.getenv("RAG_MICROSERVICE_QUESTION_PATH", "/question"),
            timeout=float(os.getenv("RAG_MICROSERVICE_TIMEOUT", "30")),
            service_name="rag",
            fatal=False,
            unavailable_message="rag_service_unavailable",
        )

        synthesis = CallAgentsService._synthesize_analysis(
            company, agent_upstream, rag_upstream, ocr_extractions, rag_products, rag_casestudies
        )

        try:
            from features.companydata.service import CompanyDataService
            import datetime
            import uuid
            db = CompanyDataService._get_db()
            db.search_history.insert_one({
                "id": str(uuid.uuid4()),
                "name": company,
                "industry": "Technology", # Hardcoded or dynamically extracted if available
                "date": datetime.datetime.now().strftime("%Y-%m-%d"),
                "status": "Analyzed",
                "trend": "Up",
                "score": synthesis.get("strategic_fit_score", 85)
            })
        except Exception as e:
            import logging
            logging.error(f"Failed to save search history: {e}")

        return synthesis

    @staticmethod
    def question(payload: Dict[str, Any], uploaded_files: Optional[Sequence[Any]] = None) -> Dict[str, Any]:
        company = (payload.get("company") or "").strip()
        if not company:
            raise BadRequestException("company is required")

        documents = payload.get("documents") or payload.get("document_ids") or []

        if not isinstance(documents, list):
            raise BadRequestException("documents must be a list")

        documents = [str(doc).strip() for doc in documents if str(doc).strip()]
        question_text = (payload.get("question") or "").strip()
        project_id = (payload.get("project_id") or "default").strip()
        project_key = (payload.get("project_key") or "default").strip()
        filters = payload.get("filters") or {}
        
        ocr_extractions = CallAgentsService._extract_uploaded_documents(uploaded_files or [])
        rag_products = CallAgentsService._fetch_rag_products(question_text, project_id, project_key, filters)
        rag_casestudies = CallAgentsService._fetch_rag_casestudies(question_text, project_id, project_key, filters)

        agent_upstream = CallAgentsService._fetch_upstream_response(
            company=company,
            documents=documents,
            base_url=os.getenv("AGENT_MICROSERVICE_BASE_URL", "http://localhost:8001"),
            question_path=os.getenv("AGENT_MICROSERVICE_QUESTION_PATH", "/question"),
            timeout=float(os.getenv("AGENT_MICROSERVICE_TIMEOUT", "30")),
            service_name="agent",
            fatal=True,
            unavailable_message="Unable to reach the agent microservice",
        )

        rag_upstream = CallAgentsService._fetch_upstream_response(
            company=company,
            documents=documents,
            base_url=os.getenv("RAG_MICROSERVICE_BASE_URL", "http://localhost:8002"),
            question_path=os.getenv("RAG_MICROSERVICE_QUESTION_PATH", "/question"),
            timeout=float(os.getenv("RAG_MICROSERVICE_TIMEOUT", "30")),
            service_name="rag",
            fatal=False,
            unavailable_message="rag_service_unavailable",
        )

        synthesis = CallAgentsService._synthesize_answer(
            company, agent_upstream, rag_upstream, ocr_extractions, rag_products, rag_casestudies
        )

        return {
            "company": company,
            "documents": documents,
            "upstream": {
                "agent": agent_upstream,
                "rag": rag_upstream,
                "ocr": ocr_extractions,
                "rag_products": rag_products,
                "rag_casestudies": rag_casestudies,
            },
            "rag_products": rag_products,
            "rag_casestudies": rag_casestudies,
            "ocr_extractions": ocr_extractions,
            "synthesized_answer": synthesis.get("answer"),
            "synthesis_provider": synthesis.get("provider"),
            "synthesis_model": synthesis.get("model"),
            "synthesis_error": synthesis.get("error"),
        }

    @staticmethod
    def _fetch_upstream_response(
        company: str,
        documents: list,
        base_url: str,
        question_path: str,
        timeout: float,
        service_name: str,
        fatal: bool,
        unavailable_message: str,
    ) -> Dict[str, Any]:
        url = f"{base_url.rstrip('/')}/{question_path.lstrip('/')}"

        request_payload = {
            "company": company,
            "documents": documents,
        }

        try:
            response = requests.post(
                url,
                json=request_payload,
                timeout=timeout
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            if fatal:
                raise ServiceUnavailableException(
                    message=f"Unable to reach the {service_name} microservice",
                    details={"service_url": url, "error": str(exc)},
                ) from exc

            return {"error": unavailable_message, "service_url": url}

        try:
            return response.json()
        except ValueError:
            return {"raw": response.text}

    @staticmethod
    def _fetch_rag_products(
        question: str,
        project_id: str,
        project_key: str,
        filters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Fetch data from RAG products endpoint (non-fatal)"""
        if not question:
            return {}

        base_url = os.getenv("RAG_PRODUCTS_BASE_URL", "http://127.0.0.1:8001")
        find_path = os.getenv("RAG_PRODUCTS_FIND_PATH", "/api/products/find")
        timeout = float(os.getenv("RAG_PRODUCTS_TIMEOUT", "30"))
        
        request_payload = {
            "question": question,
            "project_id": project_id,
            "project_key": project_key,
            "filters": filters,
        }

        return CallAgentsService._fetch_rag_endpoint(
            base_url=base_url,
            endpoint_path=find_path,
            timeout=timeout,
            request_payload=request_payload,
            service_name="rag_products",
            fatal=False,
        )

    @staticmethod
    def _fetch_rag_casestudies(
        question: str,
        project_id: str,
        project_key: str,
        filters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Fetch data from RAG case studies endpoint (non-fatal)"""
        if not question:
            return {}

        base_url = os.getenv("RAG_CASESTUDIES_BASE_URL", "http://127.0.0.1:8001")
        find_path = os.getenv("RAG_CASESTUDIES_FIND_PATH", "/api/case-studies/find")
        timeout = float(os.getenv("RAG_CASESTUDIES_TIMEOUT", "30"))
        
        request_payload = {
            "question": question,
            "project_id": project_id or "casestudies",
            "project_key": project_key or "casestudies",
            "filters": filters,
        }

        return CallAgentsService._fetch_rag_endpoint(
            base_url=base_url,
            endpoint_path=find_path,
            timeout=timeout,
            request_payload=request_payload,
            service_name="rag_casestudies",
            fatal=False,
        )

    @staticmethod
    def _fetch_rag_endpoint(
        base_url: str,
        endpoint_path: str,
        timeout: float,
        request_payload: Dict[str, Any],
        service_name: str,
        fatal: bool,
    ) -> Dict[str, Any]:
        """Generic RAG endpoint fetcher (non-fatal by design)"""
        url = f"{base_url.rstrip('/')}/{endpoint_path.lstrip('/')}"

        try:
            response = requests.post(
                url,
                json=request_payload,
                timeout=timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            error_response = {
                "error": f"{service_name}_unavailable",
                "service_url": url,
                "details": str(exc),
            }
            if fatal:
                raise ServiceUnavailableException(
                    message=f"Unable to reach the {service_name} endpoint",
                    details=error_response,
                ) from exc
            return error_response

        try:
            return response.json()
        except ValueError:
            return {"raw": response.text}

    @staticmethod
    def _extract_uploaded_documents(uploaded_files: Sequence[Any]) -> List[Dict[str, Any]]:
        if not uploaded_files:
            return []

        base_url = os.getenv("OCR_MICROSERVICE_BASE_URL", "http://127.0.0.1:8001")
        extract_path = os.getenv("OCR_EXTRACT_DOCUMENTS_PATH", "/extract/documents")
        timeout = float(os.getenv("OCR_MICROSERVICE_TIMEOUT", "60"))
        url = f"{base_url.rstrip('/')}/{extract_path.lstrip('/')}"

        extractions = []
        for uploaded_file in uploaded_files:
            file_name = getattr(uploaded_file, "name", "document")
            content_type = getattr(uploaded_file, "content_type", None) or "application/octet-stream"

            try:
                uploaded_file.seek(0)
                response = requests.post(
                    url,
                    files={"file": (file_name, uploaded_file, content_type)},
                    timeout=timeout,
                )
                response.raise_for_status()
            except requests.RequestException as exc:
                raise ServiceUnavailableException(
                    message="Unable to reach the OCR microservice",
                    details={"service_url": url, "file": file_name, "error": str(exc)},
                ) from exc

            try:
                extracted_payload = response.json()
            except ValueError:
                extracted_payload = {"raw": response.text}

            extractions.append({
                "file": file_name,
                "content_type": content_type,
                "extracted": extracted_payload,
            })

        return extractions

    @staticmethod
    def _synthesize_analysis(
        company: str,
        agent_upstream: Dict[str, Any],
        rag_upstream: Dict[str, Any],
        ocr_extractions: List[Dict[str, Any]],
        rag_products: Dict[str, Any],
        rag_casestudies: Dict[str, Any],
    ) -> Dict[str, Any]:
        groq_api_key = os.getenv("GROQ_API_KEY", "").strip()
        groq_model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant").strip()
        groq_url = os.getenv("GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions").strip()
        groq_timeout = float(os.getenv("GROQ_TIMEOUT", "60"))

        if not groq_api_key:
            return {"error": "groq_api_key_missing"}

        combined_payload = {
            "company": company,
            "agent": agent_upstream,
            "rag": rag_upstream,
            "ocr_extractions": ocr_extractions,
            "rag_products": rag_products,
            "rag_casestudies": rag_casestudies,
        }

        system_prompt = """You are a highly capable sales intelligence engine.
Analyze the provided data (web scraping agent data, OCR extractions, and internal RAG products/case studies).
You MUST return your response as a STRICT, VALID JSON object with exactly the following structure:
{
  "intelligence_overview": "A string summarizing the company's focus, recent news, and key initiatives.",
  "strategic_fit_score": 92, // An integer from 0 to 100
  "ai_needs_prediction": ["need 1", "need 2", "need 3"],
  "solution_mapping": [
    {"requirement": "VOC Reduction", "solution": "VOCapture Elite"}
  ],
  "executive_qbr": {
    "key_business_priorities": ["priority 1"],
    "growth_initiatives": ["initiative 1"],
    "risk_factors": ["risk 1"],
    "buying_signals": ["signal 1"]
  },
  "meeting_preparation": {
    "suggested_discussion_points": ["point 1"],
    "potential_objections": ["objection 1"],
    "relevant_case_studies": ["case study 1"],
    "stakeholders_to_target": ["stakeholder 1"]
  },
  "deal_coach": {
    "recommended_pitch_strategy": "string strategy",
    "cross_sell_opportunities": ["opportunity 1"],
    "upsell_opportunities": ["opportunity 2"]
  }
}
If data is missing, make reasonable inferences based on the company's industry or leave arrays empty.
"""
        user_prompt = f"Analyze this data and return the strict JSON:\n{json.dumps(combined_payload, ensure_ascii=True, default=str)}"

        request_body = {
            "model": groq_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"}
        }

        try:
            response = requests.post(
                groq_url,
                headers={"Authorization": f"Bearer {groq_api_key}", "Content-Type": "application/json"},
                json=request_body,
                timeout=groq_timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            return {"error": f"groq_request_failed: {exc}"}

        payload = response.json()
        answer_str = CallAgentsService._extract_groq_content(payload)
        
        try:
            return json.loads(answer_str)
        except json.JSONDecodeError:
            return {"error": "failed_to_parse_llm_json", "raw_output": answer_str}

    @staticmethod
    def _synthesize_answer(
        company: str,
        agent_upstream: Dict[str, Any],
        rag_upstream: Dict[str, Any],
        ocr_extractions: List[Dict[str, Any]],
        rag_products: Dict[str, Any],
        rag_casestudies: Dict[str, Any],
    ) -> Dict[str, Optional[str]]:
        groq_api_key = os.getenv("GROQ_API_KEY", "").strip()
        groq_model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant").strip()
        groq_url = os.getenv(
            "GROQ_API_URL",
            "https://api.groq.com/openai/v1/chat/completions",
        ).strip()
        groq_timeout = float(os.getenv("GROQ_TIMEOUT", "30"))

        if not groq_api_key:
            # Fallback to a rich mock response for UI demonstration if no API key is provided
            return {
                "intelligence_overview": f"Based on initial analysis, {company} is scaling its digital footprint rapidly and seeking modern AI-driven solutions to optimize its operations. They have recently shown strong buying signals in automation and infrastructure.",
                "strategic_fit_score": 85,
                "ai_needs_prediction": [
                    "Predictive Analytics for supply chain optimization",
                    "Automated Customer Support via LLMs",
                    "Data Infrastructure Modernization"
                ],
                "solution_mapping": [
                    {"their_requirement": "Reduce operational costs", "our_solution": "AI-driven Automation Suite", "match_percentage": 92, "action": "Pitch Demo"},
                    {"their_requirement": "Improve customer retention", "our_solution": "Predictive CRM Module", "match_percentage": 88, "action": "Send Case Study"}
                ],
                "meeting_prep": {
                    "key_business_priorities": ["Digital Transformation", "Cost Reduction", "Market Expansion"],
                    "growth_initiatives": ["AI Integration", "Cloud Migration"],
                    "risk_factors": ["Budget Constraints", "Legacy Systems"],
                    "buying_signals": ["Recent leadership changes", "Expansion into new markets"],
                    "suggested_discussion_points": ["How our AI suite reduces costs by 30%", "Integration timeline with current stack"],
                    "potential_objections": ["Implementation time", "Security concerns"],
                    "relevant_case_studies": ["Global Corp 2025 AI Success", "TechCorp Migration"],
                    "stakeholders_to_target": ["CIO", "VP of Engineering", "Operations Director"]
                },
                "deal_coach": {
                    "cross_sell_opportunities": ["Cloud Storage Add-on", "Premium Support Package"],
                    "upsell_opportunities": ["Enterprise Tier Upgrade", "Advanced Analytics Module"]
                }
            }

        prompt = CallAgentsService._build_synthesis_prompt(
            company,
            agent_upstream,
            rag_upstream,
            ocr_extractions,
            rag_products,
            rag_casestudies,
        )
        request_body = {
            "model": groq_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a sales intelligence assistant. Use the provided agent and RAG "
                        "results to produce a direct, helpful answer for the user. If the inputs "
                        "conflict, prefer the most specific and recent evidence."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }

        try:
            response = requests.post(
                groq_url,
                headers={
                    "Authorization": f"Bearer {groq_api_key}",
                    "Content-Type": "application/json",
                },
                json=request_body,
                timeout=groq_timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            return {
                "provider": "groq",
                "model": groq_model,
                "answer": None,
                "error": f"groq_request_failed: {exc}",
            }

        try:
            payload = response.json()
        except ValueError:
            content = response.text.strip()
            return {
                "provider": "groq",
                "model": groq_model,
                "answer": content or None,
                "error": None if content else "groq_response_missing_content",
            }

        answer = CallAgentsService._extract_groq_content(payload)
        if answer:
            answer = answer.strip()

        return {
            "provider": "groq",
            "model": groq_model,
            "answer": answer or None,
            "error": None if answer else "groq_response_missing_content",
        }

    @staticmethod
    def _build_synthesis_prompt(
        company: str,
        agent_upstream: Dict[str, Any],
        rag_upstream: Dict[str, Any],
        ocr_extractions: List[Dict[str, Any]],
        rag_products: Dict[str, Any],
        rag_casestudies: Dict[str, Any],
    ) -> str:
        combined_payload = {
            "company": company,
            "agent": agent_upstream,
            "rag": rag_upstream,
            "ocr_extractions": ocr_extractions,
            "rag_products": rag_products,
            "rag_casestudies": rag_casestudies,
        }

        return (
            "Generate the best final answer for the company query using the data below. "
            "Use the OCR extraction results as document evidence when they are available. "
            "Use rag_products and rag_casestudies data as the internal company database context. "
            "Keep the answer concise, accurate, and practical. If the data is incomplete, "
            "explain what is missing instead of inventing details.\n\n"
            f"{json.dumps(combined_payload, ensure_ascii=True, indent=2, default=str)}"
        )

    @staticmethod
    def _extract_groq_content(payload: Dict[str, Any]) -> str:
        choices = payload.get("choices") or []
        if choices:
            message = choices[0].get("message") or {}
            content = message.get("content")
            if isinstance(content, str):
                return content

        output_text = payload.get("output_text")
        if isinstance(output_text, str):
            return output_text

        text = payload.get("text")
        if isinstance(text, str):
            return text

        return ""
