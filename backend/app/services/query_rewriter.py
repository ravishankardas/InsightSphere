# app/services/query_rewriter.py

# from openai import OpenAI
from langfuse.openai import openai # type: ignore

from typing import List, Optional
import os
from app.logger import setup_logger
from dotenv import load_dotenv
logger = setup_logger()

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

query_cache = {}

class QueryRewriter:
    """
    Service to rewrite and expand user queries for better retrieval.
    Uses LLM to reformulate vague or unclear queries.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        # self.client = openai(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        self.model = "gpt-3.5-turbo"  # Fast and cost-effective for query rewriting
    
    def rewrite_query(self, original_query: str, document_context: Optional[str] = None) -> str:
        """
        Rewrite a single query to be more specific and retrieval-friendly.
        
        Args:
            original_query: The user's original question
            document_context: Optional context about the document being queried
            
        Returns:
            Rewritten query string
        """

        if original_query in query_cache:
            logger.info("Using cached rewritten query.")
            return query_cache[original_query]
        
        system_prompt = """You are a query optimization expert. Your job is to rewrite user queries to be more specific, clear, and effective for document retrieval.

                Rules:
                1. Expand vague queries into specific questions
                2. Add relevant context and keywords
                3. Keep the core intent of the original query
                4. Make it a complete, well-formed question
                5. Don't change queries that are already clear and specific
                6. Output ONLY the rewritten query, nothing else"""

        user_prompt = f"Original query: {original_query}"
        
        if document_context:
            user_prompt += f"\n\nDocument context: {document_context}"
        
        user_prompt += "\n\nRewritten query:"
        
        try:
            response = openai.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,  # Low temperature for consistent rewrites
                max_tokens=150
            )
            
            rewritten = response.choices[0].message.content.strip() # type: ignore
            
            # Remove quotes if LLM added them
            if rewritten.startswith('"') and rewritten.endswith('"'):
                rewritten = rewritten[1:-1]

            query_cache[original_query] = rewritten

            return rewritten
            
        except Exception as e:
            logger.error(f"Query rewriting failed: {e}")
            # Fallback to original query if rewriting fails
            return original_query
    
    def generate_multi_queries(self, original_query: str, num_queries: int = 3) -> List[str]:
        """
        Generate multiple variations of the query for multi-query retrieval.
        
        Args:
            original_query: The user's original question
            num_queries: Number of query variations to generate
            
        Returns:
            List of query variations
        """
        
        system_prompt = f"""You are a query expansion expert. Generate {num_queries} different variations of the user's query that capture different aspects or phrasings of the same question.

            Rules:
            1. Each variation should ask the same thing in a different way
            2. Include different keywords and synonyms
            3. Vary the specificity (broad to specific)
            4. Keep the core intent identical
            5. Output one query per line, numbered"""

        user_prompt = f"Original query: {original_query}\n\nGenerate {num_queries} variations:"
        
        try:
            response = openai.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,  # Higher temperature for diversity
                max_tokens=300
            )
            
            content = response.choices[0].message.content.strip() # type: ignore
            
            # Parse the numbered list
            queries = []
            for line in content.split('\n'):
                line = line.strip()
                if line:
                    # Remove numbering (1., 2., etc.)
                    if line[0].isdigit() and '.' in line[:3]:
                        line = line.split('.', 1)[1].strip()
                    # Remove quotes
                    line = line.strip('"').strip("'")
                    if line:
                        queries.append(line)
            
            # Always include the original query as the first one
            return [original_query] + queries[:num_queries-1]
            
        except Exception as e:
            logger.error(f"Multi-query generation failed: {e}")
            # Fallback to just the original query
            return [original_query]
    
    def should_rewrite(self, query: str) -> bool:
        """
        Determine if a query needs rewriting based on heuristics.
        
        Args:
            query: The user's query
            
        Returns:
            True if query should be rewritten
        """
        query_lower = query.lower().strip()
        
        # Short queries often need expansion
        if len(query.split()) <= 3:
            return True
        
        # Vague phrases that need clarification
        vague_phrases = [
            "what's this", "tell me about", "explain this", 
            "summarize", "what does it say", "main points",
            "about what", "what is it"
        ]
        
        for phrase in vague_phrases:
            if phrase in query_lower:
                return True
        
        # Queries without question words might need reformulation
        question_words = ["what", "why", "how", "when", "where", "who", "which"]
        if not any(word in query_lower for word in question_words):
            return True
        
        return False


# Singleton instance
_query_rewriter = None

def get_query_rewriter() -> QueryRewriter:
    """Get or create the query rewriter singleton."""
    global _query_rewriter
    if _query_rewriter is None:
        _query_rewriter = QueryRewriter()
    return _query_rewriter