import json as jsonlib
from unittest.mock import Mock, patch

import requests
from django.test import TestCase

from common.exception.base_exception import GroqApiKeyMissingException, GroqModelNotFoundException
from features.companyAnalysis.service import CompanyAnalysisService


class FakeResponse:
    def __init__(self, json_data=None, status_code=200):
        self._json_data = json_data
        self.status_code = status_code
        self.text = ""

    def raise_for_status(self):
        if self.status_code >= 400:
            error = requests.HTTPError(f"HTTP {self.status_code}")
            error.response = self
            raise error

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


def malformed_dashboard_payload():
    return {
        "company_name": "Asian Paints",
        "strategic_fit": 92,
        "meeting_prep": [
            {
                "signal": "Reliance-backed robotics startup Addverb Technologies is looking to raise expansion funding",
                "priority": "high",
                "confidence_score": 0.75,
            },
            {
                "signal": "Asian Paints website content indicates customer-facing paint products",
                "priority": "medium",
                "confidence_score": 0.8,
            },
        ],
        "intelligence_overview": "Asian Paints is a paint manufacturing company with available web signals.",
        "ai_needs_prediction": "Insufficient evidence",
        "solution_mapping": [
            {
                "product_id": "NC026",
                "product_name": "HydroSafe Monitor",
                "category": "Water Treatment",
                "description": "Smart monitoring dashboard for water systems.",
            },
            {
                "product_id": "NC037",
                "product_name": "ESG Vision Monitor",
                "category": "ESG Solutions",
                "description": "Real-time ESG performance monitoring dashboard.",
            },
        ],
    }


def numeric_deal_value_dashboard_payload():
    payload = dashboard_payload()
    payload["solution_mapping"] = [
        {
            "requirement": "Water Treatment",
            "novachem_solution": "HydroSafe Monitor",
            "match_percent": 80,
            "deal_value": 0,
            "reason": "Smart monitoring dashboard for water systems.",
        }
    ]
    return payload


def unsupported_deal_value_dashboard_payload():
    payload = dashboard_payload()
    payload["solution_mapping"] = [
        {
            "requirement": "Risk management",
            "novachem_solution": "HydroSafe Monitor",
            "match_percent": 80,
            "deal_value": "17500",
            "reason": "HydroSafe Monitor can help with risk management",
        }
    ]
    return payload


def huhtamaki_malformed_dashboard_payload():
    return {
        "company_name": "Huhtamaki",
        "strategic_fit": {"sustainability": True, "growth": True},
        "meeting_prep": {
            "sustainability": {
                "topics": ["Stick Packaging Market", "VOC Emission Reduction", "Water Conservation Initiative"],
                "questions": ["How can we support Huhtamaki's sustainability goals?"],
            },
            "growth": {
                "topics": ["Hiring", "Job Openings"],
                "questions": ["How can we support Huhtamaki's growth plans?"],
            },
        },
        "intelligence_overview": {
            "summary": "Huhtamaki is a leading global provider of sustainable packaging solutions.",
            "key_points": ["Stick Packaging Market growth", "VOC Emission Reduction opportunities"],
        },
        "ai_needs_prediction": [
            {"need": "Predictive analytics for production", "confidence": 0.8},
            {"need": "ESG performance monitoring", "confidence": 0.7},
        ],
        "solution_mapping": [
            {"requirement": "VOC Emission Reduction", "novachem_solution": "VOCapture Elite", "match_percent": 80, "deal_value": None, "reason": "Case-study evidence."},
            {"requirement": "Water Conservation Initiative", "novachem_solution": "HydroSafe Membrane", "match_percent": 90, "deal_value": None, "reason": "Case-study evidence."},
            {"requirement": "ESG performance monitoring", "novachem_solution": "ESG Vision Audit", "match_percent": 80, "deal_value": None, "reason": "Product evidence."},
        ],
    }


