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
        },
        clear=False,
    )
    @patch("features.callAgents.service.requests.post")
    def test_question_combines_agent_rag_and_synthesizes_answer(self, mock_post):
        def side_effect(url, json=None, headers=None, timeout=None):
            if "8001" in url:
                return FakeResponse({"agent": "agent-response"})

            if "8002" in url:
                return FakeResponse({"rag": "rag-response"})

            return FakeResponse({"choices": [{"message": {"content": "final synthesized answer"}}]})

        mock_post.side_effect = side_effect

        result = CallAgentsService.question({"company": "Acme"})

        self.assertEqual(result["company"], "Acme")
        self.assertEqual(result["upstream"]["agent"], {"agent": "agent-response"})
        self.assertEqual(result["upstream"]["rag"], {"rag": "rag-response"})
        self.assertEqual(result["synthesized_answer"], "final synthesized answer")
        self.assertEqual(result["synthesis_provider"], "groq")
        self.assertEqual(result["synthesis_model"], "test-model")
        self.assertIsNone(result["synthesis_error"])

    @patch.dict("os.environ", {"GROQ_API_KEY": ""}, clear=False)
    @patch("features.callAgents.service.requests.post")
    def test_question_returns_raw_data_when_llm_configuration_is_missing(self, mock_post):
        def side_effect(url, json=None, headers=None, timeout=None):
            if "8001" in url:
                return FakeResponse({"agent": "agent-response"})

            if "8002" in url:
                return FakeResponse({"rag": "rag-response"})

            raise AssertionError("Groq request should not be called when the API key is missing")

        mock_post.side_effect = side_effect

        result = CallAgentsService.question({"company": "Acme"})

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
            if "8001" in url:
                return FakeResponse({"agent": "agent-response"})

            if "8002" in url:
                return FakeResponse({"rag": "rag-response"})

            raise requests.RequestException("groq timeout")

        mock_post.side_effect = side_effect

        result = CallAgentsService.question({"company": "Acme"})

        self.assertEqual(result["upstream"]["agent"], {"agent": "agent-response"})
        self.assertEqual(result["upstream"]["rag"], {"rag": "rag-response"})
        self.assertIsNone(result["synthesized_answer"])
        self.assertTrue(result["synthesis_error"].startswith("groq_request_failed:"))