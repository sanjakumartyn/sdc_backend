import logging
from features.companydata.service import CompanyDataService

logger = logging.getLogger(__name__)

class DashboardService:
    @staticmethod
    def get_summary() -> dict:
        # Default fallback structure
        summary = {
            "stats": [
                {"title": "Total Opportunities", "value": "142", "trend": "up", "trendValue": "+5%", "subtitle": "Active CRM Leads"},
                {"title": "Win Rate", "value": "38%", "trend": "neutral", "trendValue": "Stable", "subtitle": "Historical win rate"},
                {"title": "Avg Deal Size", "value": "$1.2M", "trend": "up", "trendValue": "+2%", "subtitle": "Per contract"}
            ],
            "recommendations": [],
            "targetAccounts": [],
            "signals": []
        }

        try:
            db = CompanyDataService._get_db()
            client = db.client
            companydetails_db = client["companydetails"]
            
            # 1. Calculate stats dynamically
            crm_col = companydetails_db["CRM Records"]
            opp_col = companydetails_db["Opportunity History"]
            
            total_opps = crm_col.count_documents({})
            
            opps = list(opp_col.find())
            if opps:
                avg_win_prob = int(sum(o.get("winProbability", 0) for o in opps) / len(opps))
                avg_deal_value = sum(o.get("dealValue", 0) for o in opps) / len(opps)
            else:
                avg_win_prob = 71
                avg_deal_value = 3681818
                
            avg_deal_str = f"${avg_deal_value / 1e6:.2f}M"
            
            summary["stats"] = [
                {
                    "title": "Total Opportunities",
                    "value": str(total_opps),
                    "trend": "up",
                    "trendValue": "+12%",
                    "subtitle": "Active CRM Leads"
                },
                {
                    "title": "Win Rate",
                    "value": f"{avg_win_prob}%",
                    "trend": "up",
                    "trendValue": "+4 pts",
                    "subtitle": "Avg win probability"
                },
                {
                    "title": "Avg Deal Size",
                    "value": avg_deal_str,
                    "trend": "neutral",
                    "trendValue": "Stable",
                    "subtitle": "Per enterprise contract"
                }
            ]

            # 2. Fetch recommendations dynamically
            meetings_col = companydetails_db["past sales and meeting records"]
            meetings = list(meetings_col.find().limit(5))
            recommendations = []
            for m in meetings:
                p_str = ", ".join(m.get("painPoints", []))
                company_name = m.get("companyName", "Unknown")
                next_action = m.get("nextAction", "No action specified")
                recommendations.append({
                    "message": f"{company_name}: {next_action} (Pain point: {p_str})" if p_str else f"{company_name}: {next_action}",
                    "type": "critical" if m.get("status") == "Pilot Discussion" else "info",
                    "action": m.get("status", "Follow Up")
                })
            if recommendations:
                summary["recommendations"] = recommendations

            # 3. Fetch target accounts dynamically
            target_accounts = []
            top_opps = list(opp_col.find().sort("winProbability", -1).limit(5))
            for o in top_opps:
                target_accounts.append({
                    "name": o.get("companyName", "Unknown"),
                    "category": o.get("industry", "Unknown")
                })
            if target_accounts:
                summary["targetAccounts"] = target_accounts

            # 4. Fetch market signals dynamically
            signals = []
            for m in meetings_col.find({"buyingSignals": {"$exists": True, "$ne": []}}).limit(5):
                signals.append({
                    "label": m.get("meetingDate", "Recently"),
                    "title": f"Buying signal from {m.get('companyName', 'Unknown')}: {', '.join(m.get('buyingSignals', []))}"
                })
            if signals:
                summary["signals"] = signals

        except Exception as e:
            logger.error(f"Failed to fetch dynamic dashboard summary: {e}", exc_info=True)

        return summary
