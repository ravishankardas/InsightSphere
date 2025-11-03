"""
ULTRA-FAST Text-Only PDF Ingest
Use this when you don't need images/tables processing
~10x faster than multimodal
"""
import uuid
from typing import Dict, List
import PyPDF2 # type: ignore
from io import BytesIO
from app.services.embeddings import get_embeddings
from app.services.ingest import get_user_collection


def extract_text_only(pdf_bytes: bytes) -> str:
    """Fast text extraction using PyPDF2 (no AI processing)"""
    pdf_file = BytesIO(pdf_bytes)
    pdf_reader = PyPDF2.PdfReader(pdf_file)
    
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text() + "\n\n"
    
    return text.strip()


def chunk_text_simple(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    """Simple chunking by character count with overlap"""
    chunks = []
    start = 0
    text_len = len(text)
    
    while start < text_len:
        end = start + chunk_size
        chunk = text[start:end]
        
        if chunk.strip():
            chunks.append(chunk.strip())
        
        start += (chunk_size - overlap)
    
    return chunks


def ingest_text_only_pdf(pdf_bytes: bytes, user_id: str, filename: str) -> Dict:
    """Ultra-fast text-only PDF ingestion
    
    SPEED: ~10x faster than multimodal
    USE WHEN: You don't need images/tables processing
    
    Args:
        pdf_bytes: PDF file content
        user_id: User identifier
        filename: Name of the file
    """
    
    print(f"\n{'='*60}")
    print(f"FAST TEXT-ONLY INGEST: {filename}")
    print(f"{'='*60}")
    
    # Step 1: Extract text (very fast)
    print("📄 Extracting text...")
    text = extract_text_only(pdf_bytes)
    
    # Step 2: Chunk text
    print("✂️  Chunking text...")
    chunks = chunk_text_simple(text, chunk_size=1000, overlap=200)
    
    print(f"✅ Created {len(chunks)} chunks")
    
    # Step 3: Prepare for ChromaDB
    all_docs = chunks
    all_metas = [
        {
            "type": "text",
            "source": filename,
            "user_id": user_id,
            "chunk_index": i
        }
        for i in range(len(chunks))
    ]
    all_ids = [str(uuid.uuid4()) for _ in chunks]
    
    # Step 4: Generate embeddings
    print(f"🔢 Generating embeddings...")
    embeddings = get_embeddings(all_docs)
    
    # Step 5: Store in ChromaDB
    print(f"💾 Storing in database...")
    collection = get_user_collection(user_id)
    collection.add(
        ids=all_ids,
        documents=all_docs,
        metadatas=all_metas, # type: ignore
        embeddings=embeddings
    )
    
    print(f"✅ Done! Stored {len(all_docs)} chunks")
    print(f"{'='*60}\n")
    
    return {
        "n_chunks": len(chunks),
        "n_tables": 0,
        "n_images": 0,
        "total_items": collection.count()
    }