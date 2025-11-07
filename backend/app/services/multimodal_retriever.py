# app/services/multimodal_retriever.py

import hashlib
import os
import re
import time
import uuid
from typing import Dict, List, Any, Optional
from openai import OpenAI
from app.services.embeddings import get_embeddings
from app.services.ingest import get_user_collection
from rank_bm25 import BM25Okapi 
from dotenv import load_dotenv
import redis # type: ignore
import json
import hashlib
from sentence_transformers import CrossEncoder # Needs 'pip install sentence-transformers'
from sentence_transformers import SentenceTransformer
import numpy as np
from app.logger import setup_logger
logger = setup_logger()
# --- Agent Imports ---
from app.services.rag_agent import RAG_AGENT_APP, AgentState  # type: ignore
# ---------------------

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# --- Initialize Cross-Encoder Model (Load once at startup) ---
try:
    logger.info("Loading Cross-Encoder Reranker Model...")
    RERANKER_MODEL = CrossEncoder('cross-encoder/ms-marco-TinyBERT-L-2-v2')
    RERANKER_ENABLED = True
    logger.info("Cross-Encoder Loaded.")
except Exception as e:
    logger.error(f"Failed to load Cross-Encoder model: {e}")
    RERANKER_MODEL = None
    RERANKER_ENABLED = False
# -----------------------------------------------------------




# --- 1. RRF Score Fusion Logic ---
def reciprocal_rank_fusion(
    dense_results: List[Dict[str, Any]], 
    sparse_results: List[Dict[str, Any]], 
    k: int = 60 
) -> List[Dict[str, Any]]:
    """
    Merges dense (vector) and sparse (BM25) results using Reciprocal Rank Fusion (RRF).
    (Logic remains unchanged)
    """
    fused_scores = {}
    content_map = {}
    
    # Process Dense Results
    for rank, result in enumerate(dense_results):
        doc_id = result['id']
        score = 1 / (k + rank + 1)
        fused_scores[doc_id] = fused_scores.get(doc_id, 0) + score
        
        content_map[doc_id] = {
            'document': result['document'],
            'metadata': result['metadata'],
            'distance': result.get('distance', None) 
        }

    # Process Sparse Results
    for rank, result in enumerate(sparse_results):
        doc_id = result['id']
        score = 1 / (k + rank + 1)
        fused_scores[doc_id] = fused_scores.get(doc_id, 0) + score
        
        if doc_id not in content_map:
            content_map[doc_id] = {
                'document': result['document'],
                'metadata': result['metadata'],
                'distance': None 
            }

    # Create final fused list and sort by fused score
    fused_results = []
    for doc_id, score in fused_scores.items():
        if doc_id in content_map:
            fused_results.append({
                'id': doc_id,
                'document': content_map[doc_id]['document'],
                'metadata': content_map[doc_id]['metadata'],
                'fused_score': score, 
                'distance': content_map[doc_id]['distance'] 
            })

    fused_results.sort(key=lambda x: x['fused_score'], reverse=True)
    
    return fused_results
# --- End RRF Score Fusion Logic ---


