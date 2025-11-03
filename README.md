# AI Research Paper Summarizer & Reviewer

**Concept:** Upload a PDF research paper → AI summarizes, critiques, and suggests future directions.

**Tech stack**
- Backend: Flask + LangChain + OpenAI (or other LLMs supported by LangChain)
- PDF extraction: PyMuPDF (fitz)
- Semantic search: FAISS (via LangChain or direct)
- Embeddings: OpenAIEmbeddings (or SentenceTransformers as fallback)
- Frontend: simple HTML / CSS / JS

## Features
1. Upload PDF
2. Extract text and split into chunks
3. Create embeddings and store in FAISS
4. Query / semantic search + generate:
   - Concise summary
   - Detailed critique
   - Suggested future directions
   - Key citations / extracted metadata
5. Simple UI to upload and view results.

## Quick start (development)
1. Clone / unzip this project.
2. Create and activate a Python virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate   # macOS / Linux
   venv\Scripts\activate    # Windows
   ```
3. Install requirements:
   ```bash
   pip install -r requirements.txt
   ```
4. Create `.env` from `.env.example` and set your `OPENAI_API_KEY` (or configure an alternative LLM).
5. Run the backend:
   ```bash
   cd backend
   python app.py
   ```
6. Open `frontend/index.html` in a browser (or host it using a simple static server).

## Notes & choices
- The provided implementation uses LangChain + OpenAI by default to keep the "core AI" modular and replaceable.
- If you cannot use OpenAI, replace `OpenAI` LLM + embeddings calls in `backend/summarizer.py` with another provider (e.g., local Hugging Face models + SentenceTransformers embeddings).
- The code aims to be a working skeleton you can extend (better chunking, metadata extraction, citation parsing, UI improvements, auth).

## Files
- `backend/` : Flask API and modules
- `frontend/` : Static web UI
- `requirements.txt` : Python deps
- `.env.example`: Environment variables example

## License
MIT
