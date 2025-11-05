# app/services/citation_extractor.py

from typing import List, Dict, Tuple
import re
from difflib import SequenceMatcher

class CitationExtractor:
    """
    Service to extract and verify citations from LLM responses.
    Maps answer sentences back to source chunks for explainability.
    """
    
    def __init__(self, similarity_threshold: float = 0.6):
        """
        Args:
            similarity_threshold: Minimum similarity score to consider a citation valid (0-1)
        """
        self.similarity_threshold = similarity_threshold
    
    def extract_citations(
        self, 
        answer: str, 
        source_chunks: List[Dict]
    ) -> Dict:
        """
        Extract citations from answer and map them to source chunks.
        
        Args:
            answer: The LLM-generated answer
            source_chunks: List of retrieved chunks with 'content', 'metadata', etc.
            
        Returns:
            Dictionary with annotated answer and citation details
        """
        
        # Split answer into sentences
        answer_sentences = self._split_into_sentences(answer)
        
        # Find citations for each sentence
        citations = []
        annotated_sentences = []
        
        for idx, sentence in enumerate(answer_sentences):
            # Find best matching source chunk
            best_match = self._find_best_match(sentence, source_chunks)
            
            if best_match:
                citation_num = len(citations) + 1
                citations.append({
                    "citation_id": citation_num,
                    "sentence": sentence,
                    "source_chunk": best_match["chunk"],
                    "source_text": best_match["matched_text"],
                    "similarity": best_match["similarity"],
                    "metadata": best_match["metadata"]
                })
                
                # Annotate sentence with citation number
                annotated_sentences.append(f"{sentence} [{citation_num}]")
            else:
                # No strong citation found
                annotated_sentences.append(sentence)
        
        return {
            "original_answer": answer,
            "annotated_answer": " ".join(annotated_sentences),
            "citations": citations,
            "citation_count": len(citations),
            "coverage": len(citations) / len(answer_sentences) if answer_sentences else 0
        }
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences.
        
        Args:
            text: Input text
            
        Returns:
            List of sentences
        """
        # Simple sentence splitting (can be improved with spaCy/nltk)
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]
    
    def _find_best_match(
        self, 
        sentence: str, 
        source_chunks: List[Dict]
    ) -> Dict | None:
        """
        Find the best matching source chunk for a sentence.
        
        Args:
            sentence: A sentence from the answer
            source_chunks: List of source chunks
            
        Returns:
            Dictionary with match details or None
        """
        best_similarity = 0
        best_match = None
        
        for chunk in source_chunks:
            chunk_content = chunk.get("content", "")
            
            # Try to find matching substring in chunk
            similarity, matched_text = self._calculate_similarity(sentence, chunk_content)
            
            if similarity > best_similarity and similarity >= self.similarity_threshold:
                best_similarity = similarity
                best_match = {
                    "chunk": chunk,
                    "matched_text": matched_text,
                    "similarity": similarity,
                    "metadata": chunk.get("metadata", {})
                }
        
        return best_match
    
    def _calculate_similarity(self, sentence: str, chunk: str) -> Tuple[float, str]:
        """
        Calculate similarity between a sentence and a chunk.
        
        Args:
            sentence: Sentence from answer
            chunk: Source chunk text
            
        Returns:
            Tuple of (similarity_score, matched_text_from_chunk)
        """
        # Remove common words for better matching
        sentence_clean = self._clean_text(sentence)
        chunk_clean = self._clean_text(chunk)
        
        # Calculate overall similarity
        overall_similarity = SequenceMatcher(None, sentence_clean, chunk_clean).ratio()
        
        # Also try to find the most similar substring in the chunk
        best_substring = ""
        best_substring_similarity = 0
        
        # Split chunk into sentences
        chunk_sentences = self._split_into_sentences(chunk)
        
        for chunk_sentence in chunk_sentences:
            chunk_sentence_clean = self._clean_text(chunk_sentence)
            similarity = SequenceMatcher(None, sentence_clean, chunk_sentence_clean).ratio()
            
            if similarity > best_substring_similarity:
                best_substring_similarity = similarity
                best_substring = chunk_sentence
        
        # Use the better of overall or substring similarity
        final_similarity = max(overall_similarity, best_substring_similarity)
        matched_text = best_substring if best_substring else chunk[:200]
        
        return final_similarity, matched_text
    
    def _clean_text(self, text: str) -> str:
        """
        Clean text for similarity comparison.
        
        Args:
            text: Input text
            
        Returns:
            Cleaned text
        """
        # Convert to lowercase
        text = text.lower()
        
        # Remove punctuation
        text = re.sub(r'[^\w\s]', '', text)
        
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        return text
    
    def verify_citations(self, citations: List[Dict]) -> Dict:
        """
        Verify the quality of extracted citations.
        
        Args:
            citations: List of citation dictionaries
            
        Returns:
            Verification statistics
        """
        if not citations:
            return {
                "verified": False,
                "average_similarity": 0,
                "strong_citations": 0,
                "weak_citations": 0
            }
        
        similarities = [c["similarity"] for c in citations]
        avg_similarity = sum(similarities) / len(similarities)
        
        # Strong citations: similarity > 0.7
        strong = sum(1 for s in similarities if s > 0.7)
        # Weak citations: similarity between threshold and 0.7
        weak = len(similarities) - strong
        
        return {
            "verified": avg_similarity >= self.similarity_threshold,
            "average_similarity": round(avg_similarity, 3),
            "strong_citations": strong,
            "weak_citations": weak,
            "total_citations": len(citations)
        }
    
    def format_citations_for_display(self, citations: List[Dict]) -> List[Dict]:
        """
        Format citations for frontend display.
        
        Args:
            citations: List of citation dictionaries
            
        Returns:
            Formatted citations for UI
        """
        formatted = []
        
        for citation in citations:
            metadata = citation["metadata"]
            
            formatted.append({
                "id": citation["citation_id"],
                "sentence": citation["sentence"],
                "source": metadata.get("source", "Unknown"),
                "page": metadata.get("page", "N/A"),
                "similarity": f"{citation['similarity']*100:.1f}%",
                "excerpt": citation["source_text"][:150] + "..." if len(citation["source_text"]) > 150 else citation["source_text"]
            })
        
        return formatted


# Singleton instance
_citation_extractor = None

def get_citation_extractor() -> CitationExtractor:
    """Get or create the citation extractor singleton."""
    global _citation_extractor
    if _citation_extractor is None:
        _citation_extractor = CitationExtractor()
    return _citation_extractor