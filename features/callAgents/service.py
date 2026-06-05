import json
import os
from typing import Any, Dict, List, Optional, Sequence

import requests

from common.exception.base_exception import BadRequestException, ServiceUnavailableException
from features.companydata.service import CompanyDataService


class CallAgentsService:
    @staticmethod
    def question(payload: Dict[str, Any], uploaded_files: Optional[Sequence[Any]] = None) -> Dict[str, Any]:
        company = (payload.get("company") or "").strip()
        if not company:
            raise BadRequestException("company is required")

        documents = payload.get("documents") or payload.get("document_ids") or []

        if not isinstance(documents, list):
            raise BadRequestException("documents must be a list")

        documents = [str(doc).strip() for doc in documents if str(doc).strip()]
        ocr_extractions = CallAgentsService._extract_uploaded_documents(uploaded_files or [])
        company_data = CallAgentsService._fetch_company_data()

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
            company, agent_upstream, rag_upstream, ocr_extractions, company_data
        )

        return {
            "company": company,
            "documents": documents,
            "upstream": {
                "agent": agent_upstream,
                "rag": rag_upstream,
                "ocr": ocr_extractions,
                "company_data": company_data,
            },
            "company_data": company_data,
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
    def _fetch_company_data() -> Dict[str, Any]:
        if os.getenv("COMPANY_DATA_ENABLED", "true").lower() == "false":
            return {}

        try:
            limit_per_collection = int(os.getenv("COMPANY_DATA_LIMIT_PER_COLLECTION", "10"))
        except ValueError:
            limit_per_collection = 10

        try:
            return CompanyDataService.get_all_data(limit_per_collection=limit_per_collection)
        except Exception as exc:
            return {
                "error": "company_data_unavailable",
                "details": str(exc),
            }

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
    def _synthesize_answer(
        company: str,
        agent_upstream: Dict[str, Any],
        rag_upstream: Dict[str, Any],
        ocr_extractions: List[Dict[str, Any]],
        company_data: Dict[str, Any],
    ) -> Dict[str, Optional[str]]:
        groq_api_key = os.getenv("GROQ_API_KEY", "").strip()
        groq_model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant").strip()
        groq_url = os.getenv(
            "GROQ_API_URL",
            "https://api.groq.com/openai/v1/chat/completions",
        ).strip()
        groq_timeout = float(os.getenv("GROQ_TIMEOUT", "30"))

        if not groq_api_key:
            return {
                "provider": "groq",
                "model": groq_model,
                "answer": None,
                "error": "groq_api_key_missing",
            }

        prompt = CallAgentsService._build_synthesis_prompt(
            company,
            agent_upstream,
            rag_upstream,
            ocr_extractions,
            company_data,
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
        company_data: Dict[str, Any],
    ) -> str:
        combined_payload = {
            "company": company,
            "agent": agent_upstream,
            "rag": rag_upstream,
            "ocr_extractions": ocr_extractions,
            "company_data": company_data,
        }

        return (
            "Generate the best final answer for the company query using the data below. "
            "Use the OCR extraction results as document evidence when they are available. "
            "Use company_data as the internal company database context. "
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
