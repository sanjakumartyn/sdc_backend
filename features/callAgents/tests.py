from unittest.mock import Mock, patch
import json as jsonlib
import os
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


TEST_ENV = {
    "GROQ_API_KEY": "test-groq-key",
    "GROQ_MODEL": "test-model",
    "GROQ_API_URL": "https://api.groq.com/openai/v1/chat/completions",
    "AGENT_MICROSERVICE_BASE_URL": "http://127.0.0.1:8000",
    "AGENT_MICROSERVICE_QUESTION_PATH": "/",
    "AGENT_MICROSERVICE_TIMEOUT": "30",
    "RAG_PRODUCTS_BASE_URL": "http://127.0.0.1:8000",
    "RAG_PRODUCTS_FIND_PATH": "/api/products/find",
    "RAG_PRODUCTS_TIMEOUT": "30",
    "RAG_CASESTUDIES_BASE_URL": "http://127.0.0.1:8001",
    "RAG_CASESTUDIES_FIND_PATH": "/api/chat",
    "RAG_CASESTUDIES_TIMEOUT": "30",
    "PRODUCT_RAG_MICROSERVICE_BASE_URL": "http://127.0.0.1:8001",
    "PRODUCT_RAG_MICROSERVICE_QUESTION_PATH": "/api/products/find",
    "PRODUCT_RAG_TIMEOUT": "30",
    "CASE_STUDY_RAG_ENABLED": "true",
    "CASE_STUDY_RAG_MICROSERVICE_BASE_URL": "http://127.0.0.1:8001",
    "CASE_STUDY_RAG_MICROSERVICE_QUESTION_PATH": "/api/products/find",
    "CASE_STUDY_RAG_TIMEOUT": "30",
    "PRODUCT_RAG_PROJECT_ID": "product",
    "PRODUCT_RAG_PROJECT_KEY": "product",
    "PRODUCT_RAG_FILTER_TAG": "MY_Company_Product",
    "CASE_STUDY_RAG_PROJECT_ID": "casestudy",
    "CASE_STUDY_RAG_PROJECT_KEY": "casestudy",
    "CASE_STUDY_RAG_FILTER_TAG": "MY_Company_Case_Studies",
    "COMPANY_ANALYSIS_DATA_LIMIT_PER_COLLECTION": "10",
    "OCR_MICROSERVICE_BASE_URL": "http://127.0.0.1:8003",
    "OCR_EXTRACT_DOCUMENTS_PATH": "/extract/documents",
    "OCR_MICROSERVICE_TIMEOUT": "60",
}


