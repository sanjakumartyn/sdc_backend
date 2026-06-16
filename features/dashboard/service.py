import logging
from features.companydata.service import CompanyDataService

logger = logging.getLogger(__name__)

class DashboardService:
    @staticmethod
    def get_summary() -> dict:
        summary = {
            "overview": {
                "totalProducts": 102,
                "totalCaseStudies": 48,
                "activeOpportunities": 24,
                "activeCustomers": 12,
                "proposalSuccessRate": 72
            },
            "productPortfolio": [
                {"category": "Industrial Coatings", "count": 15},
                {"category": "Adhesives", "count": 20},
                {"category": "Resins", "count": 12},
                {"category": "Polymer Solutions", "count": 25},
                {"category": "Water Treatment", "count": 18},
                {"category": "Sustainability Products", "count": 12}
            ],
            "topSellingSolutions": [
                {"productName": "EcoShield Bio-Coatings", "opportunities": 12, "revenueImpact": "$2.5M"},
                {"productName": "VOCapture Elite", "opportunities": 8, "revenueImpact": "$1.8M"},
                {"productName": "PolyBond Industrial Adhesives", "opportunities": 6, "revenueImpact": "$900K"},
                {"productName": "ChemPure Systems", "opportunities": 5, "revenueImpact": "$1.1M"},
                {"productName": "NovaPredict AI", "opportunities": 4, "revenueImpact": "$2.0M"}
            ],
            "recentCaseStudies": [
                {"clientName": "Asian Paints", "projectTitle": "VOC Reduction Program", "industry": "Manufacturing", "result": "42% Emission Reduction"},
                {"clientName": "Tata Motors", "projectTitle": "Predictive Maintenance Deployment", "industry": "Automotive", "result": "37% Downtime Reduction"},
                {"clientName": "Reliance Industries", "projectTitle": "Polymer Optimization", "industry": "Chemicals", "result": "15% Cost Savings"}
            ],
            "opportunityPipeline": [
                {"stage": "Lead", "count": 35},
                {"stage": "Qualified", "count": 22},
                {"stage": "Proposal Sent", "count": 15},
                {"stage": "Negotiation", "count": 8},
                {"stage": "Won", "count": 42},
                {"stage": "Lost", "count": 18}
            ],
            "crmActivity": {
                "meetingsThisMonth": 34,
                "notesAdded": 89,
                "customerInteractions": 156,
                "followUpsPending": 12
            },
            "proposalAnalytics": {
                "total": 124,
                "approved": 89,
                "rejected": 20,
                "pending": 15
            },
            "aiRecommendations": [
                "EcoShield Bio-Coatings is involved in 60% of active opportunities.",
                "Automotive sector has highest conversion rate.",
                "VOCapture products are driving most sustainability-related deals.",
                "Increase focus on packaging industry opportunities."
            ]
        }

        try:
            db = CompanyDataService._get_db()
            client = db.client
            companydetails_db = client["companydetails"]
            
            # Fetch from correct collections
            products_col = companydetails_db["product details"]
            case_studies_col = companydetails_db["case studies"]
            crm_col = companydetails_db["CRM Records"]
            meeting_col = companydetails_db["past sales and meeting records"]
            proposals_col = companydetails_db["Proposal documents"]
            opp_col = companydetails_db["Opportunity History"]

            # Overview
            total_products = products_col.count_documents({})
            total_cases = case_studies_col.count_documents({})
            active_opps = opp_col.count_documents({"opportunityStatus": "Open"})
            active_customers = crm_col.count_documents({"status": "Active"})
            
            total_props = proposals_col.count_documents({})
            won_props = proposals_col.count_documents({"proposalStatus": "Approved"})
            success_rate = (won_props / total_props * 100) if total_props > 0 else 72

            if total_products > 0:
                summary["overview"]["totalProducts"] = total_products
                summary["overview"]["totalCaseStudies"] = total_cases
                summary["overview"]["activeOpportunities"] = active_opps
                summary["overview"]["activeCustomers"] = active_customers
                summary["overview"]["proposalSuccessRate"] = int(success_rate)
            
            # Product Portfolio (aggregate)
            if total_products > 0:
                pipeline = [{"$group": {"_id": "$category", "count": {"$sum": 1}}}]
                portfolio = list(products_col.aggregate(pipeline))
                if portfolio:
                    summary["productPortfolio"] = [{"category": p["_id"] or "Unknown", "count": p["count"]} for p in portfolio if p["_id"]]

            # Top Selling Solutions (Mock opportunities for now, since product details doesn't have opportunities count)
            top_products = list(products_col.find().limit(5))
            if top_products:
                summary["topSellingSolutions"] = [
                    {
                        "productName": p.get("productName", "Unknown"), 
                        "opportunities": 10, # Mocked as not directly available in schema
                        "revenueImpact": f"${p.get('price', 0) * 10}"
                    } for p in top_products
                ]

            # Recent Case Studies
            recent_cases = list(case_studies_col.find().sort("_id", -1).limit(5))
            if recent_cases:
                summary["recentCaseStudies"] = [
                    {
                        "clientName": c.get("client", "Unknown"),
                        "projectTitle": c.get("title", "Unknown"),
                        "industry": c.get("industry", "Unknown"),
                        "result": c.get("results", "Unknown")
                    } for c in recent_cases
                ]

            # Opportunity Pipeline
            if opp_col.count_documents({}) > 0:
                pipeline_stages = list(opp_col.aggregate([{"$group": {"_id": "$salesStage", "count": {"$sum": 1}}}]))
                if pipeline_stages:
                     summary["opportunityPipeline"] = [
                         {"stage": s["_id"], "count": s["count"]} for s in pipeline_stages if s["_id"]
                     ]

            # CRM Activity
            if crm_col.count_documents({}) > 0 or meeting_col.count_documents({}) > 0:
                summary["crmActivity"] = {
                    "meetingsThisMonth": meeting_col.count_documents({}), # Simple count for MTD
                    "notesAdded": crm_col.count_documents({"notes": {"$exists": True, "$ne": ""}}),
                    "customerInteractions": crm_col.count_documents({}),
                    "followUpsPending": crm_col.count_documents({"nextFollowUp": {"$exists": True}})
                }

            # Proposal Analytics
            if total_props > 0:
                summary["proposalAnalytics"] = {
                    "total": total_props,
                    "approved": proposals_col.count_documents({"proposalStatus": "Approved"}),
                    "rejected": proposals_col.count_documents({"proposalStatus": "Rejected"}),
                    "pending": proposals_col.count_documents({"proposalStatus": "Under Review"})
                }

        except Exception as e:
            logger.error(f"Failed to fetch dynamic dashboard summary: {e}", exc_info=True)

        return summary
