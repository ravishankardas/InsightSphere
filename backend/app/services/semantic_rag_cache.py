import json
import time
from typing import Optional
from sentence_transformers import SentenceTransformer
import redis # type: ignore
import hashlib
import os 
import numpy as np
from app.logger import setup_logger

logger = setup_logger()

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
        """
        self.redis = redis.from_url(redis_url, decode_responses=True)
        self.threshold = similarity_threshold
        self.encoder = SentenceTransformer(embedding_model)
        # logger.info(f"✅ Semantic cache initialized (threshold: {similarity_threshold})")
    
    def _create_cache_key(
        self, 
        user_id: str, 
        source_filter: str, 
        query: str
    ) -> str:
        """Create unique cache key."""
        user_hash = hashlib.md5(user_id.encode()).hexdigest()[:12]
        # Use query hash for cache key now that the full prompt is generated in the agent
        query_hash = hashlib.md5(query.encode()).hexdigest()[:8] 
        
        if source_filter:
            return f"rag:semantic:{user_hash}:{source_filter}:{query_hash}"
        return f"rag:semantic:{user_hash}:all:{query_hash}"
    
    def _get_user_prefix(self, user_id: str, source_filter: str) -> str:
        """Get Redis key prefix for scanning."""
        user_hash = hashlib.md5(user_id.encode()).hexdigest()[:12]
        if source_filter:
            return f"rag:semantic:{user_hash}:{source_filter}:*"
        return f"rag:semantic:{user_hash}:all:*"
    
    def search(
        self, 
        user_id: str, 
        source_filter: str, 
        query: str
    ) -> Optional[str]:
        """
        Search for semantically similar cached answer.
        """
        try:
            # logger.info(f"source_filter in cache search: {source_filter}")
            query_embedding = self.encoder.encode(query)
            pattern = self._get_user_prefix(user_id, source_filter)
            
            best_match = None
            best_similarity = 0
            
            for key in self.redis.scan_iter(match=pattern, count=100):
                try:
                    cached_data = self.redis.get(key)
                    if not cached_data:
                        continue
                    
                    data = json.loads(cached_data)
                    cached_embedding = np.array(data["embedding"])
                    
                    similarity = self._cosine_similarity(query_embedding, cached_embedding)
                    
                    if similarity > best_similarity and similarity >= self.threshold:
                        best_similarity = similarity
                        best_match = data["answer"]
                
                except (json.JSONDecodeError, KeyError):
                    continue
            
            if best_match:
                logger.info(f"✅ Semantic cache HIT (similarity: {best_similarity:.1%})")
                return best_match
            
            logger.info(f"🔍 Semantic cache MISS (best similarity: {best_similarity:.1%})")
            return None
            
        except Exception as e:
            logger.error(f"⚠️ Cache search error: {e}")
            return None
    
    def save(
        self,
        user_id: str,
        source_filter: str,
        query: str,
        answer: str,
        ttl: int = 604800  # 7 days
    ):
        """Save query-answer pair to cache."""
        try:
            query_embedding = self.encoder.encode(query).tolist()
            cache_key = self._create_cache_key(user_id, source_filter, query)
            cache_data = {
                "query": query,
                "answer": answer,
                "embedding": query_embedding,
                "source": source_filter,
                "timestamp": time.time()
            }
            self.redis.setex(
                cache_key,
                ttl,
                json.dumps(cache_data)
            )
            # logger.info(f"💾 Saved to semantic cache (TTL: {ttl//86400} days), cache_key: {cache_key}")
            
        except Exception as e:
            logger.error(f"⚠️ Cache save error: {e}")
    
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
        
        logger.info(f"🗑️ Cleared {deleted} cache entries for user")
    
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
semantic_cache = SemanticRAGCache(
    redis_url=redis_url, # type: ignore
    similarity_threshold=0.85 
)