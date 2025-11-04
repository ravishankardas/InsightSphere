from sentence_transformers import SentenceTransformer
import numpy as np
import os

MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")
_model = None


def _get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def get_embeddings(texts):
    model = _get_model()
    embeddings = model.encode(texts,show_progress_bar=False, convert_to_numpy=True)
    return [emb.tolist() for emb in embeddings]