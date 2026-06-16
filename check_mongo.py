import os
import sys

# Set up Django environment
sys.path.append(r"d:\sdc_backend")
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from features.companydata.service import CompanyDataService

def check_db():
    db = CompanyDataService._get_db()
    client = db.client
    companydetails_db = client["companydetails"]
    
    print("Collections:", companydetails_db.list_collection_names())
    
    for coll_name in ["products", "case_studies", "crm_records", "meeting_notes", "proposals", "opportunities"]:
        coll = companydetails_db[coll_name]
        count = coll.count_documents({})
        print(f"\nCollection '{coll_name}' count: {count}")

if __name__ == "__main__":
    check_db()
