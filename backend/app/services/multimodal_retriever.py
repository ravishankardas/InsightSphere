# app/services/multimodal_retriever.py

import hashlib
import os
import re
import time
import uuid
from typing import Dict, List, Any
from openai import OpenAI
from app.services.embeddings import get_embeddings
from app.services.ingest import get_user_collection
from rank_bm25 import BM25Okapi 
from dotenv import load_dotenv
import redis # type: ignore
import json
import hashlib
from typing import Optional

import hashlib

import os
load_dotenv()
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
from sentence_transformers import SentenceTransformer
import redis # type: ignore
import numpy as np
import json
import hashlib
import time
from typing import Optional
from openai import OpenAI

class SemanticRAGCache:
    """Semantic cache for RAG queries with user isolation."""
    
    def __init__(
        self, 
        redis_url: str,
        similarity_threshold: float = 0.85,
        embedding_model: str = 'all-MiniLM-L6-v2'
    ):
        """
        Initialize semantic cache.
        
        Args:
            redis_url: Redis connection URL
            similarity_threshold: Minimum similarity for cache hit (0-1)
            embedding_model: Sentence transformer model for embeddings
        """
        self.redis = redis.from_url(redis_url, decode_responses=True)
        self.threshold = similarity_threshold
        self.encoder = SentenceTransformer(embedding_model)
        print(f"✅ Semantic cache initialized (threshold: {similarity_threshold})")
    
    def _create_cache_key(
        self, 
        user_id: str, 
        source_filter: Optional[str], 
        query: str
    ) -> str:
        """Create unique cache key."""
        user_hash = hashlib.md5(user_id.encode()).hexdigest()[:12]
        query_hash = hashlib.md5(query.encode()).hexdigest()[:8]
        
        if source_filter:
            return f"rag:semantic:{user_hash}:{source_filter}:{query_hash}"
        return f"rag:semantic:{user_hash}:all:{query_hash}"
    
    def _get_user_prefix(self, user_id: str, source_filter: Optional[str]) -> str:
        """Get Redis key prefix for scanning."""
        user_hash = hashlib.md5(user_id.encode()).hexdigest()[:12]
        if source_filter:
            return f"rag:semantic:{user_hash}:{source_filter}:*"
        return f"rag:semantic:{user_hash}:all:*"
    
    def search(
        self, 
        user_id: str, 
        source_filter: Optional[str], 
        query: str
    ) -> Optional[str]:
        """
        Search for semantically similar cached answer.
        
        Returns:
            Cached answer if found, None otherwise
        """
        try:
            # Encode query
            query_embedding = self.encoder.encode(query)
            
            # Get pattern for user's cache entries
            pattern = self._get_user_prefix(user_id, source_filter)
            
            best_match = None
            best_similarity = 0
            
            # Scan cached entries
            for key in self.redis.scan_iter(match=pattern, count=100):
                try:
                    cached_data = self.redis.get(key)
                    if not cached_data:
                        continue
                    
                    data = json.loads(cached_data)
                    cached_embedding = np.array(data["embedding"])
                    
                    # Calculate cosine similarity
                    similarity = self._cosine_similarity(query_embedding, cached_embedding)
                    
                    if similarity > best_similarity and similarity >= self.threshold:
                        best_similarity = similarity
                        best_match = data["answer"]
                
                except (json.JSONDecodeError, KeyError) as e:
                    # Skip corrupted cache entries
                    continue
            
            if best_match:
                print(f"✅ Semantic cache HIT (similarity: {best_similarity:.1%})")
                return best_match
            
            print(f"🔍 Semantic cache MISS (best similarity: {best_similarity:.1%})")
            return None
            
        except Exception as e:
            print(f"⚠️ Cache search error: {e}")
            return None
    
    def save(
        self,
        user_id: str,
        source_filter: Optional[str],
        query: str,
        answer: str,
        ttl: int = 604800  # 7 days
    ):
        """Save query-answer pair to cache."""
        try:
            # Encode query
            query_embedding = self.encoder.encode(query).tolist()
            
            # Create cache key
            cache_key = self._create_cache_key(user_id, source_filter, query)
            
            # Prepare cache data
            cache_data = {
                "query": query,
                "answer": answer,
                "embedding": query_embedding,
                "source": source_filter,
                "timestamp": time.time()
            }
            
            # Save to Redis with TTL
            self.redis.setex(
                cache_key,
                ttl,
                json.dumps(cache_data)
            )
            
            print(f"💾 Saved to semantic cache (TTL: {ttl//86400} days)")
            
        except Exception as e:
            print(f"⚠️ Cache save error: {e}")
    
    def _cosine_similarity(self, a, b) -> float:
        """Calculate cosine similarity between two vectors."""
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
    
    def clear_user_cache(self, user_id: str):
        """Clear all cache entries for a user."""
        user_hash = hashlib.md5(user_id.encode()).hexdigest()[:12]
        pattern = f"rag:semantic:{user_hash}:*"
        
        deleted = 0
        for key in self.redis.scan_iter(match=pattern):
            self.redis.delete(key)
            deleted += 1
        
        print(f"🗑️ Cleared {deleted} cache entries for user")
    
    def get_stats(self, user_id: str) -> dict:
        """Get cache statistics for a user."""
        user_hash = hashlib.md5(user_id.encode()).hexdigest()[:12]
        pattern = f"rag:semantic:{user_hash}:*"
        
        count = 0
        for _ in self.redis.scan_iter(match=pattern):
            count += 1
        
        return {
            "cached_queries": count,
            "user_hash": user_hash
        }