@patch.dict("os.environ", TEST_ENV, clear=False)
class CallAgentsServiceTestCase(TestCase):
    def test_question_requires_company_or_company_name(self):
        with self.assertRaises(BadRequestException):
            CallAgentsService.question({"company": "   ", "company_name": "   "})

    @patch("features.companydata.service.CompanyDataService.get_all_data", return_value={})
    @patch("features.callAgents.service.requests.post")
    def test_question_combines_agent_rag_and_synthesizes_answer(self, mock_post, mock_company_data):
        calls = []

        def side_effect(url, json=None, headers=None, timeout=None, files=None):
            calls.append({"url": url, "json": json})
            if url == "http://127.0.0.1:8000/api/products/find":
                return FakeResponse({"products": []})
            if url == "http://127.0.0.1:8001/api/chat":
                return FakeResponse({"caseStudies": []})
            if url == "http://127.0.0.1:8000/":
                return FakeResponse({"status": "success", "signals": [{"title": "monitoring"}]})
            if url == "http://127.0.0.1:8001/api/products/find":
                return FakeResponse({"products": ["product-rag-response"]})
            if url == "https://api.groq.com/openai/v1/chat/completions":
                # Distinguish by message roles/content
                system_prompt = json["messages"][0]["content"]
                if "search inputs" in system_prompt:
                    return FakeResponse({
                        "choices": [{
                            "message": {
                                "content": '{"keywords": ["monitoring"], "product_question": "Which products help with AI-enabled equipment monitoring?"}'
                            }
                        }]
                    })
                else:
                    return FakeResponse({
                        "choices": [{
                            "message": {
                                "content": "final synthesized answer"
                            }
                        }]
                    })
            raise AssertionError(f"Unexpected URL: {url}")

        mock_post.side_effect = side_effect

        result = CallAgentsService.question({
            "account_id": "asian_paints_001",
            "company_name": "Asian Paints",
            "website_url": "https://www.asianpaints.com",
        })

        # Filter and assert the key microservice calls
        agent_call = next(c for c in calls if c["url"] == "http://127.0.0.1:8000/")
        self.assertEqual(agent_call["json"], {
            "company_name": "Asian Paints",
            "account_id": "asian_paints_001",
            "website_url": "https://www.asianpaints.com",
        })

        product_rag_call = next(c for c in calls if c["url"] == "http://127.0.0.1:8001/api/products/find" and c.get("json", {}).get("project_id") == "product")
        self.assertEqual(product_rag_call["json"], {
            "question": "Which products help with AI-enabled equipment monitoring?",
            "project_id": "product",
            "project_key": "product",
            "filters": {
                "tag": "MY_Company_Product",
            },
        })

        self.assertEqual(result["synthesized_answer"], "final synthesized answer")

    @patch.dict("os.environ", {"GROQ_API_KEY": ""}, clear=False)
    @patch("features.companydata.service.CompanyDataService.get_all_data", return_value={})
    @patch("features.callAgents.service.requests.post")
    def test_test_question_requires_groq_api_key_for_final_answer(self, mock_post, mock_company_data):
        def side_effect(url, json=None, headers=None, timeout=None, files=None):
            if url == "http://127.0.0.1:8000/api/products/find":
                return FakeResponse({"products": []})
            if url == "http://127.0.0.1:8001/api/chat":
                return FakeResponse({"caseStudies": []})
            if url == "http://127.0.0.1:8000/":
                return FakeResponse({"status": "success"})
            if url == "http://127.0.0.1:8001/api/products/find":
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

    @patch("features.companydata.service.CompanyDataService.get_all_data", return_value={})
    @patch("features.callAgents.service.requests.post")
    def test_question_uses_fallbacks_when_groq_generation_fails(self, mock_post, mock_company_data):
        def side_effect(url, json=None, headers=None, timeout=None, files=None):
            if url == "http://127.0.0.1:8000/api/products/find":
                return FakeResponse({"products": []})
            if url == "http://127.0.0.1:8001/api/chat":
                return FakeResponse({"caseStudies": []})
            if url == "http://127.0.0.1:8000/":
                return FakeResponse({"status": "success"})
            if url == "http://127.0.0.1:8001/api/products/find":
                return FakeResponse({"products": []})
            if url == "https://api.groq.com/openai/v1/chat/completions":
                raise requests.RequestException("groq timeout")
            raise AssertionError(f"Unexpected URL: {url}")

        mock_post.side_effect = side_effect

        result = CallAgentsService.question({"company": "Acme"})

        self.assertEqual(result["company"], "Acme")
        self.assertIsNone(result["synthesized_answer"])
        self.assertTrue(result["synthesis_error"].startswith("groq_request_failed:"))

    @patch("features.companydata.service.CompanyDataService.get_all_data", return_value={})
    @patch("features.callAgents.service.requests.post")
    def test_question_returns_raw_data_when_llm_configuration_is_missing(self, mock_post, mock_company_data):
        def side_effect(url, json=None, headers=None, timeout=None, files=None):
            if url == "http://127.0.0.1:8000/api/products/find":
                return FakeResponse({"products": []})
            if url == "http://127.0.0.1:8001/api/chat":
                return FakeResponse({"caseStudies": []})
            if url == "http://127.0.0.1:8000/":
                return FakeResponse({"status": "success"})
            if url == "http://127.0.0.1:8001/api/products/find":
                raise requests.RequestException("product RAG down")
            if url == "https://api.groq.com/openai/v1/chat/completions":
                system_prompt = json["messages"][0]["content"]
                if "search inputs" in system_prompt:
                    return FakeResponse({
                        "choices": [{
                            "message": {
                                "content": '{"keywords": ["monitoring"], "product_question": "Which products help with AI-enabled equipment monitoring?"}'
                            }
                        }]
                    })
                return FakeResponse({
                    "choices": [{
                        "message": {
                            "content": "answer despite product RAG outage"
                        }
                    }]
                })
            raise AssertionError(f"Unexpected URL: {url}")

        mock_post.side_effect = side_effect

        result = CallAgentsService.question({
            "company": "Acme",
            "question": "test question",
        })

        self.assertEqual(result["synthesized_answer"], "answer despite product RAG outage")

    @patch("features.companydata.service.CompanyDataService.get_all_data", return_value={})
    @patch("features.callAgents.service.requests.post")
    def test_case_study_rag_uses_case_study_project_payload(self, mock_post, mock_company_data):
        calls = []

        def side_effect(url, json=None, headers=None, timeout=None, files=None):
            calls.append({"url": url, "json": json})
            if url == "http://127.0.0.1:8000/api/products/find":
                return FakeResponse({"products": []})
            if url == "http://127.0.0.1:8001/api/chat":
                return FakeResponse({"caseStudies": []})
            if url == "http://127.0.0.1:8000/":
                return FakeResponse({"status": "success"})
            if url == "http://127.0.0.1:8001/api/products/find":
                return FakeResponse({"products": []})
            if url == "https://api.groq.com/openai/v1/chat/completions":
                system_prompt = json["messages"][0]["content"]
                if "search inputs" in system_prompt:
                    return FakeResponse({
                        "choices": [{
                            "message": {
                                "content": '{"keywords": ["monitoring"], "product_question": "Find ESG case studies"}'
                            }
                        }]
                    })
                return FakeResponse({
                    "choices": [{
                        "message": {
                            "content": "case study answer"
                        }
                    }]
                })
            raise AssertionError(f"Unexpected URL: {url}")

        mock_post.side_effect = side_effect

        result = CallAgentsService.question({
            "company": "Acme",
            "question": "Find ESG case studies",
        })

        self.assertEqual(result["synthesized_answer"], "case study answer")

        case_study_call = next(c for c in calls if c["url"] == "http://127.0.0.1:8001/api/products/find" and c.get("json", {}).get("project_id") == "casestudy")
        self.assertEqual(case_study_call["json"], {
            "question": "Find ESG case studies",
            "project_id": "casestudy",
            "project_key": "casestudy",
            "filters": {
                "tag": "MY_Company_Case_Studies",
            },
        })

    @patch("features.companydata.service.CompanyDataService.get_all_data", return_value={})
    @patch("features.callAgents.service.requests.post")
    def test_question_returns_raw_data_when_llm_request_fails(self, mock_post, mock_company_data):
        huge_text = "x" * 5000
        calls = []

        def side_effect(url, json=None, headers=None, timeout=None, files=None):
            calls.append({"url": url, "json": json})
            if url == "http://127.0.0.1:8000/api/products/find":
                return FakeResponse({"products": []})
            if url == "http://127.0.0.1:8001/api/chat":
                return FakeResponse({"caseStudies": []})
            if url == "http://127.0.0.1:8000/":
                return FakeResponse({"agent": "agent-response"})
            if url == "http://127.0.0.1:8001/api/products/find":
                return FakeResponse({
                    "found": True,
                    "products": [{"productName": "VOCapture Elite", "description": huge_text}],
                    "source_chunks": [{"text": huge_text, "project_id": "product"}],
                })
            if url == "https://api.groq.com/openai/v1/chat/completions":
                # Return keyword generation success, but raise exception for synthesis
                system_prompt = json["messages"][0]["content"]
                if "search inputs" in system_prompt:
                    return FakeResponse({
                        "choices": [{
                            "message": {
                                "content": '{"keywords": ["paint"], "product_question": "Find paint products"}'
                            }
                        }]
                    })
                raise requests.RequestException("groq synthesis failed")
            raise AssertionError(f"Unexpected URL: {url}")

        mock_post.side_effect = side_effect

        result = CallAgentsService.question({"company": "Acme"})

        self.assertEqual(result["upstream"]["agent"], {"agent": "agent-response"})
        self.assertIsNone(result["synthesized_answer"])
        self.assertTrue(result["synthesis_error"].startswith("groq_request_failed:"))
