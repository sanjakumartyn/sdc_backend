import json as jsonlib
from unittest.mock import Mock, patch

import requests
from django.test import TestCase

from common.exception.base_exception import GroqApiKeyMissingException
from features.companyAnalysis.service import CompanyAnalysisService


class FakeResponse:
    def __init__(self, json_data=None, status_code=200):
        self._json_data = json_data
        self.status_code = status_code
        self.text = ""

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self._json_data


def dashboard_payload():
    return {
        "company_name": "Asian Paints",
        "strategic_fit": {"score": 94, "alignment_level": "High Alignment Probability", "explanation": "Evidence-backed fit."},
        "meeting_prep": {
            "key_discussion_topics": ["Sustainability"],
            "business_priorities": ["VOC reduction"],
            "executive_talking_points": ["Connect compliance to savings"],
            "potential_objections": ["Budget timing"],
            "recommended_agenda": ["Review needs", "Map solutions"],
            "qbr_summary": "Focus on sustainability and manufacturing efficiency.",
        },
        "intelligence_overview": {
            "company_overview": "Evidence-based overview.",
            "industry_position": "Evidence-based position.",
            "business_model": "Evidence-based model.",
            "strategic_goals": ["Growth"],
            "expansion_initiatives": ["Manufacturing"],
            "digital_transformation_efforts": ["Analytics"],
            "sustainability_commitments": ["Lower emissions"],
        },
        "ai_needs_prediction": [{"need": "VOC Reduction Solutions", "confidence": 89, "reason": "Emissions evidence."}],
        "solution_mapping": [{"requirement": "VOC Reduction", "novachem_solution": "VOCapture Elite", "match_percent": 95, "deal_value": "$2.5M", "reason": "Matched to evidence."}],
    }


TEST_ENV = {
    "AGENT_MICROSERVICE_BASE_URL": "http://127.0.0.1:8000",
    "AGENT_MICROSERVICE_QUESTION_PATH": "/",
    "PRODUCT_RAG_MICROSERVICE_BASE_URL": "http://127.0.0.1:8001",
    "PRODUCT_RAG_MICROSERVICE_QUESTION_PATH": "/api/products/find",
    "CASE_STUDY_RAG_ENABLED": "true",
    "OCR_MICROSERVICE_BASE_URL": "http://127.0.0.1:8003",
    "OCR_EXTRACT_DOCUMENTS_PATH": "/extract/documents",
    "GROQ_API_URL": "https://api.groq.com/openai/v1/chat/completions",
}


