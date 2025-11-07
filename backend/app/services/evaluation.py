# app/services/evaluation.py

import os
import pandas as pd
import numpy as np
import math
from typing import Dict, Any, List
from datasets import Dataset
from ragas import evaluate # type: ignore
from ragas.metrics import ( # type: ignore
    faithfulness,
    answer_relevancy,
    context_recall,
    context_precision
)
from langchain_openai import ChatOpenAI # type: ignore
from langchain_core.embeddings import Embeddings # type: ignore
from ragas.llms import LangchainLLMWrapper # type: ignore
from ragas.embeddings import LangchainEmbeddingsWrapper # type: ignore
from app.services.multimodal_retriever import query_multimodal 
from app.services.embeddings import _get_model, MODEL_NAME  # Import your SentenceTransformer model
from dotenv import load_dotenv
load_dotenv()


from app.logger import setup_logger
logger = setup_logger()

OPEN_API_KEY = os.getenv("OPENAI_API_KEY")
# Define the path to your evaluation data file
EVALUATION_CSV_PATH = r"C:\Users\ravis\OneDrive\Desktop\PROJECTS\InsightSphere\backend\app\services\evaluation.csv"


class SentenceTransformerEmbeddings(Embeddings):
    """
    Wrapper to make SentenceTransformer compatible with Langchain/RAGAS.
    This ensures the same embedding model is used for both ingestion and evaluation.
    """
    def __init__(self, model, model_name: str):
        self._model_instance = model  # Store the actual model with a different name
        self._model_name = model_name  # Store model name as string
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of documents."""
        embeddings = self._model_instance.encode(texts, show_progress_bar=False, convert_to_numpy=True)
        return [emb.tolist() for emb in embeddings]
    
    def embed_query(self, text: str) -> List[float]:
        """Embed a single query."""
        embedding = self._model_instance.encode([text], show_progress_bar=False, convert_to_numpy=True)
        return embedding[0].tolist()
    
    def __str__(self):
        """Return model name for logging."""
        return self._model_name


def load_evaluation_dataset() -> pd.DataFrame:
    """Loads the question/ground_truth data from the CSV file."""
    if not os.path.exists(EVALUATION_CSV_PATH):
        raise FileNotFoundError(
            f"Evaluation file not found at: {EVALUATION_CSV_PATH}. "
            "Please create it or adjust the EVALUATION_CSV_PATH variable."
        )
    return pd.read_csv(EVALUATION_CSV_PATH)


def get_ragas_llm_and_embeddings():
    """
    Returns the LLM and embeddings for RAGAS evaluation.
    Uses the SAME SentenceTransformer model as ingestion for consistency.
    """
    
    # CRITICAL: Use the same embedding model as ingestion
    try:
        sentence_transformer_model = _get_model()  # Your ingestion model
        # Pass model name as string to avoid Pydantic validation errors
        langchain_compatible_embeddings = SentenceTransformerEmbeddings(
            sentence_transformer_model, 
            MODEL_NAME
        )
        embeddings = LangchainEmbeddingsWrapper(langchain_compatible_embeddings)
        logger.info(f"✅ Using ingestion embedding model: {MODEL_NAME}")
    except Exception as e:
        logger.error(f"⚠️ Warning: Could not load ingestion embedding model: {e}")
        return None, None
    
    if OPEN_API_KEY:
        evaluator_llm = LangchainLLMWrapper(
            ChatOpenAI(model="gpt-4o-mini", api_key=OPEN_API_KEY, temperature=0) # type: ignore
        )
        logger.info("✅ Using OpenAI for RAGAs evaluation")
        return evaluator_llm, embeddings
    
    else:
        return None, None


def sanitize_float(value):
    """Convert NaN and Inf values to None for JSON serialization."""
    if isinstance(value, (float, np.floating)):
        if math.isnan(value) or math.isinf(value):
            return None
    return value


def sanitize_dict(data):
    """Recursively sanitize all float values in a dictionary or list."""
    if isinstance(data, dict):
        return {k: sanitize_dict(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_dict(item) for item in data]
    else:
        return sanitize_float(data)


def evaluate_rag_pipeline(user_id: str, file_name: str = "") -> Dict[str, Any]:
    """
    Runs the RAG pipeline on a test set and evaluates it using RAGAs metrics.
    Uses the same embedding model as ingestion for accurate evaluation.
    
    Args:
        user_id: User identifier
        file_name: Optional file filter for evaluation
    """
    # Check for required API keys and load models
    evaluator_llm, embeddings = get_ragas_llm_and_embeddings()
    
    if evaluator_llm is None or embeddings is None:
        return {
            "error": "Cannot run evaluation. Requirements:\n"
                    "1. ANTHROPIC_API_KEY or OPENAI_API_KEY must be set\n"
                    "2. Ingestion embedding model must be accessible via _get_model()"
        }

    try:
        test_df = load_evaluation_dataset()
    except FileNotFoundError as e:
        return {"error": str(e)}

    # 1. Initialize RAGAs-compatible dictionary
    dataset_dict = {
        'question': test_df['question'].tolist(),
        'ground_truth': test_df['ground_truth'].tolist(),
        # Initialize contexts and answers as empty placeholders
        'contexts': [[] for _ in test_df.index],
        'answer': [""] * len(test_df.index)
    }
    
    # 2. Run the RAG pipeline on the test questions
    logger.info(f"\n🔬 Running RAG pipeline on {len(test_df)} test questions for evaluation...")
    for i, question in enumerate(dataset_dict['question']):
        try:
            # Use your improved hybrid+reranker query function
            rag_result = query_multimodal(
                query=question, 
                user_id=user_id, 
                top_k=4, 
                source_filter=file_name
            )
            
            # Extract the required components for RAGAs
            # Contexts must be a list of strings (the chunks)
            retrieved_contexts = [src['content'] for src in rag_result.get('sources', [])]  # type: ignore
            
            dataset_dict['answer'][i] = rag_result['answer'] # type: ignore
            dataset_dict['contexts'][i] = retrieved_contexts
            
            logger.info(f"  ✓ Question {i+1}/{len(test_df)} processed")
        except Exception as e:
            logger.error(f"  ✗ Question {i+1}/{len(test_df)} failed: {e}")
            dataset_dict['answer'][i] = f"Error: {str(e)}"
            dataset_dict['contexts'][i] = []
        
    # Create the final RAGAs dataset object
    ragas_dataset = Dataset.from_dict(dataset_dict)

    # 3. Define and run RAGAs metrics with custom LLM and matching embeddings
    logger.info("\n✨ Running RAGAs metrics (this may take a minute as an LLM is used)...")
    logger.info(f"   📊 Embedding Model: Same as ingestion (SentenceTransformer)")
    llm_name = "OpenAI GPT-4o-mini" if OPEN_API_KEY else "Unknown LLM"
    logger.info(f"   🤖 Evaluation LLM: {llm_name}")
    
    # Configure metrics with custom LLM and embeddings
    for metric in [faithfulness, answer_relevancy, context_recall, context_precision]:
        metric.llm = evaluator_llm
        metric.embeddings = embeddings
    
    try:
        result = evaluate(
            dataset=ragas_dataset,
            metrics=[
                faithfulness,
                answer_relevancy,
                context_recall,
                context_precision
            ],
        )
    except Exception as e:
        return {
            "error": f"RAGAs evaluation failed: {str(e)}",
            "timestamp": pd.Timestamp.now().isoformat()
        }

    # 4. Return results - Handle both dict and list formats
    result_df = result.to_pandas()
    
    # Debug: Print available columns
    logger.info(f"\n📋 Available columns in result: {list(result_df.columns)}")
    
    # Extract average scores from the result DataFrame
    average_scores = {}
    for col in ['faithfulness', 'answer_relevancy', 'context_recall', 'context_precision']:
        if col in result_df.columns:
            # Filter out NaN values before calculating mean
            valid_scores = result_df[col].dropna()
            if len(valid_scores) > 0:
                mean_value = float(valid_scores.mean())
                # Replace NaN/Inf with None for JSON serialization
                average_scores[col] = None if (math.isnan(mean_value) or math.isinf(mean_value)) else mean_value
            else:
                average_scores[col] = None
    
    # Prepare detail scores preview - only include columns that actually exist
    preview_columns = []
    
    # Check which base columns are available
    for col in ['user_input', 'question', 'ground_truth', 'answer', 'response', 'retrieved_contexts', 'reference']:
        if col in result_df.columns:
            preview_columns.append(col)
    
    # Add available metric columns
    for col in ['faithfulness', 'answer_relevancy', 'context_recall', 'context_precision']:
        if col in result_df.columns:
            preview_columns.append(col)
    
    # If no columns match, just use all available columns
    if not preview_columns:
        preview_columns = list(result_df.columns)
    
    # Convert DataFrame to dict and sanitize for JSON
    preview_data = result_df[preview_columns].head(10).to_dict('records')
    sanitized_preview = sanitize_dict(preview_data)
    
    return {
        "status": "Evaluation Complete",
        "timestamp": pd.Timestamp.now().isoformat(),
        "total_questions": len(test_df),
        "embedding_model": f"SentenceTransformer: {MODEL_NAME}",
        "average_scores": average_scores,
        "detail_scores_preview": sanitized_preview,
        "available_columns": list(result_df.columns)  # For debugging
    }