# Initialize cache (do this once, globally or in your startup)
redis_url=os.getenv("REDIS_URL")
# print("redis_url:", redis_url)
semantic_cache = SemanticRAGCache(
    redis_url=redis_url, # type: ignore
    similarity_threshold=0.85  # Adjust based on your needs
)

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

def call_openai(prompt: str, client: OpenAI):
    """Helper function to call OpenAI API."""
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=300
    )
    return response.choices[0].message.content # type: ignore

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
    # print(f"Searching collection with filter: {where_clause}")
    
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
        
        # print(f"  🧠 Reranking {len(to_rerank)} chunks...")
        
        # Get scores from the Cross-Encoder (higher score = better relevance)
        rerank_scores = RERANKER_MODEL.predict(sentence_pairs) # type: ignore

        # Apply new scores to the results
        for i, score in enumerate(rerank_scores):
            to_rerank[i]['rerank_score'] = score
        
        # Re-sort the reranked subset by the Cross-Encoder score
        to_rerank.sort(key=lambda x: x['rerank_score'], reverse=True)
        
        # Combine the re-ranked top N with the remaining results 
        final_chunks_all = to_rerank + remaining_results
        
        # print(f"  ✅ Reranking complete. New top item score: {to_rerank[0]['rerank_score']:.4f}")
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
    if not OPENAI_API_KEY or not context:
        return {
            "answer": "OpenAI is not configured or no context found.",
            "sources": sources,
            "query": query
        }

    # Build prompt once
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

    # Initialize client once
    client = OpenAI(api_key=OPENAI_API_KEY)

    # Try cache first, fallback to OpenAI
    answer = None

    if semantic_cache:
        try:
            # Check cache
            answer = semantic_cache.search(user_id, source_filter, prompt)
            
            if not answer:
                # Cache miss
                print("🆕 Cache miss - querying OpenAI")
                answer = call_openai(prompt, client)
                semantic_cache.save(user_id, source_filter, prompt, answer)  # type: ignore
            else:
                print("cache hit - using cached answer")
                
        except Exception as e:
            print(f"⚠️ Cache error: {e}")
            # Fallback to OpenAI
            try:
                answer = call_openai(prompt, client)
            except Exception as oe:
                answer = f"Error calling OpenAI API: {str(oe)}"

    else:
        # No cache - direct OpenAI call
        answer = call_openai(prompt, client)

    return {
        "answer": answer,
        "sources": sources,
        "query": query
    }