class CompanyAnalysisServiceTestCase(TestCase):
    @patch.dict("os.environ", {**TEST_ENV, "GROQ_API_KEY": "test-key"}, clear=False)
    @patch("features.companyAnalysis.service.CompanyAnalysisService._fetch_crm_deals", return_value=[])
    @patch("features.companyAnalysis.service.CompanyAnalysisService._fetch_company_data", return_value={})
    @patch("features.callAgents.service.requests.post")
    def test_analyze_returns_dashboard_without_debug_payloads(self, mock_post, *_):
        def side_effect(url, json=None, headers=None, timeout=None, files=None):
            if url == "http://127.0.0.1:8000/":
                return FakeResponse({"status": "success", "signals": [{"title": "VOC initiative"}]})
            if url == "http://127.0.0.1:8001/api/products/find":
                return FakeResponse({"found": True, "products": [{"productName": "VOCapture Elite"}]})
            if url == "https://api.groq.com/openai/v1/chat/completions":
                return FakeResponse({"choices": [{"message": {"content": jsonlib.dumps(dashboard_payload())}}]})
            raise AssertionError(f"Unexpected URL: {url}")

        mock_post.side_effect = side_effect

        result = CompanyAnalysisService.analyze({"company_name": "Asian Paints"})

        self.assertIn("strategic_fit", result)
        self.assertIn("meeting_prep", result)
        self.assertIn("intelligence_overview", result)
        self.assertIn("ai_needs_prediction", result)
        self.assertIn("solution_mapping", result)
        self.assertNotIn("upstream", result)
        self.assertNotIn("source_chunks", result)

    @patch.dict("os.environ", {**TEST_ENV, "GROQ_API_KEY": "test-key"}, clear=False)
    @patch("features.companyAnalysis.service.CompanyAnalysisService._fetch_crm_deals", return_value=[])
    @patch("features.companyAnalysis.service.CompanyAnalysisService._fetch_company_data", return_value={})
    @patch("features.callAgents.service.requests.post")
    def test_analyze_compacts_large_evidence_before_groq(self, mock_post, *_):
        calls = []
        huge_text = "x" * 5000

        def side_effect(url, json=None, headers=None, timeout=None, files=None):
            calls.append({"url": url, "json": json})
            if url == "http://127.0.0.1:8000/":
                return FakeResponse({"status": "success", "sources": [{"source_type": "news", "status": "ok", "content": huge_text}]})
            if url == "http://127.0.0.1:8001/api/products/find":
                return FakeResponse({"found": True, "source_chunks": [{"text": huge_text, "project_id": "companyproduct"}]})
            if url == "https://api.groq.com/openai/v1/chat/completions":
                prompt = json["messages"][1]["content"]
                self.assertLess(len(prompt), 12000)
                self.assertNotIn(huge_text, prompt)
                self.assertNotIn('"source_chunks"', prompt)
                return FakeResponse({"choices": [{"message": {"content": jsonlib.dumps(dashboard_payload())}}]})
            raise AssertionError(f"Unexpected URL: {url}")

        mock_post.side_effect = side_effect

        result = CompanyAnalysisService.analyze({"company_name": "Asian Paints"})

        self.assertEqual(result["strategic_fit"]["score"], 94)

    @patch.dict("os.environ", {**TEST_ENV, "GROQ_API_KEY": ""}, clear=False)
    @patch("features.companyAnalysis.service.CompanyAnalysisService._fetch_crm_deals", return_value=[])
    @patch("features.companyAnalysis.service.CompanyAnalysisService._fetch_company_data", return_value={})
    @patch("features.callAgents.service.requests.post")
    def test_analyze_requires_groq_key(self, mock_post, *_):
        def side_effect(url, json=None, headers=None, timeout=None, files=None):
            if url == "http://127.0.0.1:8000/":
                return FakeResponse({"status": "success"})
            if url == "http://127.0.0.1:8001/api/products/find":
                return FakeResponse({"found": False})
            raise AssertionError("Groq should not be called")

        mock_post.side_effect = side_effect

        with self.assertRaises(GroqApiKeyMissingException):
            CompanyAnalysisService.analyze({"company_name": "Asian Paints"})

    @patch.dict("os.environ", {**TEST_ENV, "GROQ_API_KEY": "test-key"}, clear=False)
    @patch("features.companyAnalysis.service.CompanyAnalysisService._fetch_crm_deals", return_value=[])
    @patch("features.companyAnalysis.service.CompanyAnalysisService._fetch_company_data", return_value={})
    @patch("features.callAgents.service.requests.post")
    def test_optional_rag_failures_still_allow_dashboard_generation(self, mock_post, *_):
        def side_effect(url, json=None, headers=None, timeout=None, files=None):
            if url == "http://127.0.0.1:8000/":
                return FakeResponse({"status": "success"})
            if url == "http://127.0.0.1:8001/api/products/find":
                raise requests.RequestException("rag down")
            if url == "https://api.groq.com/openai/v1/chat/completions":
                return FakeResponse({"choices": [{"message": {"content": jsonlib.dumps(dashboard_payload())}}]})
            raise AssertionError(f"Unexpected URL: {url}")

        mock_post.side_effect = side_effect

        result = CompanyAnalysisService.analyze({"company_name": "Asian Paints"})

        self.assertEqual(result["company_name"], "Asian Paints")

    @patch.dict("os.environ", {**TEST_ENV, "GROQ_API_KEY": "test-key"}, clear=False)
    @patch("features.companyAnalysis.service.CompanyAnalysisService._fetch_crm_deals", return_value=[])
    @patch("features.companyAnalysis.service.CompanyAnalysisService._fetch_company_data", return_value={})
    @patch("features.callAgents.service.requests.post")
    def test_ocr_and_deal_coach(self, mock_post, *_):
        uploaded_file = Mock()
        uploaded_file.name = "brief.pdf"
        uploaded_file.content_type = "application/pdf"

        def side_effect(url, json=None, headers=None, timeout=None, files=None):
            if url == "http://127.0.0.1:8003/extract/documents":
                return FakeResponse({"text": "OCR evidence"})
            if url == "http://127.0.0.1:8000/":
                return FakeResponse({"status": "success"})
            if url == "http://127.0.0.1:8001/api/products/find":
                return FakeResponse({"found": False})
            if url == "https://api.groq.com/openai/v1/chat/completions":
                content = "Pitch VOCapture Elite first." if "message" in json["messages"][1]["content"] else jsonlib.dumps(dashboard_payload())
                return FakeResponse({"choices": [{"message": {"content": content}}]})
            raise AssertionError(f"Unexpected URL: {url}")

        mock_post.side_effect = side_effect

        dashboard = CompanyAnalysisService.analyze({"company_name": "Asian Paints"}, uploaded_files=[uploaded_file])
        coach = CompanyAnalysisService.deal_coach({"company_name": "Asian Paints", "message": "Which products should I pitch?"})

        self.assertEqual(dashboard["company_name"], "Asian Paints")
        self.assertEqual(coach, {"answer": "Pitch VOCapture Elite first."})
