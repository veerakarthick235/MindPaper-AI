"""
summarizer.py
-------------
AI-powered research paper processor — production edition.

Features:
✅ Gemini 2.5 Flash (primary) with automatic 2.0 Flash fallback
✅ Shared SentenceTransformer embedding model (no double-load)
✅ RAG-based summarization, critique, future directions
✅ Metadata extraction (title, authors, year, DOI)
✅ Citation / reference detection
✅ Streaming SSE progress generator
✅ Interactive Q&A against the paper's FAISS index
✅ Retry logic with exponential backoff on Gemini API errors
✅ Robust JSON parsing for metadata (strips accidental markdown fences)
"""

import os
import re
import json
import time
import logging

from google import genai
from sentence_transformers import SentenceTransformer

# LangChain splitter — supports both old and new package layouts
try:
    from langchain.text_splitter import RecursiveCharacterTextSplitter
except ImportError:
    from langchain_text_splitters import RecursiveCharacterTextSplitter

from faiss_index import FaissIndex

logger = logging.getLogger(__name__)

# ── Model configuration ─────────────────────────────────────────────────────
MODELS_TO_TRY = [
    "gemini-3.5-flash",
    "gemini-3.1-pro-preview",
    "gemini-2.5-flash"
]

# Shared embedding model singleton — loaded once per process
_EMBEDDING_MODEL: SentenceTransformer | None = None


def get_embedding_model() -> SentenceTransformer:
    """
    Return the process-wide SentenceTransformer singleton.
    Lazy-loaded on first call; subsequent calls return the cached instance.
    """
    global _EMBEDDING_MODEL
    if _EMBEDDING_MODEL is None:
        logger.info("Loading SentenceTransformer model (all-MiniLM-L6-v2)…")
        _EMBEDDING_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
    return _EMBEDDING_MODEL


