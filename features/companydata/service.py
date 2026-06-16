from typing import List, Dict, Any, Tuple
from bson import ObjectId
from bson.errors import InvalidId
from django.db import connections
from common.exception.base_exception import BadRequestException, NotFoundException

class CompanyDataService:
    @staticmethod
    def _get_db():
        """Retrieve the pymongo database instance from Django connection."""
        try:
            connection = connections['default']
            if getattr(connection, 'vendor', None) != 'mongodb':
                raise BadRequestException(
                    "Company data requires MongoDB. Check that the default database ENGINE is django_mongodb_backend."
                )

            db = connection.get_database() if hasattr(connection, 'get_database') else getattr(connection, 'database', None)
            if db is None:
                raise BadRequestException(
                    "MongoDB connection is not available. Check that the default database ENGINE is django_mongodb_backend."
                )
            return db
        except BadRequestException:
            raise
        except Exception as e:
            import logging
            logging.error(f"Database connection error: {str(e)}", exc_info=True)
            raise BadRequestException(
                f"Failed to connect to MongoDB: {str(e)}. Verify DATABASE_URL, username, and password in .env"
            )

    @staticmethod
    def get_documents(collection_name: str, limit: int = 10, offset: int = 0) -> Tuple[List[Dict[str, Any]], int]:
        db = CompanyDataService._get_db()
        collection = db[collection_name]
        
        total_count = collection.count_documents({})
        cursor = collection.find({}).skip(offset).limit(limit)
        
        documents = []
        for doc in cursor:
            # Convert ObjectId to string for JSON serialization
            doc['_id'] = str(doc['_id'])
            documents.append(doc)
            
        return documents, total_count

    @staticmethod
    def get_all_data(limit_per_collection: int = 50) -> Dict[str, List[Dict[str, Any]]]:
        db = CompanyDataService._get_db()
        # Avoid system collections
        collections = [name for name in db.list_collection_names() if not name.startswith('system.')]
        
        result = {}
        for col_name in collections:
            collection = db[col_name]
            cursor = collection.find({}).limit(limit_per_collection)
            documents = []
            for doc in cursor:
                doc['_id'] = str(doc['_id'])
                documents.append(doc)
            result[col_name] = documents
            
        return result


    @staticmethod
    def update_document(collection_name: str, document_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        db = CompanyDataService._get_db()
        collection = db[collection_name]
        
        try:
            obj_id = ObjectId(document_id)
        except InvalidId:
            raise BadRequestException(f"Invalid document ID format: {document_id}")
            
        # Perform update
        result = collection.update_one(
            {"_id": obj_id},
            {"$set": update_data}
        )
        
        if result.matched_count == 0:
            raise NotFoundException(f"Document with ID {document_id} not found in {collection_name}")
            
        # Retrieve the updated document
        updated_doc = collection.find_one({"_id": obj_id})
        if updated_doc:
            updated_doc['_id'] = str(updated_doc['_id'])
            return updated_doc
            
        raise BadRequestException("Failed to retrieve document after update")
