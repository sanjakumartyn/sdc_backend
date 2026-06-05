import os
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from features.companydata.service import CompanyDataService

def test_company_data():
    db = CompanyDataService._get_db()
    test_collection = 'test_crm_records'
    
    # 1. Insert a test document directly using PyMongo
    print("Inserting test document...")
    result = db[test_collection].insert_one({
        "name": "Test Company",
        "status": "Lead"
    })
    doc_id = str(result.inserted_id)
    print(f"Inserted document ID: {doc_id}")
    
    try:
        # 2. Test Get Service
        print("Testing get_documents...")
        docs, total = CompanyDataService.get_documents(test_collection)
        print(f"Total documents: {total}")
        print(f"Documents: {docs}")
        assert any(d['_id'] == doc_id for d in docs), "Inserted document not found!"
        
        # 3. Test Update Service
        print("Testing update_document...")
        updated_doc = CompanyDataService.update_document(
            test_collection, 
            doc_id, 
            {"status": "Customer", "new_field": "added"}
        )
        print(f"Updated document: {updated_doc}")
        assert updated_doc['status'] == 'Customer', "Update failed!"
        assert updated_doc['new_field'] == 'added', "New field not added!"
        
        print("All tests passed successfully!")
    finally:
        # Clean up
        print("Cleaning up test data...")
        db[test_collection].delete_many({"_id": result.inserted_id})

if __name__ == '__main__':
    test_company_data()
