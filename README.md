# PaperMind AI — Research Paper Analyzer (SaaS Edition)

> **Transform any research PDF into actionable insights in minutes** — powered by Gemini 2.5 Flash, FAISS, and a real-time RAG pipeline.

---

## 🚀 Features

| Feature | Description |
|---|---|
| **Smart Summarization** | RAG-powered bullet summaries: problem → methods → findings → conclusion |
| **Expert Critique** | Balanced academic critique covering methodology, validity, clarity |
| **Future Directions** | 5 specific, actionable research directions derived from the paper |
| **Live Q&A Chat** | Ask anything about the paper — grounded answers, no hallucinations |
| **Metadata Extraction** | Auto-detects title, authors, year, DOI from the paper header |
| **Streaming Progress** | Real-time 5-step progress bar via Server-Sent Events |
| **Rich PDF Reports** | Export a professional PDF with metadata table, summary, citations |
| **Multi-Session Isolation** | UUID-based sessions — safe for multi-tab and multi-user use |

---

## 🏗️ Tech Stack

- **Backend**: Flask + Flask-Limiter + Flask-CORS
- **AI**: Google Gemini 2.5 Flash via `google-generativeai`
- **RAG**: FAISS + SentenceTransformers (`all-MiniLM-L6-v2`)
- **PDF**: PyMuPDF (text extraction) + ReportLab (report generation)
- **Frontend**: Vanilla HTML / CSS / JS — Space Grotesk + Inter fonts

---

## ⚡ Quick Start

### 1. Clone and set up environment
```bash
git clone https://github.com/veerakarthick235/Rag-Research-App
cd Rag-Research-App
python -m venv venv
venv\Scripts\activate   # Windows
# source venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
```

### 2. Configure API key
Create a `.env` file in the project root:
```env
GOOGLE_API_KEY=your_gemini_api_key_here
```
Get your key at: https://aistudio.google.com/app/apikey

### 3. Run the backend
```bash
cd backend
python app.py
```

### 4. Open in browser
Navigate to: **http://localhost:7860**

---

## 📁 Project Structure

```
Rag-Research-App/
├── backend/
│   ├── app.py            # Flask app — all API endpoints
│   ├── summarizer.py     # PaperSummarizer (streaming, Q&A, metadata)
│   ├── faiss_index.py    # FAISS vector store wrapper
│   ├── extractor.py      # PyMuPDF PDF text extractor
│   ├── session_store.py  # Thread-safe UUID session store
│   └── __init__.py
├── frontend/
│   ├── index.html        # Full SaaS landing page + app UI
│   ├── style.css         # Premium design system (dark, glassmorphism)
│   └── app.js            # SSE streaming, chat, counters, carousel
├── requirements.txt
└── .env                  # (create this — not committed)
```

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/session` | Create a new analysis session → `{session_id}` |
| `POST` | `/api/stream-upload` | Upload PDF → SSE stream of progress events |
| `POST` | `/api/chat` | Q&A chat → `{session_id, question}` → `{answer}` |
| `POST` | `/api/report` | Generate PDF report from result JSON |
| `GET`  | `/api/health` | Health check |
| `GET`  | `/api/usage` | Active session count |

---

## 🌐 Deployment Notes

- **Hugging Face Spaces**: Works as-is. Set `GOOGLE_API_KEY` as a Space secret.
- **Production**: Use `gunicorn` (already in requirements) with `--workers 2 --threads 4`.
- **Session persistence**: Currently in-memory (TTL 2h). For multi-process deployments, swap `session_store.py` to Redis.
