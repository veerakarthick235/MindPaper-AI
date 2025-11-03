from sentence_transformers import SentenceTransformer
import faiss
import numpy as np

class FaissIndex:
    def __init__(self, model_name="all-MiniLM-L6-v2", dim=384):
        self.model = SentenceTransformer(model_name)
        self.dim = dim
        self.index = faiss.IndexFlatL2(dim)
        self.texts = []

    def add_texts(self, texts):
        embeddings = self.model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        if embeddings.ndim == 1:
            embeddings = embeddings.reshape(1, -1)
        self.index.add(embeddings.astype('float32'))
        self.texts.extend(texts)

    def search(self, query, k=5):
        q_emb = self.model.encode([query], convert_to_numpy=True).astype('float32')
        D, I = self.index.search(q_emb, k)
        results = []
        for idx in I[0]:
            if idx < len(self.texts):
                results.append(self.texts[idx])
        return results
