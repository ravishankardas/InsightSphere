# app/services/multimodal_retriever.py

import os
import uuid
from typing import Dict, List, Any
from openai import OpenAI
from app.services.embeddings import get_embeddings
from app.services.ingest import get_user_collection
from rank_bm25 import BM25Okapi 

# --- New Imports for Reranking ---
from sentence_transformers import CrossEncoder # Needs 'pip install sentence-transformers'
# ---------------------------------

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# --- Initialize Cross-Encoder Model (Load once at startup) ---
# Use a fast, high-quality reranker model. ms-marco-TinyBERT-L-2-v2 is a good choice.
try:
    print("Loading Cross-Encoder Reranker Model...")
    # This model is specifically trained for query-document pair relevance scoring.
    RERANKER_MODEL = CrossEncoder('cross-encoder/ms-marco-TinyBERT-L-2-v2')
    RERANKER_ENABLED = True
    print("Cross-Encoder Loaded.")
except Exception as e:
    print(f"Failed to load Cross-Encoder model: {e}")
    RERANKER_MODEL = None
    RERANKER_ENABLED = False
# -----------------------------------------------------------


# --- 1. RRF Score Fusion Logic ---
def reciprocal_rank_fusion(
    dense_results: List[Dict[str, Any]], 
    sparse_results: List[Dict[str, Any]], 
    k: int = 60 # Parameter k for RRF, a constant often set to 60
) -> List[Dict[str, Any]]:
    """
    Merges dense (vector) and sparse (BM25) results using Reciprocal Rank Fusion (RRF).
    """
    fused_scores = {}
    content_map = {}
    
    # Process Dense Results
    for rank, result in enumerate(dense_results):
        doc_id = result['id']
        # Rank starts at 0, so (rank + 1) is the 1-based rank
        score = 1 / (k + rank + 1)
        fused_scores[doc_id] = fused_scores.get(doc_id, 0) + score
        
        # Store content/metadata for final result construction
        content_map[doc_id] = {
            'document': result['document'],
            'metadata': result['metadata'],
            'distance': result.get('distance', None) # Keep the original distance if available
        }

    # Process Sparse Results
    for rank, result in enumerate(sparse_results):
        doc_id = result['id']
        score = 1 / (k + rank + 1)
        fused_scores[doc_id] = fused_scores.get(doc_id, 0) + score
        
        # Update map, prioritizing content from sparse search if doc_id is new
        if doc_id not in content_map:
            content_map[doc_id] = {
                'document': result['document'],
                'metadata': result['metadata'],
                'distance': None # No original distance from BM25
            }

    # Create final fused list and sort by fused score
    fused_results = []
    for doc_id, score in fused_scores.items():
        if doc_id in content_map:
            fused_results.append({
                'id': doc_id,
                'document': content_map[doc_id]['document'],
                'metadata': content_map[doc_id]['metadata'],
                'fused_score': score, # The RRF score
                'distance': content_map[doc_id]['distance'] # Original distance (or None)
            })

    # Sort by the RRF score (highest score is most relevant)
    fused_results.sort(key=lambda x: x['fused_score'], reverse=True)
    
    return fused_results
# --- End RRF Score Fusion Logic ---


