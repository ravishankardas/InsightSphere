# app/services/document_manager.py

from typing import List
# Assuming get_user_collection is a known utility for ChromaDB
from app.services.ingest import get_user_collection 

def get_user_documents(user_id: str) -> List[str]:
    """
    Retrieves a unique list of filenames (source metadata) uploaded by the user.
    """
    collection = get_user_collection(user_id)
    if not collection:
        return []

    # Query ChromaDB for all unique 'source' metadatas for the user_id
    results = collection.get(
        where={"user_id": user_id},
        include=['metadatas']
    )

    if not results or 'metadatas' not in results:
        return []

    # Extract unique source names from the metadatas
    source_names = set()
    for metadata in results['metadatas']: # type: ignore
        if metadata and 'source' in metadata:
            source_names.add(metadata['source'])

    return sorted(list(source_names))

def delete_document(user_id: str, filename: str) -> bool:
    """
    Permanently deletes a document and all its associated chunks from ChromaDB.
    """
    collection = get_user_collection(user_id)
    if not collection:
        return False
        
    # ChromaDB deletes items matching the 'where' clause.
    try:
        collection.delete(
            where={
                "$and": [ 
                    {"user_id": user_id},
                    {"source": filename}
                ]
            }
        )
        return True
    except Exception as e:
        print(f"Error deleting document {filename} for user {user_id}: {e}")
        return False