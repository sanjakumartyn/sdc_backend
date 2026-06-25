import logging
from features.companydata.service import CompanyDataService

logger = logging.getLogger(__name__)

class DashboardService:
    @staticmethod
    def get_summary() -> dict:
        summary = {
            "overview": {
                "totalProducts": 0,
                "totalCaseStudies": 0,
                "activeOpportunities": 0,
                "activeCustomers": 0,
                "proposalSuccessRate": 0
            },
            "productPortfolio": [
                {"category": "AI & Generative AI", "count": 5},
                {"category": "Data Analytics", "count": 4},
                {"category": "Cloud Solutions", "count": 4},
                {"category": "Cybersecurity", "count": 3},
                {"category": "Digital Transformation", "count": 3},
                {"category": "Automation & RPA", "count": 2}
            ],
            "topSellingSolutions": [
                {"productName": "AI Sales Intelligence Platform", "opportunities": 12, "revenueImpact": "$450K"},
                {"productName": "Cloud Migration Accelerator", "opportunities": 8, "revenueImpact": "$380K"},
                {"productName": "Data Lake Analytics Suite", "opportunities": 6, "revenueImpact": "$250K"},
                {"productName": "Cybersecurity Threat Shield", "opportunities": 5, "revenueImpact": "$320K"},
                {"productName": "RPA Process Automator", "opportunities": 4, "revenueImpact": "$180K"}
            ],
            "recentCaseStudies": [],
            "opportunityPipeline": [],
            "crmActivity": {
                "meetingsThisMonth": 0,
                "notesAdded": 0,
                "customerInteractions": 0,
                "followUpsPending": 0
            },
            "proposalAnalytics": {
                "total": 0,
                "approved": 0,
                "rejected": 0,
                "pending": 0
            },
            "aiRecommendations": [
                "AI & Generative AI services are driving the highest client interest — consider bundling with analytics.",
                "Cloud Migration has the strongest conversion funnel across enterprise accounts.",
                "Cybersecurity services show rising demand in BFSI and Healthcare verticals.",
                "Increase focus on cross-selling Data Analytics with existing Cloud customers."
            ]
        }

        try:
            db = CompanyDataService._get_db()
            client = db.client
            company_db = client["company_details"]
            
            # Map to correct collection names in the new schema
            products_col = company_db["products"]
            case_studies_col = company_db["case studies"]
            crm_col = company_db["crm records"]
            meeting_col = company_db["past meeting records"]
            proposals_col = company_db["proposal documents"]

            # Overview counts
            total_products = products_col.count_documents({})
            total_cases = case_studies_col.count_documents({})
            total_crm = crm_col.count_documents({})
            
            # Count active CRM interactions (status = "Interested" or similar active states)
            active_statuses = ["Interested", "Active", "Engaged", "Follow-Up", "In Progress"]
            active_customers = crm_col.count_documents({"status": {"$in": active_statuses}})
            if active_customers == 0:
                # Fallback: count all distinct companies in CRM as active
                active_customers = len(crm_col.distinct("company"))
            
            total_props = proposals_col.count_documents({})
            # Proposal success: count statuses that indicate progress/approval
            approved_stages = ["Approved", "Accepted", "Won", "Signed", "In Progress", "Under Review", "Submitted"]
            won_props = proposals_col.count_documents({"proposalStatus": {"$in": approved_stages}})
            success_rate = (won_props / total_props * 100) if total_props > 0 else 0

            summary["overview"]["totalProducts"] = total_products
            summary["overview"]["totalCaseStudies"] = total_cases
            summary["overview"]["activeCustomers"] = active_customers
            summary["overview"]["proposalSuccessRate"] = int(success_rate)

            # Check for Opportunity History collection (may not exist in new schema)
            collection_names = company_db.list_collection_names()
            opp_col_name = None
            for name in collection_names:
                if "opportunit" in name.lower() or "deal" in name.lower():
                    opp_col_name = name
                    break
            
            if opp_col_name:
                opp_col = company_db[opp_col_name]
                active_opps = opp_col.count_documents({"opportunityStatus": "Open"})
                if active_opps == 0:
                    active_opps = opp_col.count_documents({})
                summary["overview"]["activeOpportunities"] = active_opps
                
                # Opportunity Pipeline
                pipeline_stages = list(opp_col.aggregate([{"$group": {"_id": "$salesStage", "count": {"$sum": 1}}}]))
                if pipeline_stages:
                    summary["opportunityPipeline"] = [
                        {"stage": s["_id"], "count": s["count"]} for s in pipeline_stages if s["_id"]
                    ]
            else:
                # Derive opportunities from proposals as a proxy
                summary["overview"]["activeOpportunities"] = proposals_col.count_documents({})
                # Build pipeline from proposal statuses
                prop_pipeline = list(proposals_col.aggregate([{"$group": {"_id": "$proposalStatus", "count": {"$sum": 1}}}]))
                if prop_pipeline:
                    summary["opportunityPipeline"] = [
                        {"stage": s["_id"], "count": s["count"]} for s in prop_pipeline if s["_id"]
                    ]
            
            # Product Portfolio (aggregate by category)
            if total_products > 0:
                pipeline = [{"$group": {"_id": "$category", "count": {"$sum": 1}}}]
                portfolio = list(products_col.aggregate(pipeline))
                if portfolio:
                    summary["productPortfolio"] = [{"category": p["_id"] or "Unknown", "count": p["count"]} for p in portfolio if p["_id"]]

            # Top Selling Solutions (from products collection)
            top_products = list(products_col.find().limit(5))
            if top_products:
                summary["topSellingSolutions"] = [
                    {
                        "productName": p.get("serviceName", p.get("productName", "Unknown")),
                        "opportunities": 10,  # Placeholder — not directly available in schema
                        "revenueImpact": f"${int(float(p.get('pricing', 0))) * 10:,}" if p.get('pricing') else "Contact Sales"
                    } for p in top_products
                ]

            # Recent Case Studies
            recent_cases = list(case_studies_col.find().sort("_id", -1).limit(5))
            if recent_cases:
                summary["recentCaseStudies"] = [
                    {
                        "clientName": c.get("client", c.get("company", "Unknown")),
                        "projectTitle": c.get("title", c.get("projectTitle", "Unknown")),
                        "industry": c.get("industry", "Unknown"),
                        "result": c.get("results", c.get("result", "Unknown"))
                    } for c in recent_cases
                ]

            # CRM Activity
            total_meetings = meeting_col.count_documents({})
            summary["crmActivity"] = {
                "meetingsThisMonth": total_meetings,
                "notesAdded": crm_col.count_documents({"painPoint": {"$exists": True, "$ne": ""}}),
                "customerInteractions": total_crm,
                "followUpsPending": crm_col.count_documents({"nextAction": {"$exists": True, "$ne": ""}})
            }

            # Proposal Analytics
            if total_props > 0:
                approved_count = proposals_col.count_documents({"proposalStatus": {"$in": approved_stages}})
                pending_stages = ["Under Review", "Submitted", "Draft"]
                pending_count = proposals_col.count_documents({"proposalStatus": {"$in": pending_stages}})
                rejected_count = total_props - (approved_count + pending_count)
                
                summary["proposalAnalytics"] = {
                    "total": total_props,
                    "approved": approved_count,
                    "rejected": max(0, rejected_count),
                    "pending": pending_count
                }

        except Exception as e:
            logger.error(f"Failed to fetch dynamic dashboard summary: {e}", exc_info=True)

        return summary

    @staticmethod
    def get_total_revenue() -> dict:
        try:
            db = CompanyDataService._get_db()
            client = db.client
            company_db = client["company_details"]
            past_sales_col = company_db["past_sales"]

            pipeline = [
                {
                    "$match": {
                        "$or": [
                            {"dealStatus": "Won"},
                            {"saleStatus": "Completed"}
                        ]
                    }
                },
                {
                    "$group": {
                        "_id": None,
                        "totalRevenue": {
                            "$sum": "$dealValue"
                        }
                    }
                }
            ]
            
            result = list(past_sales_col.aggregate(pipeline))
            total_revenue = result[0]["totalRevenue"] if result else 0
            
            # Fetch the actual deals that contributed to this revenue
            contributing_deals = list(past_sales_col.find({
                "$or": [
                    {"dealStatus": "Won"},
                    {"saleStatus": "Completed"}
                ]
            }, {"_id": 0}))

            return {
                "success": True,
                "totalRevenue": total_revenue,
                "currency": "USD",
                "contributingDeals": contributing_deals
            }
        except Exception as e:
            logger.error(f"Failed to fetch total revenue: {e}", exc_info=True)
            return {
                "success": False,
                "totalRevenue": 0,
                "currency": "USD",
                "error": str(e)
            }