def query_multimodal(query: str, user_id: str, top_k: int = 6, source_filter: str = "") -> Dict:
    """
    Query across all modalities using Hybrid Search (Dense + Sparse) + RRF + Cross-Encoder Reranking.
    
    THE RETURN STATEMENT IS STRICTLY MAINTAINED.
    """
    
    print(f"\n🔍 Query: {query}")
    
    collection = get_user_collection(user_id)
    if not collection or collection.count() == 0:
        return {
            "answer": "No documents found",
            "sources": [],
            "query": query
        }
    
    # --- 1. Define Filter Clause ---
    conditions = [{"user_id": user_id}]
    if source_filter and isinstance(source_filter, str) and source_filter.strip():
        conditions.append({"source": source_filter})
    
    where_clause = {"$and": conditions} if len(conditions) > 1 else conditions[0]
    print(f"Searching collection with filter: {where_clause}")
    
    # Fetch a larger pool of results for RRF (e.g., top_k * 5)
    retrieval_k = top_k * 5
    
    # --- 2. Dense Retrieval (Vector Search) ---
    query_emb = get_embeddings([query])[0]
    
    dense_chroma_results = collection.query(
        query_embeddings=[query_emb],
        n_results=min(retrieval_k, collection.count()),
        where=where_clause, # type: ignore
        include=['documents', 'metadatas', 'distances'] # type: ignore
    )
    dense_results = []
    if dense_chroma_results['ids'] and dense_chroma_results['ids'][0]:
        for i, doc_id in enumerate(dense_chroma_results['ids'][0]):
            dense_results.append({
                'id': doc_id,
                'document': dense_chroma_results['documents'][0][i], # type: ignore
                'metadata': dense_chroma_results['metadatas'][0][i], # type: ignore
                'distance': dense_chroma_results['distances'][0][i], # type: ignore
            })
    
    # --- 3. Sparse Retrieval (BM25 Keyword Search) ---
    all_filtered_content = collection.get(
        where=where_clause, # type: ignore
        include=['documents', 'metadatas'] # type: ignore
    )
    documents = all_filtered_content.get('documents', [])
    metadatas = all_filtered_content.get('metadatas', [])
    ids = all_filtered_content.get('ids', [])

    sparse_results = []
    if documents:
        tokenized_documents = [doc.split(" ") for doc in documents]
        bm25 = BM25Okapi(tokenized_documents)
        tokenized_query = query.split(" ")
        doc_scores = bm25.get_scores(tokenized_query)
        ranked_indices = sorted(range(len(doc_scores)), key=lambda i: doc_scores[i], reverse=True)
        
        for rank, i in enumerate(ranked_indices[:min(retrieval_k, len(documents))]):
            sparse_results.append({
                'id': ids[i],
                'document': documents[i],
                'metadata': metadatas[i], # type: ignore
                'score': doc_scores[i] 
            })

    # --- 4. Reciprocal Rank Fusion (RRF) ---
    fused_results = reciprocal_rank_fusion(dense_results, sparse_results)
    
    # --- 5. Reranking with Cross-Encoder (NEW STEP) ---
    if RERANKER_ENABLED and fused_results:
        # We rerank the top N results from RRF (e.g., top_k * 2)
        rerank_n = max(top_k + 4, top_k * 2) 
        
        # Select the subset to rerank
        to_rerank = fused_results[:rerank_n]
        remaining_results = fused_results[rerank_n:]

        # Create (query, document) pairs
        sentence_pairs = [[query, item['document']] for item in to_rerank]
        
        print(f"  🧠 Reranking {len(to_rerank)} chunks...")
        
        # Get scores from the Cross-Encoder (higher score = better relevance)
        rerank_scores = RERANKER_MODEL.predict(sentence_pairs) # type: ignore

        # Apply new scores to the results
        for i, score in enumerate(rerank_scores):
            to_rerank[i]['rerank_score'] = score
        
        # Re-sort the reranked subset by the Cross-Encoder score
        to_rerank.sort(key=lambda x: x['rerank_score'], reverse=True)
        
        # Combine the re-ranked top N with the remaining results 
        final_chunks_all = to_rerank + remaining_results
        
        print(f"  ✅ Reranking complete. New top item score: {to_rerank[0]['rerank_score']:.4f}")
    else:
        # If reranker is disabled, or no results, use RRF results directly
        final_chunks_all = fused_results
    
    # Truncate the final list to the user's requested top_k
    final_chunks = final_chunks_all[:top_k]
    
    # --- 6. Final Answer Generation and Output Construction ---
    context: List[str] = []
    sources: List[Dict[str, Any]] = [] 

    for i, item in enumerate(final_chunks):
        doc = item['document']
        meta = item['metadata']
        distance = item.get('distance') # Keep the original distance for frontend display compatibility
        
        # Apply the same content cleaning logic as in the original file
        display_content = doc
        if doc.startswith('[TABLE'):
            parts = doc.split(']', 1)
            display_content = parts[1].strip() if len(parts) > 1 else doc
        elif doc.startswith('[IMAGE'):
            parts = doc.split(']', 1)
            display_content = parts[1].strip() if len(parts) > 1 else doc

        sources.append({
            # Structure required by the original return:
            "index": i + 1,
            "type": meta.get('type', 'text'),
            "content": display_content,  
            "snippet": display_content[:200] + "..." if len(display_content) > 200 else display_content, 
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
    
    # Generate answer with OpenAI (same as before)
    if OPENAI_API_KEY and context:
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        prompt = f"""Answer the question based on the provided context. 
Be specific and reference sources by their numbers [1], [2], etc.

Context from document:
{chr(10).join(context[:top_k])}

Question: {query}

Instructions:
- Provide a clear, concise answer
- Reference sources using [1], [2], etc.
- If answer not in context, say so

Answer:"""
        
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300
        )
        
        answer = response.choices[0].message.content
    else:
        answer = "Found content but OpenAI not configured"
    
    print(f"✅ Found {len(sources)} sources (Reranked Hybrid Search)")
    
    # Return statement strictly maintained
    return {
        "answer": answer,
        "sources": sources,  
        "query": query
    }