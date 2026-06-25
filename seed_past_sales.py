import os
import sys

# Set up Django environment
sys.path.append(r'd:\sdc_backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from features.companydata.service import CompanyDataService

def seed_sales():
    db = CompanyDataService._get_db()
    client = db.client
    company_db = client["company_details"]
    past_sales_col = company_db["past_sales"]

    # Clear existing
    past_sales_col.delete_many({})

    sales = [
        {"dealName": "AI Engine Implementation", "dealStatus": "Won", "saleStatus": "Completed", "dealValue": 4500000},
        {"dealName": "Cloud Migration", "dealStatus": "Won", "saleStatus": "Completed", "dealValue": 3200000},
        {"dealName": "Security Audit", "dealStatus": "Won", "saleStatus": "Completed", "dealValue": 1500000},
        {"dealName": "Data Warehouse", "dealStatus": "Lost", "saleStatus": "Cancelled", "dealValue": 5000000},
        {"dealName": "ERP Setup", "dealStatus": "Open", "saleStatus": "Pending", "dealValue": 2000000},
        {"dealName": "CRM Migration", "dealStatus": "Won", "saleStatus": "Completed", "dealValue": 3300000},
    ]

    past_sales_col.insert_many(sales)
    print("Successfully seeded past_sales collection.")

if __name__ == "__main__":
    seed_sales()
