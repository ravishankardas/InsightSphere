# backend/app/services/retriever.py
import os
import re
from typing import List, Dict
import chromadb
# from openai import OpenAI
from langfuse.openai import openai # type: ignore
from .embeddings import get_embeddings

from app.logger import setup_logger

from dotenv import load_dotenv
load_dotenv()

CHROMA_DIR = os.environ.get("CHROMA_DIR", "/app/chroma_db_per")
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", None)

_client = None
_collections = {}  # Cache collections by user_id
_openai_client = None
logger = setup_logger()

def get_openai_key():
    # global _openai_client
    # if _openai_client is None and OPENAI_KEY:
    #     _openai_client = openai(api_key=OPENAI_KEY)
    # return _openai_client

    return OPENAI_KEY

def get_chroma_client():
    """Get or create the ChromaDB client"""
    global _client
    if _client is None:
        try:
            _client = chromadb.PersistentClient(path=CHROMA_DIR)
            logger.info(f"✓ ChromaDB PersistentClient initialized at {CHROMA_DIR}")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize ChromaDB PersistentClient: {e}")
    return _client

def sanitize_collection_name(user_id: str) -> str:
    """
    Sanitize user_id to make a valid ChromaDB collection name.
    ChromaDB requires: 3-512 chars, [a-zA-Z0-9._-], start/end with alphanumeric
    """
    # Replace @ with _at_ and dots after @ with underscores
    sanitized = user_id.replace('@', '_at_').replace('.', '_')
    # Remove any other invalid characters
    sanitized = re.sub(r'[^a-zA-Z0-9._-]', '_', sanitized)
    # Ensure it starts and ends with alphanumeric
    sanitized = re.sub(r'^[^a-zA-Z0-9]+|[^a-zA-Z0-9]+$', '', sanitized)
    # Create collection name with user_ prefix
    collection_name = f"user_{sanitized}_docs"
    return collection_name

def get_user_collection(user_id: str):
    """Get or create a collection specific to a user"""
    global _collections
    
    if user_id in _collections:
        return _collections[user_id]
    
    client = get_chroma_client()
    collection_name = sanitize_collection_name(user_id)
    
    try:
        collection = client.get_or_create_collection(name=collection_name)
        count = collection.count()
        logger.info(f"✓ Collection '{collection_name}' loaded with {count} items")
        _collections[user_id] = collection
        return collection
    except Exception as e:
        raise RuntimeError(f"Failed to get/create collection '{collection_name}': {e}")

def retrieve(query: str, user_id: str, top_k: int = 4):
    """Retrieve documents for a specific user"""
    logger.info(f"\n{'='*60}")
    logger.info(f"RETRIEVE for user: {user_id}")
    logger.info(f"Query: '{query}'")
    logger.info(f"{'='*60}")
    
    collection = get_user_collection(user_id)
    
    count = collection.count()
    logger.info(f"User's collection has {count} documents")
    
    if count == 0:
        logger.debug(f"⚠ User {user_id} has no documents uploaded")
        return []
    
    # Generate query embedding
    query_embedding = get_embeddings([query])[0]
    logger.info(f"✓ Query embedding generated: dimension={len(query_embedding)}")
    
    # Query the collection
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, count)
    )
    
    docs = []
    if (
        results
        and results.get("documents")
        and len(results["ids"]) > 0
        and len(results["ids"][0]) > 0
    ):
        metadatas = results.get("metadatas")
        distances = results.get("distances")
        documents = results.get("documents")
        
        for i in range(len(results["ids"][0])):
            doc = {
                "id": results["ids"][0][i],
                "document": documents[0][i], # type: ignore
                "metadata": metadatas[0][i] if metadatas else None,
                "distance": distances[0][i] if distances else None
            }
            docs.append(doc)
            logger.info(f"  [{i}] Distance: {doc['distance']:.4f} | {doc['document'][:80]}...")
    
    logger.info(f"✓ Returning {len(docs)} documents")
    return docs

def call_openai_system_prompt(context_snippets: List[str], question: str):
    if not context_snippets:
        return {
            "answer": "No context available to answer the question.",
            "sources": []
        }
    
    client_api_key = get_openai_key()
    
    if not client_api_key:
        return {
            "answer": "OpenAI API key not set. Here are retrieved snippets:\n\n" + "\n\n".join(context_snippets),
            "sources": [{"snippet": s[0:100], "index": i} for i, s in enumerate(context_snippets, start=1)]
        }
    
    prompt = "You are an expert research assistant. Use the context below to answer the question concisely (3-5 sentences). If answer not in context, say 'I don't know; check sources.' Provide sources with snippet indices.\n\nContext:\n"
    for i, s in enumerate(context_snippets, start=1):
        prompt += f"[{i}] {s}\n\n"
    prompt += f"Question: {question}\nAnswer:"
    
    try:
        resp = openai.chat.completions.create(
            model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
            temperature=0.0
        )
        text = resp.choices[0].message.content
        return {
            "answer": text,
            "sources": [{"snippet": s, "index": i} for i, s in enumerate(context_snippets, start=1)]
        }
    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        return {
            "answer": f"Error calling OpenAI API: {str(e)}",
            "sources": [{"snippet": s, "index": i} for i, s in enumerate(context_snippets, start=1)]
        }

def retrieve_and_answer(query: str, user_id: str, top_k: int = 4) -> Dict:
    """Retrieve and answer for a specific user"""
    docs = retrieve(query, user_id, top_k=top_k)
    snippets = [d["document"] for d in docs if d.get("document")]
    
    resp = call_openai_system_prompt(snippets, query)
    
    return {
        "answer": resp["answer"],
        "sources": resp.get("sources", []),
        "retrieved": [{"id": d["id"], "meta": d["metadata"], "distance": d["distance"]} for d in docs]
    }