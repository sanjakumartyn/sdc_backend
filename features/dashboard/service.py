import logging
from features.companydata.service import CompanyDataService

logger = logging.getLogger(__name__)

class DashboardService:
    @staticmethod
    def get_summary() -> dict:
        # Default empty structure
        summary = {
            "stats": [
                {"title": "Total Opportunities", "value": "0"},
                {"title": "Win Rate", "value": "0%"}
            ],
            "recommendations": [],
            "targetAccounts": [],
            "signals": []
        }

        try:
            db = CompanyDataService._get_db()
            
            # Fetch stats
            stats_docs = list(db.dashboard_stats.find({}, {"_id": 0}))
            if stats_docs:
                summary["stats"] = stats_docs

            # Fetch recommendations
            rec_docs = list(db.recommendations.find({}, {"_id": 0}).limit(5))
            if rec_docs:
                summary["recommendations"] = rec_docs

            # Fetch target accounts
            accounts_docs = list(db.target_accounts.find({}, {"_id": 0}).limit(5))
            if accounts_docs:
                summary["targetAccounts"] = accounts_docs

            # Fetch signals
            signals_docs = list(db.market_signals.find({}, {"_id": 0}).limit(5))
            if signals_docs:
                summary["signals"] = signals_docs
                
        except Exception as e:
            logger.error(f"Failed to fetch dashboard summary from MongoDB: {e}")
            # If MongoDB connection fails (e.g., bad auth), it will gracefully fall back to the empty structure above,
            # but we can also inject an error message into the stats to inform the user.
            summary["stats"] = [
                {"title": "Database Error", "value": "Auth Failed"},
                {"title": "Check .env", "value": "MONGODB_URI"}
            ]

        return summary
