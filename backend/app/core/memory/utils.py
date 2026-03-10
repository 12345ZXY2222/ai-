import numpy as np
from app.core.adapter import zhipu_embedding

DEFAULT_WALLET_BALANCE = 100

def get_embedding(text):
    """
    Wrapper to get embedding using the adapter.
    """
    try:
        text = text.replace("\n", " ")
        if not text: 
            text = "this is blank"
        return zhipu_embedding(text)
    except Exception as e:
        print(f"Error getting embedding: {e}")
        # Return a zero vector of size 1536 (standard OpenAI size) as fallback
        return [0] * 1536

def cos_sim(a, b):
    """
    Calculates the cosine similarity between two vectors a and b.
    """
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