def huhtamaki_context():
    return {
        "company_name": "Huhtamaki",
        "website_url": "https://www.huhtamaki.com",
        "user_question": "Create full company analysis dashboard",
        "agent_signals": [
            {"type": "sustainability", "title": "Stick Packaging Market growth", "summary": "Sustainable packaging demand is growing."},
            {"type": "hiring", "title": "Production hiring", "summary": "Manufacturing hiring signals."},
        ],
        "client_products": ["Foodservice packaging Products", "Paper hot cups and lids"],
        "product_matches": [
            {"productId": "NC026", "productName": "HydroSafe Monitor", "category": "Water Treatment", "description": "Smart monitoring dashboard for water systems.", "price": 17500},
            {"productId": "NC038", "productName": "ESG Vision Audit", "category": "ESG Solutions", "description": "Automated ESG audit and compliance system.", "price": 41000},
            {"productId": "NC043", "productName": "CarbonZero Prime", "category": "ESG Solutions", "description": "Carbon neutrality management software.", "price": 47000},
        ],
        "case_study_matches": [
            {"title": "VOC Emission Reduction for Automotive Paint Manufacturer", "productsUsed": ["VOCapture Elite", "AirGuard Prime"]},
            {"title": "Smart ESG Tracking for Manufacturing Operations", "productsUsed": ["ESG Vision Audit", "CarbonZero Prime"]},
        ],
        "ocr_evidence": [],
        "company_data_summary": {},
        "crm_deals_summary": [],
    }


def noisy_asian_paints_agent_output():
    return {
        "account_id": "asian_paints_001",
        "company_name": "Asian Paints",
        "status": "completed",
        "signals": [
            {
                "type": "competitor_activity",
                "title": "GO TO HOMEPAGE SHOP ONLINE Recently Viewed VIEW ALL Book of Colours",
                "summary": "Oops! the page does not exist. GO TO HOMEPAGE SHOP ONLINE Recently Viewed.",
                "intent": "risk",
                "impact_score": 78,
                "priority": "medium",
                "confidence_score": 0.8,
                "source_type": "annual_report",
            },
            {
                "type": "supply_chain",
                "title": "Jobs People Learning Clear text Clear text Sign in Join now",
                "summary": "We couldn't find a match for Asian Paints jobs in United States.",
                "intent": "neutral",
                "impact_score": 78,
                "priority": "medium",
                "confidence_score": 0.85,
                "source_type": "hiring",
            },
        ],
        "company_profile": {
            "company_name": "Asian Paints",
            "website": "https://www.asianpaints.com",
            "description": "Get hassle-free wall paint with waterproofing solutions, interior wall paint, exterior house painting and paint colours by Asian Paints.",
            "confidence_score": 0.95,
            "products": [
                {"name": "Featured products"},
                {"name": "Interior wall paint"},
                {"name": "Exterior wall paint"},
                {"name": "Waterproofing Services"},
                {"name": "Wood Solutions"},
                {"name": "Product catalog"},
                {"name": "Select country"},
            ],
            "services": [
                {"name": "Painting Service"},
                {"name": "Everything a home needs"},
                {"name": "Waterproofing Services"},
                {"name": "Get home decor advice and interior design solutions"},
                {"name": "What our"},
                {"name": "clients say about us!"},
            ],
            "source_urls": ["https://www.asianpaints.com"],
        },
        "sources": [
            {
                "source_type": "esg",
                "status": "ok",
                "content": "Resource at '/sustainability' not found: No resource found",
            }
        ],
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
    "GROQ_MODEL": "llama-3.1-8b-instant",
    "GROQ_FALLBACK_MODEL": "llama-3.1-8b-instant",
    "COMPANY_ANALYSIS_DEBUG": "false",
}


