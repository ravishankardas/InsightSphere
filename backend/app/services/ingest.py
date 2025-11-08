# backend/app/services/ingest.py
import os
import re
import uuid
import tempfile
import pdfplumber
from .embeddings import get_embeddings
import chromadb
from typing import Optional
from dotenv import load_dotenv
load_dotenv()
from app.logger import setup_logger
logger = setup_logger()

CHROMA_DIR = os.environ.get("CHROMA_DIR", "./chroma_db")

_client = None
_collections = {}

def get_chroma_client():
    """Get or create the ChromaDB client"""
    global _client
    if _client is None:
        try:
            _client = chromadb.PersistentClient(path=CHROMA_DIR)
            logger.info(f"✓ Ingest: ChromaDB PersistentClient initialized at {CHROMA_DIR}")
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
    client.heartbeat()
    collection_name = sanitize_collection_name(user_id)
    
    try:
        collection = client.get_or_create_collection(name=collection_name)
        count = collection.count()
        # logger.info(f"✓ Ingest: Collection '{collection_name}' loaded with {count} items")
        _collections[user_id] = collection
        return collection
    except Exception as e:
        raise RuntimeError(f"Failed to get/create collection '{collection_name}': {e}")

def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
        tf.write(pdf_bytes)
        tmp_path = tf.name
    text = ""
    try:
        with pdfplumber.open(tmp_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += "\n\n" + page_text
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass
    return text

def chunk_text(text: str, chunk_size: int = 500, chunk_overlap: int = 50):
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = words[i:i+chunk_size]
        chunks.append(" ".join(chunk))
        i += chunk_size - chunk_overlap
    return chunks

def ingest_pdf(pdf_bytes: bytes, user_id: str, filename: Optional[str] = None):
    """Ingest a PDF for a specific user"""
    logger.info(f"\n{'='*60}")
    logger.info(f"INGESTING PDF for user: {user_id}")
    logger.info(f"Filename: {filename or 'uploaded'}")
    logger.info(f"{'='*60}")
    
    text = extract_text_from_pdf_bytes(pdf_bytes)
    logger.info(f"Extracted {len(text)} characters from PDF")
    
    if not text.strip():
        raise ValueError("No text could be extracted from the PDF")
    
    chunks = chunk_text(text)
    logger.debug(f"Created {len(chunks)} chunks")
    
    ids = []
    metadatas = []
    docs = []
    for i, c in enumerate(chunks):
        doc_id = f"{uuid.uuid4()}"
        ids.append(doc_id)
        metadatas.append({
            "source": filename or "uploaded",
            "chunk_index": i,
            "user_id": user_id
        })
        docs.append(c)
    
    logger.info(f"Generating embeddings for {len(docs)} chunks...")
    embeddings = get_embeddings(docs)
    logger.info(f"✓ Embeddings generated: {len(embeddings)} vectors")

    collection = get_user_collection(user_id)
    
    logger.info(f"Adding {len(chunks)} chunks to user's collection...")
    collection.add(
        ids=ids,
        metadatas=metadatas,
        documents=docs,
        embeddings=embeddings
    )
    
    new_count = collection.count()
    logger.info(f"✓ Successfully added chunks. User's collection now has {new_count} total items")
    logger.info(f"{'='*60}\n")
    
    return {"n_chunks": len(chunks), "total_items": new_count, "user_id": user_id}