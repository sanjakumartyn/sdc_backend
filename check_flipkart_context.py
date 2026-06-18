import os
import sys
import json
import re

sys.path.append(r"d:\sdc_backend")
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from features.companydata.service import CompanyDataService
from features.companyAnalysis.service import CompanyAnalysisService

db = CompanyDataService._get_db()

# Load all products
products = []
for coll_name in ['productinfo', 'product details']:
    for doc in db[coll_name].find({}):
        doc['collection'] = coll_name
        products.append(doc)

# Build context for flipkart
context = {
    "company_name": "flipkart",
    "agent_signals": [
        {
            "source_type": "hiring",
            "type": "role_category_demand",
            "title": "Digital Data hiring signal",
            "summary": "Digital Data hiring signal: Flipkart is actively hiring for 'Digital Data' roles, indicating a focus on digital transformation, automation, analytics, cloud, and enterprise software solutions.",
        },
        {
            "source_type": "public_mentions",
            "type": "competitor_activity",
            "title": "Strategic Partnership signal",
            "summary": "Strategic Partnership signal: Amazon Now to launch 100 large fulfilment stores in key markets ahead of Prime Day",
        }
    ],
    "client_products": [],
    "ocr_evidence": [],
    "company_data_summary": {},
    "crm_deals_summary": [],
}

def fallback_database_search(context, products):
    # 1. Extract search tokens from context
    search_text = ""
    if context.get("company_name"):
        search_text += " " + context["company_name"]
    for signal in context.get("agent_signals") or []:
        if isinstance(signal, dict):
            search_text += " " + " ".join(str(signal.get(k) or "") for k in ("title", "summary", "type"))
    
    # Clean and tokenize
    tokens = re.findall(r"[a-z0-9]{3,}", search_text.lower())
    # Exclude common stopwords
    stopwords = {"and", "the", "for", "with", "this", "that", "from", "are", "hiring", "signal", "roles", "active", "actively", "stores", "markets", "launch"}
    keywords = [t for t in tokens if t not in stopwords]
    print("Extracted Keywords:", keywords)

    # 2. Score products
    scored_products = []
    for p in products:
        if not CompanyAnalysisService._product_allowed_by_company_evidence(p, context):
            continue
        
        # Calculate score
        score = 0
        p_text = f"{p.get('productName') or ''} {p.get('category') or ''} {p.get('description') or ''} {p.get('application') or ''} {p.get('technology') or ''}".lower()
        
        for kw in keywords:
            # Check for exact keyword match
            matches = re.findall(rf"\b{re.escape(kw)}\b", p_text)
            score += len(matches) * 2
            # Substring match
            if kw in p_text:
                score += 1
                
        # Boost if category matches "AI", "Software", "IoT", "Automation"
        cat = (p.get("category") or "").lower()
        if any(term in cat for term in ["ai", "software", "iot", "automation", "digital"]):
            score += 10
            
        scored_products.append((p, score))
        
    # Sort by score descending
    scored_products.sort(key=lambda x: x[1], reverse=True)
    
    # Return top 5
    return [item[0] for item in scored_products[:5]], scored_products[:10]

fallback_matches, top_scored = fallback_database_search(context, products)
print("\n--- Top Scored Fallback Products ---")
for p, score in top_scored:
    print(f"Product: {p.get('productName')} ({p.get('category')}) - Score: {score}")
    print(f"  Desc: {p.get('description')}")
