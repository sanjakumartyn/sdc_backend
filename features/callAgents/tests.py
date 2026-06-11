from unittest.mock import patch

import requests
from django.test import TestCase

from common.exception.base_exception import BadRequestException
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
    def test_question_requires_company(self):
        with self.assertRaises(BadRequestException):
            CallAgentsService.question({"company": "   "})

    @patch.dict(
        "os.environ",
        {
            "GROQ_API_KEY": "test-groq-key",
            "GROQ_MODEL": "test-model",
            "GROQ_API_URL": "https://api.groq.com/openai/v1/chat/completions",
            "RAG_PRODUCTS_BASE_URL": "http://127.0.0.1:8001",
            "RAG_PRODUCTS_FIND_PATH": "/api/products/find",
            "RAG_CASESTUDIES_BASE_URL": "http://127.0.0.1:8001",
            "RAG_CASESTUDIES_FIND_PATH": "/api/case-studies/find",
        },
        clear=False,
    )
    @patch("features.callAgents.service.requests.post")
    def test_question_combines_agent_rag_and_synthesizes_answer(self, mock_post):
        def side_effect(url, json=None, headers=None, timeout=None):
            if "/api/products/find" in url:
                return FakeResponse({"products": ["product1", "product2"]})

            if "/api/case-studies/find" in url:
                return FakeResponse({"casestudies": ["case1", "case2"]})

            if "localhost:8001" in url:
                return FakeResponse({"agent": "agent-response"})

            if "8002" in url:
                return FakeResponse({"rag": "rag-response"})

            return FakeResponse({"choices": [{"message": {"content": "final synthesized answer"}}]})

        mock_post.side_effect = side_effect

        result = CallAgentsService.question({
            "company": "Acme",
            "question": "Which products help with monitoring?",
        })

        self.assertEqual(result["company"], "Acme")
        self.assertEqual(result["upstream"]["agent"], {"agent": "agent-response"})
        self.assertEqual(result["upstream"]["rag"], {"rag": "rag-response"})
        self.assertEqual(result["rag_products"], {"products": ["product1", "product2"]})
        self.assertEqual(result["rag_casestudies"], {"casestudies": ["case1", "case2"]})
        self.assertEqual(result["synthesized_answer"], "final synthesized answer")
        self.assertEqual(result["synthesis_provider"], "groq")
        self.assertEqual(result["synthesis_model"], "test-model")
        self.assertIsNone(result["synthesis_error"])

    @patch.dict("os.environ", {"GROQ_API_KEY": ""}, clear=False)
    @patch("features.callAgents.service.requests.post")
    def test_question_returns_raw_data_when_llm_configuration_is_missing(self, mock_post):
        def side_effect(url, json=None, headers=None, timeout=None):
            if "/api/products/find" in url:
                return FakeResponse({"products": ["product1"]})

            if "/api/case-studies/find" in url:
                return FakeResponse({"casestudies": ["case1"]})

            if "localhost:8001" in url:
                return FakeResponse({"agent": "agent-response"})

            if "8002" in url:
                return FakeResponse({"rag": "rag-response"})

            raise AssertionError("Groq request should not be called when the API key is missing")

        mock_post.side_effect = side_effect

        result = CallAgentsService.question({
            "company": "Acme",
            "question": "test question",
        })

        self.assertEqual(result["upstream"]["agent"], {"agent": "agent-response"})
        self.assertEqual(result["upstream"]["rag"], {"rag": "rag-response"})
        self.assertIsNone(result["synthesized_answer"])
        self.assertEqual(result["synthesis_error"], "groq_api_key_missing")

    @patch.dict(
        "os.environ",
        {
            "GROQ_API_KEY": "test-groq-key",
            "GROQ_MODEL": "test-model",
            "GROQ_API_URL": "https://api.groq.com/openai/v1/chat/completions",
        },
        clear=False,
    )
    @patch("features.callAgents.service.requests.post")
    def test_question_returns_raw_data_when_llm_request_fails(self, mock_post):
        def side_effect(url, json=None, headers=None, timeout=None):
            if "/api/products/find" in url:
                return FakeResponse({"products": ["product1"]})

            if "/api/case-studies/find" in url:
                return FakeResponse({"casestudies": ["case1"]})

            if "localhost:8001" in url:
                return FakeResponse({"agent": "agent-response"})

            if "8002" in url:
                return FakeResponse({"rag": "rag-response"})

            raise requests.RequestException("groq timeout")

        mock_post.side_effect = side_effect

        result = CallAgentsService.question({
            "company": "Acme",
            "question": "test question",
        })

        self.assertEqual(result["upstream"]["agent"], {"agent": "agent-response"})
        self.assertEqual(result["upstream"]["rag"], {"rag": "rag-response"})
        self.assertIsNone(result["synthesized_answer"])
        self.assertTrue(result["synthesis_error"].startswith("groq_request_failed:"))

    @patch.dict(
        "os.environ",
        {
            "GROQ_API_KEY": "test-groq-key",
            "RAG_PRODUCTS_BASE_URL": "http://127.0.0.1:8001",
            "RAG_PRODUCTS_FIND_PATH": "/api/products/find",
            "RAG_CASESTUDIES_BASE_URL": "http://127.0.0.1:8001",
            "RAG_CASESTUDIES_FIND_PATH": "/api/case-studies/find",
        },
        clear=False,
    )
    @patch("features.callAgents.service.requests.post")
    def test_rag_products_endpoint_failure_is_non_fatal(self, mock_post):
        """Verify that RAG products endpoint failure doesn't stop processing"""
        def side_effect(url, json=None, headers=None, timeout=None):
            if "/api/products/find" in url:
                raise requests.RequestException("Products endpoint down")

            if "/api/case-studies/find" in url:
                return FakeResponse({"casestudies": ["case1"]})

            if "localhost:8001" in url:
                return FakeResponse({"agent": "agent-response"})

            if "8002" in url:
                return FakeResponse({"rag": "rag-response"})

            return FakeResponse({"choices": [{"message": {"content": "answer"}}]})

        mock_post.side_effect = side_effect

        result = CallAgentsService.question({
            "company": "Acme",
            "question": "test question",
        })

        # Verify products failure is captured but not fatal
        self.assertIn("error", result["rag_products"])
        self.assertEqual(result["rag_products"]["error"], "rag_products_unavailable")
        
        # Verify casestudies still succeeded
        self.assertEqual(result["rag_casestudies"], {"casestudies": ["case1"]})
        
        # Verify synthesis still happened
        self.assertIsNotNone(result["synthesized_answer"])

    @patch.dict(
        "os.environ",
        {
            "GROQ_API_KEY": "test-groq-key",
            "RAG_PRODUCTS_BASE_URL": "http://127.0.0.1:8001",
            "RAG_PRODUCTS_FIND_PATH": "/api/products/find",
            "RAG_CASESTUDIES_BASE_URL": "http://127.0.0.1:8001",
            "RAG_CASESTUDIES_FIND_PATH": "/api/case-studies/find",
        },
        clear=False,
    )
    @patch("features.callAgents.service.requests.post")
    def test_both_rag_endpoints_failures_are_non_fatal(self, mock_post):
        """Verify that both RAG endpoints can fail without stopping processing"""
        def side_effect(url, json=None, headers=None, timeout=None):
            if "/api/products/find" in url:
                raise requests.RequestException("Products endpoint down")

            if "/api/case-studies/find" in url:
                raise requests.RequestException("Casestudies endpoint down")

            if "localhost:8001" in url:
                return FakeResponse({"agent": "agent-response"})

            if "8002" in url:
                return FakeResponse({"rag": "rag-response"})

            return FakeResponse({"choices": [{"message": {"content": "answer"}}]})

        mock_post.side_effect = side_effect

        result = CallAgentsService.question({
            "company": "Acme",
            "question": "test question",
        })

        # Both should have errors but not crash
        self.assertIn("error", result["rag_products"])
        self.assertIn("error", result["rag_casestudies"])
        
        # Synthesis should still happen
        self.assertIsNotNone(result["synthesized_answer"])

    @patch.dict(
        "os.environ",
        {
            "RAG_PRODUCTS_BASE_URL": "http://127.0.0.1:8001",
            "RAG_PRODUCTS_FIND_PATH": "/api/products/find",
            "RAG_CASESTUDIES_BASE_URL": "http://127.0.0.1:8001",
            "RAG_CASESTUDIES_FIND_PATH": "/api/case-studies/find",
        },
        clear=False,
    )
    @patch("features.callAgents.service.requests.post")
    def test_rag_endpoints_use_question_from_payload(self, mock_post):
        """Verify that RAG endpoints receive the question from the request payload"""
        captured_payloads = []
        
        def side_effect(url, json=None, headers=None, timeout=None):
            if "/api/products/find" in url or "/api/case-studies/find" in url:
                captured_payloads.append(json)
                return FakeResponse({})
            if "8001" in url and "agent" not in url.lower():
                return FakeResponse({})
            if "8002" in url:
                return FakeResponse({})
            return FakeResponse({"choices": [{"message": {"content": "answer"}}]})

        mock_post.side_effect = side_effect

        result = CallAgentsService.question({
            "company": "Acme",
            "question": "What products help with AI monitoring?",
            "project_id": "my_project",
            "project_key": "my_key",
            "filters": {"tag": "MY_TAG"},
        })

        # Verify question was passed to both RAG endpoints
        self.assertEqual(len(captured_payloads), 2)
        for payload in captured_payloads:
            self.assertEqual(payload["question"], "What products help with AI monitoring?")
            self.assertIn("project_id", payload)
            self.assertIn("filters", payload)