# --- MODIFIED: query_multimodal is now async and uses ainvoke ---
async def query_multimodal(query: str, user_id: str, top_k: int = 6, source_filter: str = "file.pdf", email_present: bool=False) -> Dict:
    """
    Query across all modalities using Hybrid Search (Dense + Sparse) + RRF + Cross-Encoder Reranking
    and delegates final answer generation to the RAG Agent (via ainvoke).
    """
    
    # logger.info(f"\n🔍 Query: {query}, file_name: {source_filter}, user_id: {user_id}, top_k: {top_k}\n")
    
    collection = get_user_collection(user_id)
    if not collection or collection.count() == 0:
        return {
            "answer": "Collection is empty or API Key is not configured.",
            "sources": [],
            "cached": False,
            "action_performed": False
        }
    
    # --- 1. Define Filter Clause (unchanged) ---
    conditions = [{"user_id": user_id}]
    if source_filter and isinstance(source_filter, str) and source_filter.strip():
        conditions.append({"source": source_filter})
    
    where_clause = {"$and": conditions} if len(conditions) > 1 else conditions[0]
    retrieval_k = top_k * 5
    
    # --- 2. Dense Retrieval (Vector Search) (unchanged) ---
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
    
    # --- 3. Sparse Retrieval (BM25 Keyword Search) (unchanged) ---
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
        
        for i in ranked_indices[:min(retrieval_k, len(documents))]:
            sparse_results.append({
                'id': ids[i],
                'document': documents[i],
                'metadata': metadatas[i], # type: ignore
                'score': doc_scores[i] 
            })

    # --- 4. Reciprocal Rank Fusion (RRF) (unchanged) ---
    fused_results = reciprocal_rank_fusion(dense_results, sparse_results)
    
    # --- 5. Reranking with Cross-Encoder (unchanged) ---
    if RERANKER_ENABLED and fused_results:
        rerank_n = max(top_k + 4, top_k * 2) 
        to_rerank = fused_results[:rerank_n]
        remaining_results = fused_results[rerank_n:]

        sentence_pairs = [[query, item['document']] for item in to_rerank]
        rerank_scores = RERANKER_MODEL.predict(sentence_pairs) # type: ignore

        for i, score in enumerate(rerank_scores):
            to_rerank[i]['rerank_score'] = score
        
        to_rerank.sort(key=lambda x: x['rerank_score'], reverse=True)
        final_chunks_all = to_rerank + remaining_results
    else:
        final_chunks_all = fused_results
    
    # Truncate the final list to the user's requested top_k
    final_chunks = final_chunks_all[:top_k]
    
    # --- 6. Final Answer Generation and Output Construction (MODIFIED) ---
    context: List[str] = []
    sources: List[Dict[str, Any]] = [] 

    for i, item in enumerate(final_chunks):
        doc = item['document']
        meta = item['metadata']
        distance = item.get('distance') 
        
        display_content = doc
        if doc.startswith('[TABLE'):
            parts = doc.split(']', 1)
            display_content = parts[1].strip() if len(parts) > 1 else doc
        elif doc.startswith('[IMAGE'):
            parts = doc.split(']', 1)
            display_content = parts[1].strip() if len(parts) > 1 else doc

        sources.append({
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
        
        # Build context for the agent
        context.append(doc) # Agent's prompt will handle source numbers
    
    # 6b. Agent Execution (NEW LOGIC)
    
    answer = "Error: Could not process request."
    action_performed = False
    cached = False 
    
    if not OPENAI_API_KEY or not context:
        return {
            "answer": "OpenAI is not configured or no context found.",
            "sources": sources,
            "query": query,
            "cached": cached,
            "action_performed": action_performed
        }
    

    logger.info("Invoking RAG Agent...")

    # Prepare the initial state for the LangGraph agent
    initial_state: AgentState = {
        "user_query": query,
        "user_id": user_id,
        "source_filter": source_filter,
        "context": context, # Pass the retrieved chunks to the agent
        "answer": "",
        "tool_call": None,
        "action_performed": False,
        "email_present": email_present,
        "query_type": "RAG_ANSWER",
        "tool_calls": [],
        "intermediate_results": [],
        "execution_plan": [],
        "confidence": 0.0,
        "current_step": 0,
        "max_steps": 3
    }

    # logger.info("context passed to RAG Agent:", context)
    
    try:
        # Use ainvoke for async graph execution
        final_state = await RAG_AGENT_APP.ainvoke(initial_state)
        answer = final_state['answer']
        
        
    except Exception as e:
        answer = f"Error invoking RAG Agent: {str(e)}"
        action_performed = False

    return {
        "answer": answer,
        "sources": sources,
        "query": query,
        "cached": cached,
        "action_performed": action_performed 
    }