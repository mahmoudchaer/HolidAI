"""Embeddings using sentence-transformers."""
from sentence_transformers import SentenceTransformer
import os

# Load model once (singleton pattern)
_model = None


def get_model():
    """Get or load the sentence transformer model."""
    global _model
    if _model is None:
        _model = SentenceTransformer('all-MiniLM-L6-v2')
    return _model


def embed(text: str) -> list:
    """
    Generate embedding for text.
    
    Args:
        text: Input text to embed
        
    Returns:
        768-dim embedding as list of floats
    """
    model = get_model()
    embedding = model.encode(text, convert_to_numpy=True)
    return embedding.tolist()

