from unittest.mock import Mock, patch

import requests
from django.test import TestCase

from common.exception.base_exception import BadRequestException, GroqApiKeyMissingException, ServiceUnavailableException
from features.callAgents.service import CallAgentsService


class FakeResponse:
    def __init__(self, json_data=None, text="", status_code=200):
        self._json_data = json_data
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        if self._json_data is None:
            raise ValueError("No JSON body")
        return self._json_data


class CallAgentsServiceTestCase(TestCase):
    def test_question_requires_company_or_company_name(self):
        with self.assertRaises(BadRequestException):
            CallAgentsService.question({"company": "   ", "company_name": "   "})

    @patch.dict(
        "os.environ",
        {
            "GROQ_API_KEY": "test-groq-key",
            "GROQ_MODEL": "test-model",
            "GROQ_API_URL": "https://api.groq.com/openai/v1/chat/completions",
            "AGENT_MICROSERVICE_BASE_URL": "http://127.0.0.1:8000",
            "AGENT_MICROSERVICE_QUESTION_PATH": "/",
            "PRODUCT_RAG_MICROSERVICE_BASE_URL": "http://127.0.0.1:8001",
            "PRODUCT_RAG_MICROSERVICE_QUESTION_PATH": "/api/products/find",
            "CASE_STUDY_RAG_ENABLED": "false",
        },
        clear=False,
    )
    @patch("features.callAgents.service.requests.post")
    def test_question_uses_real_agent_and_product_rag_payloads(self, mock_post):
        calls = []

        def side_effect(url, json=None, headers=None, timeout=None, files=None):
            calls.append({"url": url, "json": json, "files": files})

            if url == "http://127.0.0.1:8000/":
                return FakeResponse({"status": "success", "signals": []})

            if url == "https://api.groq.com/openai/v1/chat/completions":
                groq_call_number = len([call for call in calls if call["url"] == url])
                if groq_call_number == 1:
                    return FakeResponse({
                        "choices": [{
                            "message": {
                                "content": (
                                    '{"keywords": ["equipment monitoring"], '
                                    '"product_question": "Which products help with AI-enabled equipment monitoring?"}'
                                )
                            }
                        }]
                    })

                return FakeResponse({"choices": [{"message": {"content": "final synthesized answer"}}]})

            if url == "http://127.0.0.1:8001/api/products/find":
                return FakeResponse({"products": ["product-rag-response"]})

            raise AssertionError(f"Unexpected URL: {url}")

        mock_post.side_effect = side_effect

        result = CallAgentsService.question({
            "account_id": "asian_paints_001",
            "company_name": "Asian Paints",
            "website_url": "https://www.asianpaints.com",
        })

        self.assertEqual(calls[0]["url"], "http://127.0.0.1:8000/")
        self.assertEqual(calls[0]["json"], {
            "company_name": "Asian Paints",
            "account_id": "asian_paints_001",
            "website_url": "https://www.asianpaints.com",
        })
        self.assertEqual(calls[1]["url"], "https://api.groq.com/openai/v1/chat/completions")
        self.assertEqual(calls[2]["url"], "http://127.0.0.1:8001/api/products/find")
        self.assertEqual(calls[2]["json"], {
            "question": "Which products help with AI-enabled equipment monitoring?",
            "project_id": "companyproduct",
            "project_key": "companyproduct",
            "filters": {
                "tag": "MY_Company_Product",
            },
        })
        self.assertEqual(calls[3]["url"], "https://api.groq.com/openai/v1/chat/completions")

        self.assertEqual(result, {"answer": "final synthesized answer"})
        self.assertNotIn("upstream", result)
        self.assertNotIn("products", result)
        self.assertNotIn("caseStudies", result)
        self.assertNotIn("synthesized_answer", result)

    @patch.dict(
        "os.environ",
        {
            "GROQ_API_KEY": "",
            "AGENT_MICROSERVICE_BASE_URL": "http://127.0.0.1:8000",
            "AGENT_MICROSERVICE_QUESTION_PATH": "/",
            "PRODUCT_RAG_MICROSERVICE_BASE_URL": "http://127.0.0.1:8001",
            "PRODUCT_RAG_MICROSERVICE_QUESTION_PATH": "/api/products/find",
            "CASE_STUDY_RAG_ENABLED": "false",
        },
        clear=False,
    )
    @patch("features.callAgents.service.requests.post")
    def test_question_requires_groq_api_key_for_final_answer(self, mock_post):
        def side_effect(url, json=None, headers=None, timeout=None, files=None):
            if url == "http://127.0.0.1:8000/":
                return FakeResponse({"status": "success"})

            if url == "http://127.0.0.1:8001/api/products/find":
                self.assertEqual(json["question"], "Find monitoring products")
                return FakeResponse({"products": []})

            raise AssertionError("Groq should not be called when the API key is missing")

        mock_post.side_effect = side_effect

        with self.assertRaises(GroqApiKeyMissingException) as context:
            CallAgentsService.question({
                "company": "Acme",
                "question": "Find monitoring products",
            })

        self.assertEqual(context.exception.error_code, "GROQ_API_KEY_MISSING")
        self.assertEqual(
            context.exception.message,
            "Groq API key is required to generate the final answer",
        )

    @patch.dict(
        "os.environ",
        {
            "GROQ_API_KEY": "test-groq-key",
            "GROQ_API_URL": "https://api.groq.com/openai/v1/chat/completions",
            "AGENT_MICROSERVICE_BASE_URL": "http://127.0.0.1:8000",
            "AGENT_MICROSERVICE_QUESTION_PATH": "/",
            "PRODUCT_RAG_MICROSERVICE_BASE_URL": "http://127.0.0.1:8001",
            "PRODUCT_RAG_MICROSERVICE_QUESTION_PATH": "/api/products/find",
            "CASE_STUDY_RAG_ENABLED": "false",
        },
        clear=False,
    )
    @patch("features.callAgents.service.requests.post")
    def test_question_uses_fallbacks_when_groq_generation_fails(self, mock_post):
        groq_call_count = 0

        def side_effect(url, json=None, headers=None, timeout=None, files=None):
            nonlocal groq_call_count

            if url == "http://127.0.0.1:8000/":
                return FakeResponse({"status": "success"})

            if url == "http://127.0.0.1:8001/api/products/find":
                self.assertEqual(json["question"], "Which products are relevant for Acme?")
                return FakeResponse({"products": []})

            if url == "https://api.groq.com/openai/v1/chat/completions":
                groq_call_count += 1
                if groq_call_count == 1:
                    raise requests.RequestException("keyword timeout")
                raise requests.RequestException("synthesis timeout")

            raise AssertionError(f"Unexpected URL: {url}")

        mock_post.side_effect = side_effect

        with self.assertRaises(ServiceUnavailableException) as context:
            CallAgentsService.question({"company": "Acme"})

        self.assertEqual(context.exception.error_code, "SERVICE_UNAVAILABLE")
        self.assertEqual(context.exception.message, "Unable to generate the final Groq answer")
        self.assertTrue(context.exception.details["error"].startswith("groq_request_failed:"))

    @patch.dict(
        "os.environ",
        {
            "GROQ_API_KEY": "test-groq-key",
            "GROQ_API_URL": "https://api.groq.com/openai/v1/chat/completions",
            "AGENT_MICROSERVICE_BASE_URL": "http://127.0.0.1:8000",
            "AGENT_MICROSERVICE_QUESTION_PATH": "/",
            "PRODUCT_RAG_MICROSERVICE_BASE_URL": "http://127.0.0.1:8001",
            "PRODUCT_RAG_MICROSERVICE_QUESTION_PATH": "/api/products/find",
            "CASE_STUDY_RAG_ENABLED": "false",
        },
        clear=False,
    )
    @patch("features.callAgents.service.requests.post")
    def test_product_rag_failure_is_optional(self, mock_post):
        def side_effect(url, json=None, headers=None, timeout=None, files=None):
            if url == "http://127.0.0.1:8000/":
                return FakeResponse({"status": "success"})

            if url == "http://127.0.0.1:8001/api/products/find":
                raise requests.RequestException("product rag down")

            if url == "https://api.groq.com/openai/v1/chat/completions":
                return FakeResponse({"choices": [{"message": {"content": "answer despite product rag outage"}}]})

            raise AssertionError(f"Unexpected URL: {url}")

        mock_post.side_effect = side_effect

        result = CallAgentsService.question({"company": "Acme"})

        self.assertEqual(result, {"answer": "answer despite product rag outage"})

    @patch.dict(
        "os.environ",
        {
            "GROQ_API_KEY": "test-groq-key",
            "GROQ_API_URL": "https://api.groq.com/openai/v1/chat/completions",
            "AGENT_MICROSERVICE_BASE_URL": "http://127.0.0.1:8000",
            "AGENT_MICROSERVICE_QUESTION_PATH": "/",
            "PRODUCT_RAG_MICROSERVICE_BASE_URL": "http://127.0.0.1:8001",
            "PRODUCT_RAG_MICROSERVICE_QUESTION_PATH": "/api/products/find",
            "CASE_STUDY_RAG_ENABLED": "true",
        },
        clear=False,
    )
    @patch("features.callAgents.service.requests.post")
    def test_case_study_rag_uses_case_study_project_payload(self, mock_post):
        def side_effect(url, json=None, headers=None, timeout=None, files=None):
            if url == "http://127.0.0.1:8000/":
                return FakeResponse({"status": "success"})

            if url == "http://127.0.0.1:8001/api/products/find":
                if json["project_id"] == "companyproduct":
                    return FakeResponse({"products": []})

                self.assertEqual(json, {
                    "question": "Find ESG case studies",
                    "project_id": "companycasestudies",
                    "project_key": "companycasestudies",
                    "filters": {
                        "tag": "MY_Company_Case_Studies",
                    },
                })
                return FakeResponse({
                    "found": True,
                    "products": [],
                    "caseStudies": [{"caseStudyId": "CS008"}],
                    "Complaints": [],
                    "source_chunks": [],
                })

            if url == "https://api.groq.com/openai/v1/chat/completions":
                return FakeResponse({"choices": [{"message": {"content": "case study answer"}}]})

            raise AssertionError(f"Unexpected URL: {url}")

        mock_post.side_effect = side_effect

        result = CallAgentsService.question({
            "company": "Acme",
            "question": "Find ESG case studies",
        })

        self.assertEqual(result, {"answer": "case study answer"})

    @patch.dict(
        "os.environ",
        {
            "GROQ_API_KEY": "test-groq-key",
            "GROQ_API_URL": "https://api.groq.com/openai/v1/chat/completions",
            "AGENT_MICROSERVICE_BASE_URL": "http://127.0.0.1:8000",
            "AGENT_MICROSERVICE_QUESTION_PATH": "/",
            "PRODUCT_RAG_MICROSERVICE_BASE_URL": "http://127.0.0.1:8001",
            "PRODUCT_RAG_MICROSERVICE_QUESTION_PATH": "/api/products/find",
            "CASE_STUDY_RAG_ENABLED": "false",
        },
        clear=False,
    )
    @patch("features.callAgents.service.requests.post")
    def test_synthesis_prompt_compacts_large_upstream_payloads(self, mock_post):
        calls = []
        huge_text = "x" * 5000

        def side_effect(url, json=None, headers=None, timeout=None, files=None):
            calls.append({"url": url, "json": json})

            if url == "http://127.0.0.1:8000/":
                return FakeResponse({
                    "status": "success",
                    "signals": [{"title": huge_text, "summary": huge_text}],
                    "sources": [{"source_type": "news", "status": "ok", "content": huge_text}],
                })

            if url == "https://api.groq.com/openai/v1/chat/completions":
                groq_call_number = len([call for call in calls if call["url"] == url])
                if groq_call_number == 1:
                    return FakeResponse({
                        "choices": [{
                            "message": {
                                "content": '{"keywords": ["paint"], "product_question": "Find paint products"}'
                            }
                        }]
                    })

                prompt = json["messages"][1]["content"]
                self.assertLess(len(prompt), 12000)
                self.assertNotIn(huge_text, prompt)
                self.assertNotIn('"source_chunks"', prompt)
                self.assertIn('"source_snippets"', prompt)
                return FakeResponse({"choices": [{"message": {"content": "compact answer"}}]})

            if url == "http://127.0.0.1:8001/api/products/find":
                return FakeResponse({
                    "found": True,
                    "products": [{"productName": "VOCapture Elite", "description": huge_text}],
                    "source_chunks": [{"text": huge_text, "project_id": "companyproduct"}],
                })

            raise AssertionError(f"Unexpected URL: {url}")

        mock_post.side_effect = side_effect

        result = CallAgentsService.question({"company": "Asian Paints"})

        self.assertEqual(result, {"answer": "compact answer"})

    @patch.dict("os.environ", {"OCR_MICROSERVICE_BASE_URL": "http://127.0.0.1:8003"}, clear=False)
    @patch("features.callAgents.service.requests.post")
    def test_ocr_uses_8003_documents_endpoint_and_file_field(self, mock_post):
        uploaded_file = Mock()
        uploaded_file.name = "EV_Fleet_Incident_Management (1).pdf"
        uploaded_file.content_type = "application/pdf"

        mock_post.return_value = FakeResponse({"text": "ocr text"})

        result = CallAgentsService._extract_uploaded_documents([uploaded_file])

        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        self.assertEqual(mock_post.call_args.args[0], "http://127.0.0.1:8003/extract/documents")
        self.assertIn("file", kwargs["files"])
        self.assertEqual(kwargs["files"]["file"][0], "EV_Fleet_Incident_Management (1).pdf")
        self.assertEqual(kwargs["files"]["file"][2], "application/pdf")
        self.assertEqual(result[0]["extracted"], {"text": "ocr text"})
