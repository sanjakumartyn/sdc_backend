import os
import sys
import random

# Set up Django environment
sys.path.append(r'd:\sdc_backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from features.companydata.service import CompanyDataService

def generate_products():
    categories = [
        "AI & Generative AI", "Data & Analytics", "Cloud Services", 
        "Cybersecurity", "Enterprise Automation", "Industry Solutions",
        "Customer Success", "Sales Intelligence", "Consulting Services",
        "CRM Solutions", "ERP Solutions", "Integration Services"
    ]
    
    techs = ["Generative AI", "Machine Learning", "RPA", "Cloud Native", "IoT", "Blockchain", "Data Lake", "Zero Trust", "DevOps", "FinOps", "Predictive Analytics"]
    units = ["Annual License", "Project", "Monthly Subscription", "Per User/Month"]
    
    industries = ["Retail", "Manufacturing", "BFSI", "Healthcare", "Telecom", "All Industries", "Enterprise", "Technology"]
    
    products = []
    
    # Core products based on user's sample
    core_products = [
        ("AI Sales Intelligence Platform", "AI & Generative AI", "Improves sales conversion rates"),
        ("Enterprise Knowledge Assistant", "AI & Generative AI", "Reduces employee search time"),
        ("Predictive Analytics Engine", "Data & Analytics", "Improves forecasting accuracy"),
        ("AWS Migration Service", "Cloud Services", "Cloud modernization"),
        ("Security Operations Center", "Cybersecurity", "Improves security posture"),
        ("Invoice Automation Solution", "Enterprise Automation", "Reduces manual processing"),
        ("Retail Analytics Platform", "Industry Solutions", "Improves sales performance"),
        ("Enterprise CRM Modernization", "CRM Solutions", "Improves customer engagement")
    ]
    
    for i in range(1, 201):
        if i <= len(core_products):
            name, cat, val = core_products[i-1]
        else:
            cat = random.choice(categories)
            name = f"{random.choice(['Enterprise', 'Smart', 'Advanced', 'Digital', 'Cloud', 'AI-Driven', 'NextGen'])} {cat.split(' ')[0]} {random.choice(['Platform', 'Suite', 'Engine', 'Accelerator', 'Hub', 'Solution'])} {i}"
            val = f"Improves {cat.lower()} efficiency"
            
        products.append({
            "serviceId": f"IT{i:03d}",
            "serviceName": name,
            "category": cat,
            "description": f"Enterprise-grade {name.lower()} designed for modern businesses.",
            "targetIndustry": random.choice(industries),
            "pricing": random.randint(25, 250) * 1000,
            "unit": random.choice(units),
            "technology": random.choice(techs),
            "businessValue": val,
            "useCase": f"{cat} Optimization"
        })
        
    return products

def seed_database():
    print("Connecting to MongoDB...")
    db = CompanyDataService._get_db()
    client = db.client
    company_db = client["company_details"]
    products_col = company_db["products"]
    
    # Delete existing to prevent duplicates
    current_count = products_col.count_documents({})
    print(f"Found {current_count} existing products. Clearing collection...")
    products_col.delete_many({})
    
    # Generate and insert 200 products
    print("Generating 200 products...")
    new_products = generate_products()
    
    print("Inserting into database...")
    products_col.insert_many(new_products)
    
    final_count = products_col.count_documents({})
    print(f"Success! Database now has {final_count} products.")

if __name__ == "__main__":
    seed_database()