class PaperSummarizer:
    """
    Full RAG pipeline for academic paper analysis.

    Usage
    -----
    summarizer = PaperSummarizer(gemini_api_key="…")

    # Streaming (for SSE endpoints)
    for event_json in summarizer.process_document_streaming(text, meta=…):
        yield f"data: {event_json}\\n\\n"

    # Blocking (for report generation or testing)
    result = summarizer.process_document(text, meta=…)

    # Q&A
    answer = summarizer.answer_question(faiss_index, "What dataset was used?")
    """

    def __init__(
        self,
        gemini_api_key: str | None = None,
        model_name: str | None = None,
    ):
        if gemini_api_key:
            os.environ["GOOGLE_API_KEY"] = gemini_api_key

        self.client     = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
        self.model_name = model_name or MODELS_TO_TRY[0]
        self.active_model: str | None = None   # resolved after first API call

        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=3000,
            chunk_overlap=300,
            length_function=len,
        )

        # Shared embedding model — not owned by this class
        self._embed_model = get_embedding_model()

        # Populated by process_document_streaming() so the caller can store
        # the index in the session without passing it through the SSE stream
        self._last_index: FaissIndex | None = None

    # ── Streaming pipeline ────────────────────────────────────────────────

    def process_document_streaming(
        self,
        full_text: str,
        meta: dict | None = None,
        rag_k: int = 5,
    ):
        """
        Generator that yields SSE-formatted JSON progress events followed
        by a final 'done' event containing the complete result.

        Yield shapes
        ------------
        Progress: {"step": str, "pct": int, "done": False}
        Done:     {"step": str, "pct": 100, "done": True, "result": dict}
        Error:    {"error": str, "done": True}
        """

        def _emit(step: str, pct: int) -> str:
            return json.dumps({"step": step, "pct": pct, "done": False})

        yield _emit("Extracting text…", 5)

        # ── Step 1: Chunk ────────────────────────────────────────────────
        yield _emit("Chunking document…", 20)
        docs = self.text_splitter.split_text(full_text)
        if not docs:
            yield json.dumps({"error": "Document is empty after chunking.", "done": True})
            return

        # ── Step 2: Embed + Index ────────────────────────────────────────
        yield _emit("Building semantic index…", 40)
        index = FaissIndex(model=self._embed_model)
        index.add_texts(docs)

        # ── Step 3: Citations ────────────────────────────────────────────
        yield _emit("Detecting citations…", 55)
        citations = self._extract_references(full_text)

        # ── Step 4: Metadata ─────────────────────────────────────────────
        yield _emit("Extracting metadata…", 65)
        metadata = self.extract_metadata(full_text)

        # RAG helper — retrieves context then queries Gemini
        def rag_answer(instruction: str) -> str:
            retrieved = index.search(instruction, k=rag_k)
            context   = "\n\n---\n\n".join(retrieved)
            prompt = (
                "You are an expert academic research assistant.\n\n"
                f"Relevant retrieved context:\n{context}\n\n"
                f"Instruction:\n{instruction}\n\n"
                "Respond with clear, structured markdown (bullet points where appropriate). "
                "Be concise and accurate. Do not hallucinate — only use information from the context."
            )
            return self._ask_gemini(prompt)

        # ── Step 5: Summary ──────────────────────────────────────────────
        yield _emit("Generating summary…", 72)
        summary = rag_answer(
            "Summarize the main problem, methods, key findings, and conclusion "
            "in 4–6 clear bullet points."
        )

        # ── Step 6: Critique ─────────────────────────────────────────────
        yield _emit("Crafting critique…", 83)
        critique = rag_answer(
            "Provide a constructive academic critique covering: "
            "strengths, methodological weaknesses, statistical validity, "
            "clarity issues, and reproducibility concerns."
        )

        # ── Step 7: Future Directions ────────────────────────────────────
        yield _emit("Suggesting future directions…", 93)
        future_directions = rag_answer(
            "Suggest 5 specific, actionable future research directions based "
            "on the paper's identified gaps and conclusions."
        )

        # Key excerpts via semantic search
        top_excerpts = index.search("most important contribution or finding", k=5)

        result = {
            "meta":              {**(meta or {}), **metadata},
            "summary":           summary,
            "critique":          critique,
            "future_directions": future_directions,
            "excerpts":          top_excerpts,
            "citations":         citations,
            "model_used":        self.active_model or self.model_name,
        }

        # Store index on the instance BEFORE yielding the done event so
        # the caller can access _last_index immediately upon receiving it
        self._last_index = index

        yield json.dumps({
            "step":   "Analysis complete!",
            "pct":    100,
            "done":   True,
            "result": result,
        })

    # ── Blocking pipeline ─────────────────────────────────────────────────

    def process_document(
        self,
        full_text: str,
        meta: dict | None = None,
        rag_k: int = 5,
    ) -> dict:
        """
        Blocking version — drives the streaming generator internally.
        Useful for report generation and unit tests.
        """
        result = None
        for event_json in self.process_document_streaming(
            full_text, meta=meta, rag_k=rag_k
        ):
            data = json.loads(event_json)
            if data.get("done"):
                result = data.get("result")
        return result or {}

    # ── Q&A ───────────────────────────────────────────────────────────────

    def answer_question(
        self,
        index: FaissIndex,
        question: str,
        rag_k: int = 6,
    ) -> str:
        """
        Answer a user question grounded in the paper's FAISS index.

        Parameters
        ----------
        index : FaissIndex
            The index built during paper analysis for this session.
        question : str
            The user's natural-language question.
        rag_k : int
            Number of context chunks to retrieve.
        """
        retrieved = index.search(question, k=rag_k)
        if not retrieved:
            return (
                "I couldn't find relevant content in the paper to answer that question. "
                "Try rephrasing or asking about a different aspect."
            )

        context = "\n\n---\n\n".join(retrieved)
        prompt = (
            "You are a knowledgeable research assistant helping the user understand an academic paper.\n\n"
            f"Paper context (retrieved via semantic search):\n{context}\n\n"
            f"User question: {question}\n\n"
            "Answer directly and concisely, referencing the paper content. "
            "If the information is not in the retrieved context, say so clearly."
        )
        return self._ask_gemini(prompt)

    # ── Metadata extraction ───────────────────────────────────────────────

    def extract_metadata(self, text: str) -> dict:
        """
        Extract structured metadata from the paper header using heuristics
        and Gemini. All fields degrade gracefully if not found.
        """
        meta: dict = {
            "title":           None,
            "authors":         None,
            "year":            None,
            "doi":             None,
            "abstract_length": 0,
            "word_count":      len(text.split()),
        }

        # DOI: standard regex covering the vast majority of academic DOIs
        doi_match = re.search(
            r"\b(10\.\d{4,9}/[-._;()/:A-Z0-9]+)", text, re.IGNORECASE
        )
        if doi_match:
            meta["doi"] = doi_match.group(1).rstrip(".")

        # Year: first 4-digit year in the 1900–2099 range found in header
        year_match = re.search(r"\b(19|20)\d{2}\b", text[:3000])
        if year_match:
            meta["year"] = year_match.group(0)

        # Abstract length: word count between "Abstract" and "Introduction"
        lower = text.lower()
        abs_start   = lower.find("abstract")
        intro_start = lower.find("introduction")
        if abs_start != -1 and intro_start != -1 and intro_start > abs_start:
            meta["abstract_length"] = len(text[abs_start:intro_start].split())

        # Gemini: extract title and authors from the first 1500 characters
        first_chunk = text[:1500]
        try:
            prompt = (
                "Extract ONLY the paper title and author names from this text.\n"
                'Return a JSON object with keys "title" and "authors" '
                "(authors as a comma-separated string).\n"
                "If a field is not found, set its value to null.\n"
                "Return raw JSON only — no markdown fences, no extra text.\n\n"
                f"Text:\n{first_chunk}"
            )
            raw = self._ask_gemini(prompt)
            parsed = self._parse_json_response(raw)
            meta["title"]   = parsed.get("title")   or meta["title"]
            meta["authors"] = parsed.get("authors") or meta["authors"]
        except Exception as exc:
            logger.debug("Metadata extraction via Gemini failed: %s", exc)
            # Metadata is optional — never fail the pipeline over this

        return meta

    # ── Internal helpers ──────────────────────────────────────────────────

    def _ask_gemini(self, prompt: str, max_retries: int = 4) -> str:
        """
        Safe Gemini API wrapper with primary/fallback model and exponential
        backoff retry on transient errors (rate limits, 503s).

        Parameters
        ----------
        prompt : str
            The prompt to send to Gemini.
        max_retries : int
            Total attempts before raising. Default 4.
        """
        models_to_try = [self.model_name]
        for m in MODELS_TO_TRY:
            if m not in models_to_try:
                models_to_try.append(m)

        last_error: Exception | None = None

        for model_id in models_to_try:
            for attempt in range(max_retries):
                try:
                    response = self.client.models.generate_content(
                        model=model_id,
                        contents=prompt,
                    )
                    self.active_model = model_id   # track which model succeeded
                    return (response.text or "").strip()

                except Exception as exc:
                    last_error = exc
                    err_msg = str(exc).lower()

                    # 429 Too Many Requests specific handling
                    if "429" in err_msg or "quota_exceeded" in err_msg or "too many requests" in err_msg or "quota" in err_msg:
                        wait = 4 ** attempt  # 1s, 4s, 16s, 64s
                        logger.warning(
                            "Gemini API 429 Rate Limit (model=%s attempt=%d/%d). Retrying in %ds…",
                            model_id, attempt + 1, max_retries, wait,
                        )
                        time.sleep(wait)
                        continue

                    # Non-retryable errors: bad request, content policy, auth
                    if any(
                        kw in err_msg
                        for kw in ("invalid_argument", "permission_denied",
                                   "unauthenticated", "content_filter")
                    ):
                        break  # try fallback model immediately

                    # Other retryable errors: server error 500/503
                    wait = 2 ** attempt  # 1s, 2s, 4s
                    logger.warning(
                        "Gemini API error (model=%s attempt=%d/%d): %s — retrying in %ds",
                        model_id, attempt + 1, max_retries, exc, wait,
                    )
                    time.sleep(wait)

        # All models and retries exhausted
        logger.error("All Gemini models failed. Last error: %s", last_error)
        return f"[AI Error: {last_error}]"

    @staticmethod
    def _parse_json_response(raw: str) -> dict:
        """
        Parse a Gemini JSON response, stripping accidental markdown fences.
        Returns an empty dict on any parse failure.
        """
        # Remove ```json ... ``` or ``` ... ``` wrappers
        clean = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()
        try:
            return json.loads(clean)
        except json.JSONDecodeError:
            return {}

    def _extract_references(self, text: str) -> list[str]:
        """
        Heuristic citation extraction from the References / Bibliography section.
        Handles numbered ([1], 1., 1)) and author-year (Smith et al.) formats.
        Returns up to 50 citations.
        """
        lower = text.lower()
        section_start = -1

        for marker in ["\nreferences", "\nbibliography", "\nworks cited"]:
            idx = lower.find(marker)
            if idx != -1:
                section_start = idx
                break

        if section_start == -1:
            return []

        refs_text = text[section_start:][:20_000]  # safety trim
        lines = [ln.strip() for ln in refs_text.splitlines() if ln.strip()]

        citations: list[str] = []
        current = ""

        for ln in lines:
            # New citation entry: starts with a number marker or author pattern
            if re.match(
                r"^(\d{1,3}[.)]\s|^\[\d{1,3}\]\s|[A-Z][a-záéíóú]+,?\s+[A-Z]\.)", ln
            ):
                if current:
                    citations.append(current.strip())
                current = ln
            else:
                current += " " + ln

        if current:
            citations.append(current.strip())

        # Filter out very short lines that are probably section headings
        citations = [c for c in citations if len(c) > 20]

        return citations[:50]
