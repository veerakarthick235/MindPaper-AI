import os
import re
import google.generativeai as genai
from sentence_transformers import SentenceTransformer

# ✅ Compatibility for LangChain Splitter
try:
    from langchain.text_splitter import RecursiveCharacterTextSplitter
except ImportError:
    from langchain_text_splitters import RecursiveCharacterTextSplitter

from faiss_index import FaissIndex


class PaperSummarizer:
    """
    AI-powered research paper processor:
    ✅ RAG-based summarization
    ✅ Balanced academic critique
    ✅ Future research suggestions
    ✅ Citation / reference extraction
    """

    def __init__(self, gemini_api_key: str = None, model_name="models/gemini-2.5-flash"):
        if gemini_api_key:
            os.environ["GOOGLE_API_KEY"] = gemini_api_key

        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

        # ✅ Latest model request from user
        self.llm = genai.GenerativeModel(model_name)

        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1500,
            chunk_overlap=200
        )
        self.embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

        self._last_index = None  # Stored for future Q&A expansions

    def process_document(self, full_text: str, meta=None, rag_k: int = 5):
        """Main method — document → structured AI output"""

        # Chunking
        docs = self.text_splitter.split_text(full_text)

        # Build FAISS index and store for future use
        index = FaissIndex()
        index.add_texts(docs)
        self._last_index = index

        # Citation detection
        citations = self._extract_references(full_text)

        # ✅ RAG helper
        def rag_answer(instruction: str):
            retrieved = index.search(instruction, k=rag_k)
            context = "\n\n---\n\n".join(retrieved)

            prompt = f"""
You are an expert academic assistant.

Relevant retrieved context:
{context}

Instruction:
{instruction}

Provide clear, direct, and structured output.
            """
            return self._ask_gemini(prompt)

        # RAG-based Summaries
        summary = rag_answer(
            "Summarize the main problem, methods, key findings, and conclusion in 3-6 bullet points."
        )
        critique = rag_answer(
            "Give a constructive critique with strengths, weaknesses, validity concerns, and clarity issues."
        )
        future_directions = rag_answer(
            "Suggest 5 specific future research directions based on the study."
        )

        # Top representative excerpts
        top_excerpts = index.search("important parts of the paper", k=5)

        return {
            "meta": meta or {},
            "summary": summary,
            "critique": critique,
            "future_directions": future_directions,
            "excerpts": top_excerpts,
            "citations": citations,
        }

    def _ask_gemini(self, prompt: str) -> str:
        """Safe Gemini API wrapper"""
        try:
            response = self.llm.generate_content(prompt)
            return (response.text or "").strip()
        except Exception as e:
            return f"[Gemini API Error: {e}]"

    def _extract_references(self, text: str):
        """
        Simple heuristic citation extraction:
        Detects 'References'/'Bibliography' section,
        extracts numbered or author-style entries.
        """
        lower = text.lower()
        idx = -1

        # Locate reference section markers
        for marker in ["\nreferences", "\nbibliography", "\nworks cited"]:
            idx = lower.find(marker)
            if idx != -1:
                break
        if idx == -1:
            return []

        refs_text = text[idx:]
        refs_text = refs_text[:20000]  # Safety trim

        lines = [ln.strip() for ln in refs_text.splitlines() if ln.strip()]

        citations = []
        current = ""

        for ln in lines:
            # Detect citation line patterns
            if re.match(r"^(\d+[\.\)]|\[\d+\]|[A-Z][a-z]+ et al\.)", ln):
                if current:
                    citations.append(current.strip())
                current = ln
            else:
                current += " " + ln

        if current:
            citations.append(current.strip())

        return citations[:50]  # Safety limit