class CompanyAnalysisServiceTestCase(TestCase):
    @patch.dict("os.environ", {**TEST_ENV, "GROQ_API_KEY": "test-key"}, clear=False)
    @patch("features.companyAnalysis.service.CompanyAnalysisService._fetch_crm_deals", return_value=[])
    @patch("features.companyAnalysis.service.CompanyAnalysisService._fetch_company_data", return_value={})
    @patch("features.companyAnalysis.service.requests.get")
    @patch("features.callAgents.service.requests.post")
    def test_analyze_returns_dashboard_without_debug_payloads(self, mock_post, mock_get, *_):
        mock_get.return_value = FakeResponse({"data": [{"id": "llama-3.1-8b-instant"}]})

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
    @patch("features.companyAnalysis.service.requests.get")
    @patch("features.callAgents.service.requests.post")
    def test_analyze_compacts_large_evidence_before_groq(self, mock_post, mock_get, *_):
        calls = []
        huge_text = "x" * 5000
        mock_get.return_value = FakeResponse({"data": [{"id": "llama-3.1-8b-instant"}]})

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
                self.assertIn('"product_matches"', prompt)
                self.assertIn('"case_study_matches"', prompt)
                return FakeResponse({"choices": [{"message": {"content": jsonlib.dumps(dashboard_payload())}}]})
            raise AssertionError(f"Unexpected URL: {url}")

        mock_post.side_effect = side_effect

        result = CompanyAnalysisService.analyze({"company_name": "Asian Paints"})

        self.assertIsNone(result["strategic_fit"]["score"])
        self.assertEqual(result["strategic_fit"]["alignment_level"], "insufficient_evidence")

    @patch.dict("os.environ", {**TEST_ENV, "GROQ_API_KEY": "test-key"}, clear=False)
    @patch("features.companyAnalysis.service.CompanyAnalysisService._fetch_crm_deals", return_value=[])
    @patch("features.companyAnalysis.service.CompanyAnalysisService._fetch_company_data", return_value={})
    @patch("features.companyAnalysis.service.requests.get")
    @patch("features.callAgents.service.requests.post")
    def test_analyze_repairs_malformed_groq_dashboard_shapes(self, mock_post, mock_get, *_):
        mock_get.return_value = FakeResponse({"data": [{"id": "llama-3.1-8b-instant"}]})

        def side_effect(url, json=None, headers=None, timeout=None, files=None):
            if url == "http://127.0.0.1:8000/":
                return FakeResponse({"status": "success"})
            if url == "http://127.0.0.1:8001/api/products/find":
                return FakeResponse({"found": False})
            if url == "https://api.groq.com/openai/v1/chat/completions":
                return FakeResponse({"choices": [{"message": {"content": jsonlib.dumps(malformed_dashboard_payload())}}]})
            raise AssertionError(f"Unexpected URL: {url}")

        mock_post.side_effect = side_effect

        result = CompanyAnalysisService.analyze({"company_name": "Asian Paints"})

        self.assertIsNone(result["strategic_fit"]["score"])
        self.assertEqual(result["strategic_fit"]["alignment_level"], "insufficient_evidence")
        self.assertEqual(
            result["meeting_prep"]["key_discussion_topics"][0],
            "Reliance-backed robotics startup Addverb Technologies is looking to raise expansion funding",
        )
        self.assertEqual(
            result["intelligence_overview"]["company_overview"],
            "Asian Paints is a paint manufacturing company with available web signals.",
        )
        self.assertEqual(result["ai_needs_prediction"], [])
        self.assertEqual(result["solution_mapping"], [])

    def test_repairs_huhtamaki_malformed_dashboard_without_losing_content(self):
        result = CompanyAnalysisService._normalize_dashboard_result(
            huhtamaki_malformed_dashboard_payload(),
            huhtamaki_context(),
        )

        self.assertGreater(result["strategic_fit"]["score"], 0)
        self.assertIn("sustainability", result["strategic_fit"]["explanation"].lower())
        self.assertIn("Stick Packaging Market", result["meeting_prep"]["key_discussion_topics"])
        self.assertIn("Huhtamaki is a leading global provider", result["intelligence_overview"]["company_overview"])
        self.assertIn("Stick Packaging Market growth", result["intelligence_overview"]["strategic_goals"])
        self.assertEqual(result["ai_needs_prediction"][0]["confidence"], 70)
        self.assertNotEqual(result["ai_needs_prediction"][0]["reason"], "Insufficient evidence.")
        self.assertEqual([item["novachem_solution"] for item in result["solution_mapping"]], ["ESG Vision Audit", "CarbonZero Prime"])

    def test_solution_mapping_drops_products_absent_from_product_matches(self):
        context = huhtamaki_context()
        context["product_matches"] = [{"productName": "ESG Vision Audit", "category": "ESG Solutions"}]
        mappings = CompanyAnalysisService._normalize_solution_mapping(
            [
                {"novachem_solution": "VOCapture Elite", "requirement": "VOC Emission Reduction", "match_percent": 90},
                {"novachem_solution": "ESG Vision Audit", "requirement": "ESG monitoring", "match_percent": 80},
            ],
            context,
        )

        self.assertEqual([item["novachem_solution"] for item in mappings], ["ESG Vision Audit"])

    def test_solution_mapping_replaces_no_evidence_reason_with_product_evidence(self):
        context = huhtamaki_context()
        context["product_matches"] = [
            {
                "productName": "ESG Vision Audit",
                "category": "ESG Solutions",
                "description": "Automated ESG audit and compliance system.",
            }
        ]

        mappings = CompanyAnalysisService._normalize_solution_mapping(
            [
                {
                    "requirement": "ESG tracking and reporting",
                    "novachem_solution": "ESG Vision Audit",
                    "match_percent": 85,
                    "deal_value": None,
                    "reason": "No evidence found to map ESG Vision Audit to Huhtamaki's needs.",
                }
            ],
            context,
        )

        self.assertEqual(mappings[0]["novachem_solution"], "ESG Vision Audit")
        self.assertEqual(mappings[0]["match_percent"], 85)
        self.assertNotIn("No evidence found", mappings[0]["reason"])
        self.assertIn("Retrieved product match", mappings[0]["reason"])

    def test_solution_mapping_caps_generic_overconfident_score(self):
        context = huhtamaki_context()
        context["case_study_matches"] = []
        context["product_matches"] = [
            {
                "productName": "ESG Vision Audit",
                "category": "ESG Solutions",
                "description": "Automated ESG audit and compliance system.",
            }
        ]

        mappings = CompanyAnalysisService._normalize_solution_mapping(
            [
                {
                    "requirement": "ESG tracking and reporting",
                    "novachem_solution": "ESG Vision Audit",
                    "match_percent": 100,
                    "deal_value": None,
                    "reason": "ESG Vision Audit matches Asian Paints' ESG tracking and reporting needs.",
                }
            ],
            context,
        )

        self.assertEqual(mappings[0]["match_percent"], 85)
        self.assertEqual(mappings[0]["reason"], "Retrieved product match: Automated ESG audit and compliance system.")

    def test_solution_mapping_adds_remaining_product_matches_with_scores(self):
        context = huhtamaki_context()
        context["agent_signals"] = [
            {"type": "sustainability", "title": "Water and ESG initiatives", "summary": "Water efficiency and ESG reporting are priorities."}
        ]
        context["product_matches"] = [
            {
                "productName": "ESG Vision Audit",
                "category": "ESG Solutions",
                "description": "Automated ESG audit and compliance system.",
            },
            {
                "productName": "AquaSense Recovery",
                "category": "Water Treatment",
                "description": "Water recovery optimization platform.",
            },
            {
                "productName": "CarbonZero Prime",
                "category": "ESG Solutions",
                "description": "Carbon neutrality management software.",
            },
        ]
        context["case_study_matches"] = [
            {"title": "Smart ESG Tracking for Manufacturing Operations", "productsUsed": ["ESG Vision Audit", "CarbonZero Prime"]}
        ]

        mappings = CompanyAnalysisService._normalize_solution_mapping(
            [
                {
                    "requirement": "Sustainability governance enhancement",
                    "novachem_solution": "ESG Vision Audit",
                    "match_percent": 90,
                    "deal_value": None,
                    "reason": "Case study evidence from Smart ESG Tracking for Manufacturing Operations",
                }
            ],
            context,
        )

        self.assertEqual([item["novachem_solution"] for item in mappings], ["ESG Vision Audit", "CarbonZero Prime", "AquaSense Recovery"])
        self.assertEqual([item["match_percent"] for item in mappings], [90, 90, 75])

    def test_zero_confidence_needs_are_removed(self):
        needs = CompanyAnalysisService._normalize_needs_prediction(
            [
                {
                    "need": "Predictive analytics for production",
                    "confidence": 0,
                    "reason": "No evidence of predictive analytics needs in Asian Paints' current operations.",
                },
                {
                    "need": "ESG performance monitoring",
                    "confidence": 70,
                    "reason": "Supported by sustainability evidence.",
                },
            ],
            huhtamaki_context(),
        )

        self.assertEqual(needs[0]["need"], "ESG performance monitoring")
        self.assertEqual(needs[0]["confidence"], 70)
        self.assertEqual(needs[0]["reason"], "Supported by sustainability evidence.")
        self.assertTrue(needs[0]["evidence"])

    def test_noisy_agent_output_is_cleaned_into_profile_signals(self):
        signals = CompanyAnalysisService._extract_agent_signals(noisy_asian_paints_agent_output())

        rendered = jsonlib.dumps(signals)
        self.assertNotIn("GO TO HOMEPAGE", rendered)
        self.assertNotIn("Jobs People Learning", rendered)
        self.assertEqual(signals[0]["type"], "product_line")
        self.assertIn("Interior wall paint", signals[0]["summary"])
        self.assertIn("Waterproofing Services", rendered)
        self.assertEqual(signals[0]["source_type"], "website")

    def test_noisy_agent_profile_products_are_filtered(self):
        products = CompanyAnalysisService._extract_client_products(noisy_asian_paints_agent_output())

        self.assertIn("Interior wall paint", products)
        self.assertIn("Exterior wall paint", products)
        self.assertIn("Waterproofing Services", products)
        self.assertIn("Wood Solutions", products)
        self.assertNotIn("Featured products", products)
        self.assertNotIn("Product catalog", products)
        self.assertNotIn("Select country", products)

    def test_case_study_only_products_are_not_returned_as_solutions(self):
        context = huhtamaki_context()
        context["product_matches"] = [{"productName": "ESG Vision Audit", "category": "ESG Solutions"}]
        context["case_study_matches"] = [{"title": "VOC win", "productsUsed": ["VOCapture Elite"]}]

        mappings = CompanyAnalysisService._normalize_solution_mapping(
            [{"novachem_solution": "VOCapture Elite", "requirement": "VOC Emission Reduction", "match_percent": 90}],
            context,
        )

        self.assertEqual(mappings[0]["requirement"], "ESG Solutions")
        self.assertEqual(mappings[0]["novachem_solution"], "ESG Vision Audit")
        self.assertEqual(mappings[0]["match_percent"], 75)
        self.assertIsNone(mappings[0]["deal_value"])
        self.assertEqual(mappings[0]["reason"], "Retrieved product match: ESG Solutions.")
        self.assertEqual(mappings[0]["confidence"], 75)
        self.assertTrue(mappings[0]["evidence"])

    def test_product_matches_create_fallback_mapping_when_supported_by_evidence(self):
        context = huhtamaki_context()
        context["agent_signals"] = [{"type": "sustainability", "title": "Water reuse initiative", "summary": "Packaging plant water conservation program."}]
        context["product_matches"] = [{"productName": "HydroSafe Monitor", "category": "Water Treatment", "description": "Smart monitoring dashboard for water systems."}]
        context["case_study_matches"] = []

        mappings = CompanyAnalysisService._normalize_solution_mapping([], context)

        self.assertEqual(mappings[0]["novachem_solution"], "HydroSafe Monitor")
        self.assertEqual(mappings[0]["deal_value"], None)

    def test_water_products_are_excluded_without_water_evidence(self):
        context = huhtamaki_context()
        context["agent_signals"] = [{"type": "sustainability", "title": "Packaging growth", "summary": "Sustainable packaging expansion."}]
        context["client_products"] = ["Paper hot cups"]
        context["product_matches"] = [{"productName": "HydroSafe Monitor", "category": "Water Treatment", "description": "Smart monitoring dashboard for water systems."}]
        context["case_study_matches"] = []

        mappings = CompanyAnalysisService._normalize_solution_mapping(
            [{"novachem_solution": "HydroSafe Monitor", "requirement": "Water Treatment", "match_percent": 90}],
            context,
        )

        self.assertEqual(mappings, [])

    @patch.dict("os.environ", {**TEST_ENV, "GROQ_API_KEY": "test-key"}, clear=False)
    @patch("features.companyAnalysis.service.CompanyAnalysisService._fetch_crm_deals", return_value=[])
    @patch("features.companyAnalysis.service.CompanyAnalysisService._fetch_company_data", return_value={})
    @patch("features.companyAnalysis.service.requests.get")
    @patch("features.callAgents.service.requests.post")
    def test_analyze_converts_numeric_zero_deal_value_to_null(self, mock_post, mock_get, *_):
        mock_get.return_value = FakeResponse({"data": [{"id": "llama-3.1-8b-instant"}]})

        def side_effect(url, json=None, headers=None, timeout=None, files=None):
            if url == "http://127.0.0.1:8000/":
                return FakeResponse({"status": "success", "signals": [{"title": "Water conservation initiative"}]})
            if url == "http://127.0.0.1:8001/api/products/find":
                return FakeResponse({"found": True, "products": [{"productName": "HydroSafe Monitor", "category": "Water Treatment", "description": "Smart monitoring dashboard for water systems."}]})
            if url == "https://api.groq.com/openai/v1/chat/completions":
                return FakeResponse({"choices": [{"message": {"content": jsonlib.dumps(numeric_deal_value_dashboard_payload())}}]})
            raise AssertionError(f"Unexpected URL: {url}")

        mock_post.side_effect = side_effect

        result = CompanyAnalysisService.analyze({"company_name": "Asian Paints"})

        self.assertIsNone(result["solution_mapping"][0]["deal_value"])

    @patch.dict("os.environ", {**TEST_ENV, "GROQ_API_KEY": "test-key"}, clear=False)
    @patch("features.companyAnalysis.service.CompanyAnalysisService._fetch_crm_deals", return_value=[])
    @patch("features.companyAnalysis.service.CompanyAnalysisService._fetch_company_data", return_value={})
    @patch("features.companyAnalysis.service.requests.get")
    @patch("features.callAgents.service.requests.post")
    def test_analyze_removes_unsupported_groq_deal_value(self, mock_post, mock_get, *_):
        mock_get.return_value = FakeResponse({"data": [{"id": "llama-3.1-8b-instant"}]})

        def side_effect(url, json=None, headers=None, timeout=None, files=None):
            if url == "http://127.0.0.1:8000/":
                return FakeResponse({"status": "success", "signals": [{"title": "Water risk management initiative"}]})
            if url == "http://127.0.0.1:8001/api/products/find":
                return FakeResponse({"found": True, "products": [{"productName": "HydroSafe Monitor", "category": "Water Treatment", "description": "Smart monitoring dashboard for water systems.", "price": 17500}]})
            if url == "https://api.groq.com/openai/v1/chat/completions":
                return FakeResponse({"choices": [{"message": {"content": jsonlib.dumps(unsupported_deal_value_dashboard_payload())}}]})
            raise AssertionError(f"Unexpected URL: {url}")

        mock_post.side_effect = side_effect

        result = CompanyAnalysisService.analyze({"company_name": "Nestle India"})

        self.assertIsNone(result["solution_mapping"][0]["deal_value"])

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
    @patch("features.companyAnalysis.service.requests.get")
    @patch("features.callAgents.service.requests.post")
    def test_optional_rag_failures_still_allow_dashboard_generation(self, mock_post, mock_get, *_):
        mock_get.return_value = FakeResponse({"data": [{"id": "llama-3.1-8b-instant"}]})

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
    @patch("features.companyAnalysis.service.requests.get")
    @patch("features.callAgents.service.requests.post")
    def test_ocr_and_deal_coach(self, mock_post, mock_get, *_):
        uploaded_file = Mock()
        uploaded_file.name = "brief.pdf"
        uploaded_file.content_type = "application/pdf"
        mock_get.return_value = FakeResponse({"data": [{"id": "llama-3.1-8b-instant"}]})

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

    @patch.dict("os.environ", {**TEST_ENV, "GROQ_API_KEY": "test-key"}, clear=False)
    @patch("features.companyAnalysis.service.CompanyAnalysisService._fetch_crm_deals", return_value=[])
    @patch("features.companyAnalysis.service.CompanyAnalysisService._fetch_company_data", return_value={})
    @patch("features.companyAnalysis.service.requests.get")
    @patch("features.callAgents.service.requests.post")
    def test_uses_one_dashboard_groq_call_and_deterministic_rag_question(self, mock_post, mock_get, *_):
        groq_calls = []
        rag_questions = []
        mock_get.return_value = FakeResponse({"data": [{"id": "llama-3.1-8b-instant"}]})

        def side_effect(url, json=None, headers=None, timeout=None, files=None):
            if url == "http://127.0.0.1:8000/":
                return FakeResponse({"status": "success"})
            if url == "http://127.0.0.1:8001/api/products/find":
                rag_questions.append(json["question"])
                if json["project_id"] == "companycasestudies":
                    return FakeResponse({
                        "found": True,
                        "caseStudies": [{"title": "Paint plant VOC win", "productsUsed": ["VOCapture Elite"]}],
                    })
                return FakeResponse({"found": True, "products": [{"productName": "VOCapture Elite"}]})
            if url == "https://api.groq.com/openai/v1/chat/completions":
                groq_calls.append(json)
                return FakeResponse({"choices": [{"message": {"content": jsonlib.dumps(dashboard_payload())}}]})
            raise AssertionError(f"Unexpected URL: {url}")

        mock_post.side_effect = side_effect

        CompanyAnalysisService.analyze({
            "company_name": "Asian Paints",
            "question": "Which products or case studies are relevant?",
        })

        self.assertEqual(len(groq_calls), 1)
        self.assertEqual(len(rag_questions), 2)
        self.assertIn("Find case studies", rag_questions[0])
        self.assertIn("Which products or case studies are relevant? for Asian Paints", rag_questions[0])
        self.assertIn("Find NovaChem products", rag_questions[1])
        self.assertIn("Matched case-study products to prioritize: VOCapture Elite", rag_questions[1])

    @patch.dict(
        "os.environ",
        {
            **TEST_ENV,
            "GROQ_API_KEY": "test-key",
            "GROQ_MODEL": "mixtral-8x7b-instruct",
            "GROQ_FALLBACK_MODEL": "llama-3.1-8b-instant",
        },
        clear=False,
    )
    @patch("features.companyAnalysis.service.requests.get")
    @patch("features.callAgents.service.requests.post")
    def test_uses_fallback_model_when_configured_model_is_unavailable(self, mock_post, mock_get):
        mock_get.return_value = FakeResponse({"data": [{"id": "llama-3.1-8b-instant"}]})

        def side_effect(url, json=None, headers=None, timeout=None, files=None):
            if url == "https://api.groq.com/openai/v1/chat/completions":
                self.assertEqual(json["model"], "llama-3.1-8b-instant")
                return FakeResponse({"choices": [{"message": {"content": "ok"}}]})
            raise AssertionError(f"Unexpected URL: {url}")

        mock_post.side_effect = side_effect

        result = CompanyAnalysisService._call_groq_chat(messages=[{"role": "user", "content": "hello"}], temperature=0.2)

        self.assertEqual(result["model"], "llama-3.1-8b-instant")
        self.assertEqual(result["content"], "ok")

    @patch.dict(
        "os.environ",
        {
            **TEST_ENV,
            "GROQ_API_KEY": "test-key",
            "GROQ_MODEL": "mixtral-8x7b-instruct",
            "GROQ_FALLBACK_MODEL": "llama-3.1-8b-instant",
        },
        clear=False,
    )
    @patch("features.companyAnalysis.service.requests.get")
    def test_unavailable_configured_and_fallback_models_raise_clear_error(self, mock_get):
        mock_get.return_value = FakeResponse({"data": [{"id": "another-model"}]})

        with self.assertRaises(GroqModelNotFoundException):
            CompanyAnalysisService._call_groq_chat(messages=[{"role": "user", "content": "hello"}], temperature=0.2)
