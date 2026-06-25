import os
import sys
import random

# Set up Django environment
sys.path.append(r'd:\sdc_backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from features.companydata.service import CompanyDataService

def seed_case_studies():
    print("Connecting to MongoDB...")
    db = CompanyDataService._get_db()
    client = db.client
    company_db = client["company_details"]
    case_studies_col = company_db["case studies"]
    
    # Delete existing to prevent duplicates
    current_count = case_studies_col.count_documents({})
    print(f"Found {current_count} existing case studies. Clearing collection...")
    case_studies_col.delete_many({})
    
    # Base templates for generating 200 case studies
    industries = ["Retail", "BFSI", "Healthcare", "Manufacturing", "Telecom", "Technology", "Logistics", "Energy"]
    challenges = [
        "Legacy on-premise servers causing downtime.",
        "High rate of false positives in monitoring.",
        "Need to secure patient/customer data.",
        "Siloed data across global locations.",
        "Call center overwhelmed by inquiries.",
        "Manual processes slowing down operations.",
        "Lack of visibility into supply chain.",
        "Increasing cybersecurity threats and breaches.",
        "Poor customer retention and engagement.",
        "Inefficient resource allocation."
    ]
    solutions = [
        "Migrated to scalable AWS architecture.",
        "Deployed custom Machine Learning model.",
        "Rolled out Zero Trust Security Framework.",
        "Implemented Enterprise Data Lake.",
        "Integrated AI Customer Support Agent.",
        "Automated workflows with RPA.",
        "Deployed real-time IoT tracking.",
        "Implemented SIEM Analytics Platform.",
        "Launched Omnichannel Commerce Platform.",
        "Utilized AI Demand Forecasting."
    ]
    results = [
        "Zero downtime, 40% reduction in costs.",
        "Reduced errors by 60%, saved 1200 hours.",
        "Achieved 100% compliance audit pass rate.",
        "Real-time visibility, reduced delays by 25%.",
        "Deflected 45% of tickets, improved CSAT.",
        "Increased throughput by 300%.",
        "Cut logistics costs by 15%.",
        "Blocked 99.9% of advanced threats.",
        "Increased sales conversions by 22%.",
        "Optimized inventory, saving $2M annually."
    ]
    companies = [
        "Global Retail Corp", "FinTech Innovators", "HealthPlus Network", "AutoMakers Int'l",
        "NextGen Telecom", "TechForward Inc", "LogisTech Solutions", "EcoEnergy Corp",
        "MegaBank Partners", "CloudFirst Systems", "DataDriven Logistics", "SecureNet Security"
    ]
    
    case_studies = []
    
    for i in range(1, 201):
        case_studies.append({
            "caseStudyId": f"CS{i:03d}",
            "client": random.choice(companies) + f" {random.randint(1, 99)}",
            "title": f"Enterprise Transformation {i}",
            "industry": random.choice(industries),
            "challenge": random.choice(challenges),
            "solution": random.choice(solutions),
            "results": random.choice(results)
        })
    
    print("Inserting 200 case studies into database...")
    case_studies_col.insert_many(case_studies)
    
    final_count = case_studies_col.count_documents({})
    print(f"Success! Database now has {final_count} case studies.")

if __name__ == "__main__":
    seed_case_studies()
