from django.http import JsonResponse
import json
from django.views.decorators.csrf import csrf_exempt

def dashboard_summary(request):
    data = {
        "stats": [
            {
                "title": "Revenue Pipeline",
                "value": "$1.2B",
                "trend": "up",
                "trendValue": "+5.2%",
                "icon": "TrendingUp",
                "subtitle": "since last quarter"
            },
            {
                "title": "Active Accounts",
                "value": "450",
                "trend": "neutral",
                "trendValue": "Current",
                "icon": "ShieldCheck",
                "subtitle": "high-priority coverage"
            }
        ],
        "recommendations": [
            {
                "message": "Nexus Global Systems: +92% match with enterprise data migration",
                "type": "critical",
                "action": "View opportunity"
            }
        ],
        "targetAccounts": [
            {"name": "Volt Energy", "category": "Energy"},
            {"name": "Orion Space", "category": "Aerospace"}
        ],
        "signals": [
            {"label": "Just now", "title": "Nexus Global CFO mentioned AI expansion in earnings call."}
        ]
    }
    return JsonResponse(data)

@csrf_exempt
def history(request):
    if request.method == "DELETE":
        try:
            from features.companydata.service import CompanyDataService
            db = CompanyDataService._get_db()
            db.search_history.delete_many({})
            return JsonResponse({"status": "success", "message": "Search history cleared"})
        except Exception as e:
            import logging
            logging.error(f"Error clearing history: {e}")
            return JsonResponse({"status": "error", "message": str(e)}, status=500)

    try:
        from features.companydata.service import CompanyDataService
        import datetime
        db = CompanyDataService._get_db()
        history_cursor = db.search_history.find({}, {"_id": 0}).sort("date", -1)
        data = list(history_cursor)
        
        # Fallback if history is completely empty, give some dummy to show UI
        if not data:
            data = [
                {
                    "id": 1,
                    "name": "Starlight Automotive",
                    "industry": "Manufacturing",
                    "date": datetime.datetime.now().strftime("%Y-%m-%d"),
                    "status": "Analyzed",
                    "trend": "Up",
                    "score": 92
                }
            ]
    except Exception as e:
        import logging
        logging.error(f"Error fetching history: {e}")
        data = []
        
    return JsonResponse(data, safe=False)

def company_details(request, name):
    data = {
        "healthTrend": "+12%",
        "industry": "Cloud Infrastructure",
        "annualRevenue": "$14.2B USD",
        "strategicFit": 94,
        "nextMilestone": {
            "title": "Executive QBR",
            "date": "Oct 24, 2:00 PM"
        },
        "intelligenceOverview": [
            {
                "title": f"Strategic Goal for {name}: APAC Expansion",
                "description": "Aggressive push into Southeast Asian markets..."
            }
        ],
        "aiNeeds": [
            {
                "category": "Operational",
                "urgency": "Critical", 
                "title": "Automated Multi-Cloud FinOps",
                "description": "Currently overspending by 18% on egress fees."
            }
        ],
        "mappingData": [
            {
                "requirement": "Cloud Cost Reduction",
                "subReq": "Targeting -20% OpEx",
                "solution": "Nexus Optimizer v4",
                "subSol": "FinOps Tier",
                "match": 98,
                "matchColor": "bg-emerald-600",
                "dealValue": "$2.4M"
            }
        ],
        "initialMessage": f"I've completed the intelligence map for {name}."
    }
    return JsonResponse(data)

@csrf_exempt
def chat(request):
    if request.method == "POST":
        try:
            body = json.loads(request.body)
            account = body.get("account", "Unknown")
            message = body.get("message", "").lower()
            
            if "why" in message:
                reply = f"Top reasons to contact {account}:\n1. Strong alignment with our solutions."
            else:
                reply = f"I am your AI Deal Coach. I see you asked about {account}. How else can I help?"
        except:
            reply = "Error processing message."
        return JsonResponse({"reply": reply})
    return JsonResponse({"reply": "Only POST allowed."})
