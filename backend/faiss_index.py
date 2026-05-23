"""
faiss_index.py
--------------
Efficient FAISS-backed semantic search index using cosine similarity.

Key design decisions:
- Accepts an *externally provided* SentenceTransformer model instead of
  instantiating its own, eliminating the ~450 MB double-load issue.
- Uses L2-normalised vectors with IndexFlatIP (inner product ≡ cosine
  similarity after normalisation) for better semantic ranking than raw L2.
- Clamps k to the number of stored texts so FAISS never crashes with an
  out-of-bounds index request.
"""

import numpy as np
import faiss
from sentence_transformers import SentenceTransformer


class FaissIndex:
    """
    Lightweight FAISS wrapper for semantic retrieval.

    Parameters
    ----------
    model : SentenceTransformer
        A pre-loaded embedding model shared across the application to avoid
        redundant memory allocation.
    dim : int
        Embedding dimensionality. Must match the model's output size.
        Default 384 matches 'all-MiniLM-L6-v2'.
    """

    def __init__(self, model: SentenceTransformer, dim: int = 384):
        self.model = model
        self.dim = dim
        # IndexFlatIP with L2-normalised vectors ≡ cosine similarity search
        self.index = faiss.IndexFlatIP(dim)
        self.texts: list[str] = []

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def add_texts(self, texts: list[str]) -> None:
        """
        Embed and index a list of text chunks.

        Parameters
        ----------
        texts : list[str]
            Text chunks to embed and store.
        """
        if not texts:
            return

        embeddings = self.model.encode(
            texts,
            convert_to_numpy=True,
            show_progress_bar=False,
            batch_size=32,          # process in batches to control peak RAM
            normalize_embeddings=True,  # in-place L2 normalisation
        ).astype("float32")

        # Guard against single-text edge case where encode returns 1-D array
        if embeddings.ndim == 1:
            embeddings = embeddings.reshape(1, -1)

        self.index.add(embeddings)
        self.texts.extend(texts)

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def search(self, query: str, k: int = 5) -> list[str]:
        """
        Return the top-k most semantically similar texts to *query*.

        Parameters
        ----------
        query : str
            The search string.
        k : int
            Number of results to return. Automatically clamped to the number
            of stored texts so FAISS never raises an out-of-bounds error.

        Returns
        -------
        list[str]
            Matching text chunks in relevance order (most relevant first).
        """
        n_stored = len(self.texts)
        if n_stored == 0:
            return []

        # Clamp k so we never ask FAISS for more results than exist
        k_clamped = min(k, n_stored)

        q_emb = self.model.encode(
            [query],
            convert_to_numpy=True,
            normalize_embeddings=True,
        ).astype("float32")

        _scores, indices = self.index.search(q_emb, k_clamped)

        results: list[str] = []
        for idx in indices[0]:
            if 0 <= idx < n_stored:
                results.append(self.texts[idx])

        return results

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        """Return the number of indexed text chunks."""
        return len(self.texts)
