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
    
    colls = ['case studies', 'crm records', 'proposal documents', 'past meeting records', 'products']
    for c in colls:
        coll = companydetails_db[c]
        count = coll.count_documents({})
        print(f"\nCollection '{c}' count: {count}")
        if count > 0:
            doc = coll.find_one()
            print("Sample doc keys:", list(doc.keys()))
            print("Sample doc:", doc)

if __name__ == "__main__":
    check_db()
