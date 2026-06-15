import json
import os
import re
from typing import Any, Dict, List, Optional, Sequence

import requests

from common.exception.base_exception import (
    BadRequestException,
    GroqApiKeyMissingException,
    ServiceUnavailableException,
)
from features.companydata.service import CompanyDataService


class CallAgentsService:
    MAX_AGENT_SIGNALS = 5
    MAX_AGENT_SOURCES = 4
    MAX_RAG_ITEMS = 5
    MAX_SOURCE_CHUNKS = 4
    MAX_TEXT_CHARS = 800

    @staticmethod
    def question(payload: Dict[str, Any], uploaded_files: Optional[Sequence[Any]] = None) -> Dict[str, Any]:
        company_name = (payload.get("company_name") or payload.get("company") or "").strip()
        if not company_name:
            raise BadRequestException("company or company_name is required")

        account_id = (payload.get("account_id") or "").strip()
        website_url = (payload.get("website_url") or "").strip()
        user_question = (payload.get("question") or "").strip()
        documents = payload.get("documents") or payload.get("document_ids") or []

        if not isinstance(documents, list):
            raise BadRequestException("documents must be a list")

        documents = [str(doc).strip() for doc in documents if str(doc).strip()]
        ocr_extractions = CallAgentsService._extract_uploaded_documents(uploaded_files or [])
        company_data = CallAgentsService._fetch_company_data()

        agent_upstream = CallAgentsService._fetch_agent_response(
            account_id=account_id,
            company_name=company_name,
            website_url=website_url,
        )

        keyword_generation = CallAgentsService._generate_keywords(
            company_name=company_name,
            documents=documents,
            user_question=user_question,
            agent_upstream=agent_upstream,
            ocr_extractions=ocr_extractions,
            company_data=company_data,
        )
        keywords = keyword_generation.get("keywords") or CallAgentsService._fallback_keywords(company_name, documents)
        product_question = (
            keyword_generation.get("product_question")
            or CallAgentsService._fallback_product_question(company_name, user_question)
        )

        product_rag_upstream = CallAgentsService._fetch_product_rag_response(
            product_question=product_question,
        )

        case_study_rag_upstream = CallAgentsService._fetch_case_study_rag_response(
            product_question=product_question,
        )

        synthesis = CallAgentsService._synthesize_answer(
            company_name,
            user_question,
            agent_upstream,
            product_rag_upstream,
            case_study_rag_upstream,
            keywords,
            product_question,
            ocr_extractions,
            company_data,
        )

        return {"answer": synthesis["answer"]}

    @staticmethod
    def _build_url(base_url: str, path: str) -> str:
        url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
        return url

    @staticmethod
    def _post_json(
        *,
        base_url: str,
        path: str,
        payload: Dict[str, Any],
        timeout: float,
        service_name: str,
        fatal: bool,
        unavailable_message: str,
    ) -> Dict[str, Any]:
        url = CallAgentsService._build_url(base_url, path)

        try:
            response = requests.post(
                url,
                json=payload,
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
    def _fetch_agent_response(account_id: str, company_name: str, website_url: str) -> Dict[str, Any]:
        request_payload = {
            "company_name": company_name,
        }
        if account_id:
            request_payload["account_id"] = account_id
        if website_url:
            request_payload["website_url"] = website_url

        return CallAgentsService._post_json(
            base_url=os.getenv("AGENT_MICROSERVICE_BASE_URL", "http://127.0.0.1:8000"),
            path=os.getenv("AGENT_MICROSERVICE_QUESTION_PATH", "/"),
            payload=request_payload,
            timeout=float(os.getenv("AGENT_MICROSERVICE_TIMEOUT", "60")),
            service_name="agent",
            fatal=True,
            unavailable_message="Unable to reach the agent microservice",
        )

    @staticmethod
    def _fetch_product_rag_response(product_question: str) -> Dict[str, Any]:
        request_payload = {
            "question": product_question,
            "project_id": os.getenv("PRODUCT_RAG_PROJECT_ID", "companyproduct"),
            "project_key": os.getenv("PRODUCT_RAG_PROJECT_KEY", "companyproduct"),
            "filters": {
                "tag": os.getenv("PRODUCT_RAG_FILTER_TAG", "MY_Company_Product"),
            },
        }

        return CallAgentsService._post_json(
            base_url=os.getenv("PRODUCT_RAG_MICROSERVICE_BASE_URL", "http://127.0.0.1:8001"),
            path=os.getenv("PRODUCT_RAG_MICROSERVICE_QUESTION_PATH", "/api/products/find"),
            payload=request_payload,
            timeout=float(os.getenv("PRODUCT_RAG_MICROSERVICE_TIMEOUT", "30")),
            service_name="product_rag",
            fatal=False,
            unavailable_message="product_rag_service_unavailable",
        )

    @staticmethod
    def _fetch_case_study_rag_response(product_question: str) -> Dict[str, Any]:
        case_study_enabled = os.getenv("CASE_STUDY_RAG_ENABLED", "true").lower()
        if case_study_enabled != "true":
            print(
                "case_study_rag skipped: CASE_STUDY_RAG_ENABLED="
                f"{case_study_enabled}"
            )
            return {"skipped": "case_study_rag_not_configured"}

        base_url = (
            os.getenv("CASE_STUDY_RAG_MICROSERVICE_BASE_URL", "").strip()
            or os.getenv("PRODUCT_RAG_MICROSERVICE_BASE_URL", "http://127.0.0.1:8001")
        )
        path = (
            os.getenv("CASE_STUDY_RAG_MICROSERVICE_QUESTION_PATH", "").strip()
            or os.getenv("PRODUCT_RAG_MICROSERVICE_QUESTION_PATH", "/api/products/find")
        )
        if not base_url or not path:
            print(
                "case_study_rag skipped: missing CASE_STUDY_RAG_MICROSERVICE_BASE_URL "
                "or CASE_STUDY_RAG_MICROSERVICE_QUESTION_PATH, and no product RAG fallback is configured"
            )
            return {"skipped": "case_study_rag_not_configured"}

        request_payload = {
            "question": product_question,
            "project_id": os.getenv("CASE_STUDY_RAG_PROJECT_ID", "companycasestudies"),
            "project_key": os.getenv("CASE_STUDY_RAG_PROJECT_KEY", "companycasestudies"),
            "filters": {
                "tag": os.getenv("CASE_STUDY_RAG_FILTER_TAG", "MY_Company_Case_Studies"),
            },
        }
        print(
            "case_study_rag request:",
            {
                "url": CallAgentsService._build_url(base_url, path),
                "payload": request_payload,
            },
        )

        return CallAgentsService._post_json(
            base_url=base_url,
            path=path,
            payload=request_payload,
            timeout=float(os.getenv("CASE_STUDY_RAG_MICROSERVICE_TIMEOUT", "30")),
            service_name="case_study_rag",
            fatal=False,
            unavailable_message="case_study_rag_service_unavailable",
        )

    @staticmethod
    def _generate_keywords(
        company_name: str,
        documents: List[str],
        user_question: str,
        agent_upstream: Dict[str, Any],
        ocr_extractions: List[Dict[str, Any]],
        company_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        groq_model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant").strip()
        fallback_keywords = CallAgentsService._fallback_keywords(company_name, documents)
        fallback_product_question = CallAgentsService._fallback_product_question(company_name, user_question)

        if not os.getenv("GROQ_API_KEY", "").strip():
            return {
                "provider": "groq",
                "model": groq_model,
                "keywords": fallback_keywords,
                "product_question": fallback_product_question,
                "error": "groq_api_key_missing",
                "product_question_error": "groq_api_key_missing",
            }

        prompt_payload = {
            "company_name": company_name,
            "documents": documents,
            "user_question": user_question,
            "agent": agent_upstream,
            "ocr_extractions": ocr_extractions,
            "company_data": company_data,
        }
        messages = [
            {
                "role": "system",
                "content": (
                    "You generate search inputs for product retrieval. Return only strict JSON "
                    "with this shape: {\"keywords\": [\"keyword\"], \"product_question\": \"question\"}. "
                    "Use concise product, industry, pain-point, and use-case keywords. The "
                    "product_question must be a natural-language question suitable for product RAG."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(prompt_payload, ensure_ascii=True, indent=2, default=str),
            },
        ]

        result = CallAgentsService._call_groq_chat(messages=messages, temperature=0.1)
        if result.get("error"):
            result["keywords"] = fallback_keywords
            result["product_question"] = fallback_product_question
            result["product_question_error"] = result.get("error")
            return result

        parsed_search = CallAgentsService._parse_search_generation(result.get("content") or "")
        keywords = parsed_search.get("keywords") or []
        product_question = (parsed_search.get("product_question") or "").strip()
        if not keywords:
            result["error"] = "groq_keyword_response_missing_keywords"
            keywords = fallback_keywords

        if not product_question:
            result["product_question_error"] = "groq_product_question_missing"
            product_question = fallback_product_question

        result["keywords"] = keywords
        result["product_question"] = product_question
        return result

    @staticmethod
    def _fallback_keywords(company: str, documents: Sequence[str]) -> List[str]:
        return CallAgentsService._clean_keywords([company, *(documents or [])])

    @staticmethod
    def _fallback_product_question(company_name: str, user_question: str) -> str:
        if user_question:
            return user_question
        return f"Which products are relevant for {company_name}?"

    @staticmethod
    def _parse_search_generation(content: str) -> Dict[str, Any]:
        content = (content or "").strip()
        if not content:
            return {"keywords": [], "product_question": ""}

        json_content = content
        fenced_match = re.search(r"```(?:json)?\s*(.*?)\s*```", content, flags=re.IGNORECASE | re.DOTALL)
        if fenced_match:
            json_content = fenced_match.group(1).strip()

        try:
            parsed = json.loads(json_content)
        except json.JSONDecodeError:
            parsed = None

        if isinstance(parsed, dict):
            raw_keywords = parsed.get("keywords") or []
            product_question = parsed.get("product_question") if isinstance(parsed.get("product_question"), str) else ""
        elif isinstance(parsed, list):
            raw_keywords = parsed
            product_question = ""
        else:
            raw_keywords = re.split(r"[\n,;]+", content)
            product_question = ""

        return {
            "keywords": CallAgentsService._clean_keywords(raw_keywords),
            "product_question": product_question,
        }

    @staticmethod
    def _clean_keywords(raw_keywords: Sequence[Any]) -> List[str]:
        try:
            limit = int(os.getenv("GROQ_KEYWORD_LIMIT", "8"))
        except ValueError:
            limit = 8

        keywords = []
        seen = set()
        for raw_keyword in raw_keywords:
            keyword = str(raw_keyword).strip()
            if not keyword:
                continue

            normalized = keyword.casefold()
            if normalized in seen:
                continue

            keywords.append(keyword)
            seen.add(normalized)

            if len(keywords) >= max(limit, 1):
                break

        return keywords

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

        base_url = os.getenv("OCR_MICROSERVICE_BASE_URL", "http://127.0.0.1:8003")
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
        user_question: str,
        agent_upstream: Dict[str, Any],
        product_rag_upstream: Dict[str, Any],
        case_study_rag_upstream: Dict[str, Any],
        keywords: List[str],
        product_question: str,
        ocr_extractions: List[Dict[str, Any]],
        company_data: Dict[str, Any],
    ) -> Dict[str, Optional[str]]:
        groq_model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant").strip()

        if not os.getenv("GROQ_API_KEY", "").strip():
            raise GroqApiKeyMissingException()

        prompt = CallAgentsService._build_synthesis_prompt(
            company,
            user_question,
            agent_upstream,
            product_rag_upstream,
            case_study_rag_upstream,
            keywords,
            product_question,
            ocr_extractions,
            company_data,
        )
        result = CallAgentsService._call_groq_chat(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a sales intelligence assistant. Answer the user's question directly "
                        "using only the provided agent, product RAG, case-study RAG, OCR, and company "
                        "data evidence. Recommend products and case studies only when the data supports "
                        "them. Do not dump raw JSON or source chunks. Keep the response concise, "
                        "business-focused, and practical. If evidence is incomplete, say what is missing."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )

        if result.get("error"):
            raise ServiceUnavailableException(
                message="Unable to generate the final Groq answer",
                details={"provider": result.get("provider"), "model": result.get("model"), "error": result.get("error")},
            )

        answer = result.get("content")
        if answer:
            answer = answer.strip()

        if not answer:
            raise ServiceUnavailableException(
                message="Unable to generate the final Groq answer",
                details={
                    "provider": result.get("provider"),
                    "model": result.get("model"),
                    "error": "groq_response_missing_content",
                },
            )

        return {"provider": result.get("provider"), "model": result.get("model"), "answer": answer}

    @staticmethod
    def _call_groq_chat(messages: List[Dict[str, str]], temperature: float) -> Dict[str, Optional[str]]:
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
                "content": None,
                "error": "groq_api_key_missing",
            }

        try:
            response = requests.post(
                groq_url,
                headers={
                    "Authorization": f"Bearer {groq_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": groq_model,
                    "messages": messages,
                    "temperature": temperature,
                },
                timeout=groq_timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            return {
                "provider": "groq",
                "model": groq_model,
                "content": None,
                "error": f"groq_request_failed: {exc}",
            }

        try:
            payload = response.json()
        except ValueError:
            content = response.text.strip()
            return {
                "provider": "groq",
                "model": groq_model,
                "content": content or None,
                "error": None if content else "groq_response_missing_content",
            }

        content = CallAgentsService._extract_groq_content(payload)
        return {
            "provider": "groq",
            "model": groq_model,
            "content": content,
            "error": None if content else "groq_response_missing_content",
        }

    @staticmethod
    def _build_synthesis_prompt(
        company: str,
        user_question: str,
        agent_upstream: Dict[str, Any],
        product_rag_upstream: Dict[str, Any],
        case_study_rag_upstream: Dict[str, Any],
        keywords: List[str],
        product_question: str,
        ocr_extractions: List[Dict[str, Any]],
        company_data: Dict[str, Any],
    ) -> str:
        evidence_payload = CallAgentsService._build_compact_synthesis_context(
            company=company,
            user_question=user_question,
            keywords=keywords,
            product_question=product_question,
            agent_upstream=agent_upstream,
            product_rag_upstream=product_rag_upstream,
            case_study_rag_upstream=case_study_rag_upstream,
            ocr_extractions=ocr_extractions,
            company_data=company_data,
        )

        return (
            "Generate the final answer for the user's company question using the compact evidence below. "
            "Answer the user_question directly. Recommend products or case studies only when supported "
            "by the evidence. Do not expose raw JSON, source chunks, IDs, or debug payloads. Keep the "
            "answer concise, accurate, business-focused, and practical. If the evidence is incomplete, "
            "state what is missing instead of inventing details.\n\n"
            f"{json.dumps(evidence_payload, ensure_ascii=True, indent=2, default=str)}"
        )

    @staticmethod
    def _build_compact_synthesis_context(
        *,
        company: str,
        user_question: str,
        keywords: List[str],
        product_question: str,
        agent_upstream: Dict[str, Any],
        product_rag_upstream: Dict[str, Any],
        case_study_rag_upstream: Dict[str, Any],
        ocr_extractions: List[Dict[str, Any]],
        company_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        combined_payload = {
            "company": company,
            "user_question": user_question,
            "keywords": keywords,
            "product_question": product_question,
            "agent": CallAgentsService._summarize_agent(agent_upstream),
            "product_rag": CallAgentsService._summarize_rag_payload(product_rag_upstream),
            "case_study_rag": CallAgentsService._summarize_rag_payload(case_study_rag_upstream),
            "ocr_extractions": CallAgentsService._summarize_ocr_extractions(ocr_extractions),
            "company_data": CallAgentsService._truncate_value(company_data),
        }

        return combined_payload

    @staticmethod
    def _summarize_agent(agent_upstream: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(agent_upstream, dict):
            return {"raw": CallAgentsService._truncate_value(agent_upstream)}

        return {
            "status": agent_upstream.get("status"),
            "signal_count": agent_upstream.get("signal_count"),
            "signals": [
                CallAgentsService._truncate_value(signal)
                for signal in (agent_upstream.get("signals") or [])[:CallAgentsService.MAX_AGENT_SIGNALS]
            ],
            "sources": [
                {
                    "source_type": source.get("source_type"),
                    "status": source.get("status"),
                    "content": CallAgentsService._truncate_text(source.get("content")),
                }
                for source in (agent_upstream.get("sources") or [])[:CallAgentsService.MAX_AGENT_SOURCES]
                if isinstance(source, dict)
            ],
        }

    @staticmethod
    def _summarize_rag_payload(rag_payload: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(rag_payload, dict):
            return {"raw": CallAgentsService._truncate_value(rag_payload)}

        summary = {
            "found": rag_payload.get("found"),
            "error": rag_payload.get("error"),
            "products": [
                CallAgentsService._truncate_value(product)
                for product in (rag_payload.get("products") or [])[:CallAgentsService.MAX_RAG_ITEMS]
            ],
            "caseStudies": [
                CallAgentsService._truncate_value(case_study)
                for case_study in (rag_payload.get("caseStudies") or [])[:CallAgentsService.MAX_RAG_ITEMS]
            ],
            "Complaints": [
                CallAgentsService._truncate_value(complaint)
                for complaint in (rag_payload.get("Complaints") or [])[:CallAgentsService.MAX_RAG_ITEMS]
            ],
            "source_snippets": [],
        }

        for chunk in (rag_payload.get("source_chunks") or [])[:CallAgentsService.MAX_SOURCE_CHUNKS]:
            if not isinstance(chunk, dict):
                continue

            summary["source_snippets"].append({
                "project_id": chunk.get("project_id"),
                "tag": chunk.get("tag"),
                "score": chunk.get("score"),
                "text": CallAgentsService._truncate_text(chunk.get("text")),
            })

        return summary

    @staticmethod
    def _summarize_ocr_extractions(ocr_extractions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        summarized = []
        for extraction in ocr_extractions[:CallAgentsService.MAX_RAG_ITEMS]:
            summarized.append({
                "file": extraction.get("file"),
                "content_type": extraction.get("content_type"),
                "extracted": CallAgentsService._truncate_value(extraction.get("extracted")),
            })
        return summarized

    @staticmethod
    def _truncate_value(value: Any) -> Any:
        if isinstance(value, str):
            return CallAgentsService._truncate_text(value)

        if isinstance(value, list):
            return [CallAgentsService._truncate_value(item) for item in value[:CallAgentsService.MAX_RAG_ITEMS]]

        if isinstance(value, dict):
            return {
                key: CallAgentsService._truncate_value(item)
                for key, item in value.items()
                if key not in {"source_chunks"}
            }

        return value

    @staticmethod
    def _truncate_text(value: Any) -> str:
        text = str(value or "").strip()
        if len(text) <= CallAgentsService.MAX_TEXT_CHARS:
            return text
        return f"{text[:CallAgentsService.MAX_TEXT_CHARS].rstrip()}..."

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
