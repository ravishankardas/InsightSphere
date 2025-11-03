"""
Simple Multi-Modal Retriever with Source Highlighting
"""
import os
from typing import Dict, List
from openai import OpenAI
from app.services.embeddings import get_embeddings
from app.services.ingest import get_user_collection

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


def query_multimodal(query: str, user_id: str, top_k: int = 6, source_filter: str = "") -> Dict:
    """Query across all modalities with detailed source snippets"""
    
    # --- DEBUG LINE ---
    # print(f"\n--- DEBUG: Incoming source_filter: {repr(source_filter)} ---")
    # ------------------
    print(f"\n🔍 Query: {query}")
    
    # Get collection
    collection = get_user_collection(user_id)
    if not collection or collection.count() == 0:
        return {
            "answer": "No documents found",
            "sources": [],
            "citations": []
        }
    
    # Generate query embedding
    query_emb = get_embeddings([query])[0]
    results = collection.query(
        query_embeddings=[query_emb],
        n_results=min(top_k, max(1, collection.count())),
        where={
            "$and": [
                {"user_id": user_id},
                {"source": source_filter}
            ]
        }  
    )

    # --- END CRITICAL FIX AREA ---

    # print(results)
    # Format results with detailed snippets
    sources = []
    context = []
    
    if results and results.get('ids') and len(results['ids'][0]) > 0:
        for i in range(len(results['ids'][0])):
            doc = results['documents'][0][i] # type: ignore
            meta = results['metadatas'][0][i] # type: ignore
            distance = results['distances'][0][i] if results.get('distances') else None # type: ignore
            
            content_type = meta.get('type', 'text')
            
            # Get clean snippet (remove [TABLE], [IMAGE] prefixes for display)
            display_content = doc
            if doc.startswith('[TABLE'):
                # Extract just the summary part
                parts = doc.split(']', 1)
                display_content = parts[1].strip() if len(parts) > 1 else doc
            elif doc.startswith('[IMAGE'):
                # Extract just the description
                parts = doc.split(']', 1)
                display_content = parts[1].strip() if len(parts) > 1 else doc
            
            sources.append({
                "index": i + 1,
                "type": content_type,
                "content": display_content,  # Full content for highlighting
                "snippet": display_content[:200] + "..." if len(display_content) > 200 else display_content,  # Preview
                "distance": round(distance, 4) if distance else None,
                "metadata": {
                    "source": meta.get('source', 'Unknown'),
                    "page": meta.get('page', 'N/A'),
                    "table_index": meta.get('table_index'),
                    "image_index": meta.get('image_index')
                }
            })
            
            # Build context for GPT
            context.append(f"[Source {i+1}] {doc}")
    
    # Generate answer with OpenAI
    if OPENAI_API_KEY and context:
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        prompt = f"""Answer the question based on the provided context. 
Be specific and reference sources by their numbers [1], [2], etc.

Context from document:
{chr(10).join(context[:5])}

Question: {query}

Instructions:
- Provide a clear, concise answer
- Reference sources using [1], [2], etc.
- If answer not in context, say so

Answer:"""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300
        )
        
        answer = response.choices[0].message.content
    else:
        answer = "Found content but OpenAI not configured"
    
    print(f"✅ Found {len(sources)} sources")
    
    return {
        "answer": answer,
        "sources": sources,  # Detailed sources with full content for highlighting
        "query": query
    }