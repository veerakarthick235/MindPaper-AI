"""
app.py
------
PaperMind AI — production Flask application.

Architecture
------------
- /api/session        POST  — create a new analysis session
- /api/stream-upload  POST  — upload PDF + stream SSE analysis progress
- /api/chat           POST  — Q&A against the paper's FAISS index
- /api/report         POST  — generate and download a PDF summary report
- /api/usage          GET   — server stats (active sessions, version)
- /api/health         GET   — health check with active model info
- /favicon.ico        GET   — browser tab icon
- /.well-known/…      GET   — silence Chrome DevTools discovery probe
- /                   GET   — serve frontend SPA

Security measures
-----------------
- Filename sanitisation via werkzeug.utils.secure_filename (path traversal)
- Uploaded files deleted from disk immediately after text extraction
- Chat question capped at 1000 characters
- JSON Content-Type enforced on /api/chat
- Rate limits: 10 uploads / hour, 60 chats / hour per IP
"""

import io
import json
import logging
from logging.handlers import RotatingFileHandler
import os
import time

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request, send_file, send_from_directory, stream_with_context
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from werkzeug.utils import secure_filename

from extractor import extract_text_from_pdf
from session_store import store as session_store
from summarizer import PaperSummarizer

# ── Logging ───────────────────────────────────────────────────────────────
log_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log_handler = RotatingFileHandler("app.log", maxBytes=5 * 1024 * 1024, backupCount=2)
log_handler.setFormatter(log_formatter)
logging.basicConfig(level=logging.INFO, handlers=[log_handler, logging.StreamHandler()])
logger = logging.getLogger(__name__)

# ── Environment ───────────────────────────────────────────────────────────
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

if not GOOGLE_API_KEY:
    raise EnvironmentError(
        "❌ Neither GOOGLE_API_KEY nor GEMINI_API_KEY found in environment. "
        "Add one to your .env file before starting."
    )

# ── Flask app ─────────────────────────────────────────────────────────────
app = Flask(__name__, static_folder="../frontend", static_url_path="/")
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10 MB limit
CORS(app, origins=["*", "null"], supports_credentials=False)

# Rate limiting (in-memory; swap storage_uri for Redis in production)
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per hour"],
    storage_uri="memory://",
)

# Upload directory
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Shared AI pipeline — initialised once per process (loads embedding model)
summarizer = PaperSummarizer(gemini_api_key=GOOGLE_API_KEY)
logger.info("PaperSummarizer initialised (model=%s)", summarizer.model_name)


# ── Static routes ─────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(app.static_folder, "favicon.ico", mimetype="image/x-icon")


@app.route("/.well-known/appspecific/com.chrome.devtools.json")
def devtools_probe():
    """Silence Edge / Chrome DevTools discovery probe — not an error."""
    return jsonify({}), 200


# ── Session management ────────────────────────────────────────────────────

@app.route("/api/session", methods=["POST"])
def create_session():
    """Create a new analysis session and return its UUID."""
    sid = session_store.create_session()
    return jsonify({"session_id": sid})


# ── Streaming upload + analysis ───────────────────────────────────────────

@app.route("/api/stream-upload", methods=["POST"])
@limiter.limit("10 per hour")
def stream_upload():
    """
    Accept a PDF upload and stream SSE progress events back to the client.
    The final event contains the full analysis result JSON.

    Security notes:
    - Filename is sanitised with secure_filename() to prevent path traversal.
    - The uploaded file is deleted from disk after text extraction.
    """
    if "file" not in request.files:
        return jsonify({"error": "No file attached to the request."}), 400

    file       = request.files["file"]
    session_id = request.form.get("session_id", "").strip()

    # Validate file extension
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Please upload a valid PDF file."}), 400

    # Verify magic bytes for PDF (%PDF-)
    header = file.read(5)
    if header != b"%PDF-":
        return jsonify({"error": "Invalid file format. Please upload a real PDF."}), 400
    file.seek(0) # reset pointer

    # Sanitise filename — prevents directory traversal attacks
    safe_name = secure_filename(file.filename) or "upload.pdf"
    saved_path = os.path.join(UPLOAD_DIR, safe_name)
    file.save(saved_path)

    # Extract text then immediately delete the file from disk
    try:
        text = extract_text_from_pdf(saved_path)
    except (ValueError, RuntimeError) as exc:
        _safe_remove(saved_path)
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        _safe_remove(saved_path)
        logger.exception("Unexpected extraction error")
        return jsonify({"error": "Failed to process the PDF. Please try again."}), 500
    finally:
        _safe_remove(saved_path)  # always clean up

    if len(text.strip()) < 100:
        return jsonify({"error": "Could not extract enough text from this PDF."}), 400

    # Estimate page count from text length (≈3000 chars per page)
    page_count = max(1, len(text) // 3000)

    def generate():
        try:
            for event_json in summarizer.process_document_streaming(
                text, meta={"filename": safe_name, "page_count": page_count}
            ):
                data = json.loads(event_json)

                # On completion, persist session state + refresh TTL
                if data.get("done") and session_id:
                    if "result" in data:
                        result = data["result"]
                        session_store.update(
                            session_id,
                            faiss_index=summarizer._last_index,
                            result=result,
                            metadata=result.get("meta", {}),
                            filename=safe_name,
                            page_count=page_count,
                        )
                else:
                    # Refresh TTL on every progress event for long analyses
                    if session_id:
                        session_store.touch(session_id)

                yield f"data: {event_json}\n\n"
                time.sleep(0.04)

        except Exception as exc:
            logger.exception("Error during streaming analysis")
            error_event = json.dumps({"error": str(exc), "done": True})
            yield f"data: {error_event}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":        "keep-alive",
        },
    )


# ── Q&A chat ──────────────────────────────────────────────────────────────

@app.route("/api/chat", methods=["POST"])
@limiter.limit("60 per hour")
def chat():
    """
    Accept {session_id, question} and return an AI answer grounded in the
    session's FAISS index.
    """
    if not request.is_json:
        return jsonify({"error": "Request must be JSON."}), 415

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid or empty JSON body."}), 400

    session_id = data.get("session_id", "").strip()
    question   = (data.get("question") or "").strip()

    if not question:
        return jsonify({"error": "Question cannot be empty."}), 400
    if len(question) > 1000:
        return jsonify({"error": "Question must be 1000 characters or fewer."}), 400

    session = session_store.get(session_id)
    if not session:
        return jsonify({
            "error": "Session not found or expired. Please re-upload your paper."
        }), 404

    faiss_index = session.get("faiss_index")
    if not faiss_index:
        return jsonify({
            "error": "Paper has not been processed yet for this session."
        }), 400

    # Refresh TTL on chat activity
    session_store.touch(session_id)

    answer = summarizer.answer_question(faiss_index, question)
    return jsonify({"answer": answer})


# ── PDF report generation ─────────────────────────────────────────────────

@app.route("/api/report", methods=["POST"])
def generate_report():
    """Generate and stream a rich PDF report from the AI analysis output."""
    if not request.is_json:
        return jsonify({"error": "Request must be JSON."}), 415

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "No data provided."}), 400

    try:
        summary  = data.get("summary", "")
        critique = data.get("critique", "")
        future   = data.get("future_directions", "")
        excerpts = data.get("excerpts", [])
        citations= data.get("citations", [])
        meta     = data.get("meta", {})

        filename = meta.get("filename", "Unknown")
        title    = meta.get("title") or filename
        authors  = meta.get("authors", "")
        year     = meta.get("year", "")
        doi      = meta.get("doi", "")

        # ── Build PDF ────────────────────────────────────────────────────
        pdf_buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            pdf_buffer,
            pagesize=A4,
            leftMargin=2.5 * cm,
            rightMargin=2.5 * cm,
            topMargin=2.5 * cm,
            bottomMargin=2.5 * cm,
        )

        styles = getSampleStyleSheet()
        accent = colors.HexColor("#7C3AED")  # purple-600
        muted  = colors.HexColor("#6B7280")

        title_style = ParagraphStyle(
            "ReportTitle",
            parent=styles["Title"],
            fontSize=22,
            textColor=accent,
            spaceAfter=6,
            alignment=TA_CENTER,
        )
        subtitle_style = ParagraphStyle(
            "Subtitle",
            parent=styles["Normal"],
            fontSize=11,
            textColor=muted,
            alignment=TA_CENTER,
            spaceAfter=4,
        )
        section_style = ParagraphStyle(
            "Section",
            parent=styles["Heading2"],
            fontSize=14,
            textColor=accent,
            spaceBefore=14,
            spaceAfter=6,
        )
        body_style = ParagraphStyle(
            "Body",
            parent=styles["Normal"],
            fontSize=10,
            leading=15,
            spaceAfter=4,
        )
        caption_style = ParagraphStyle(
            "Caption",
            parent=styles["Normal"],
            fontSize=9,
            textColor=muted,
            spaceAfter=2,
            alignment=TA_CENTER,
        )

        story = []

        # Cover block
        story.append(Paragraph("PaperMind AI — Research Analysis", title_style))
        story.append(Paragraph("Powered by Gemini 3.5 Flash / 3.1 Pro + RAG + FAISS", subtitle_style))
        story.append(HRFlowable(width="100%", thickness=2, color=accent, spaceAfter=12))

        # Metadata table
        meta_rows = [
            ["📄 File",    filename],
            ["📰 Title",   title or "—"],
            ["👥 Authors", authors or "—"],
            ["📅 Year",    year or "—"],
            ["🔗 DOI",     doi or "—"],
        ]
        tbl = Table(meta_rows, colWidths=[3.5 * cm, 12 * cm])
        tbl.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (0, -1), colors.HexColor("#F5F3FF")),
            ("TEXTCOLOR",    (0, 0), (0, -1), accent),
            ("FONTNAME",     (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE",     (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#FAFAFA")]),
            ("BOX",          (0, 0), (-1, -1), 0.5, colors.HexColor("#DDDDDD")),
            ("INNERGRID",    (0, 0), (-1, -1), 0.25, colors.HexColor("#EEEEEE")),
            ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",   (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 16))

        def add_section(heading: str, content: str):
            story.append(Paragraph(heading, section_style))
            story.append(HRFlowable(
                width="100%", thickness=0.5,
                color=colors.HexColor("#E0E0E0"), spaceAfter=6,
            ))
            for line in content.split("\n"):
                if line.strip():
                    safe_line = line.strip().replace("•", "&#8226;")
                    # Escape XML-unsafe characters for ReportLab
                    safe_line = safe_line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    story.append(Paragraph(safe_line, body_style))
            story.append(Spacer(1, 8))

        add_section("📝 Summary",           summary)
        add_section("🔬 Critique",          critique)
        add_section("🔭 Future Directions", future)

        if excerpts:
            story.append(Paragraph("📌 Key Excerpts", section_style))
            story.append(HRFlowable(
                width="100%", thickness=0.5,
                color=colors.HexColor("#E0E0E0"), spaceAfter=6,
            ))
            for i, ex in enumerate(excerpts, 1):
                story.append(Paragraph(f"<b>Excerpt {i}:</b>", body_style))
                safe_ex = str(ex)[:600].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                story.append(Paragraph(safe_ex, body_style))
                story.append(Spacer(1, 4))

        if citations:
            story.append(Paragraph("📚 References", section_style))
            story.append(HRFlowable(
                width="100%", thickness=0.5,
                color=colors.HexColor("#E0E0E0"), spaceAfter=6,
            ))
            for c in citations[:25]:
                safe_c = str(c)[:200].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                story.append(Paragraph(f"• {safe_c}", body_style))

        story.append(Spacer(1, 20))
        story.append(HRFlowable(width="100%", thickness=0.5, color=accent, spaceAfter=6))
        story.append(Paragraph(
            "Generated by PaperMind AI — Gemini 3.5 Flash / 3.1 Pro + RAG",
            caption_style,
        ))

        doc.build(story)
        pdf_buffer.seek(0)

        download_name = (safe_name.replace(".pdf", "") if (safe_name := secure_filename(filename)) else "paper") + "_analysis.pdf"

        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name=download_name,
            mimetype="application/pdf",
        )

    except Exception as exc:
        logger.exception("Error generating PDF report")
        return jsonify({"error": str(exc)}), 500


# ── Monitoring ────────────────────────────────────────────────────────────

@app.route("/api/usage")
def usage():
    """Server usage statistics for monitoring dashboards."""
    stats = session_store.stats()
    return jsonify({
        "active_sessions": stats["active_sessions"],
        "total_sessions":  stats["total_sessions"],
        "service":         "PaperMind AI",
        "model_primary":   summarizer.model_name,
        "model_active":    summarizer.active_model or summarizer.model_name,
        "version":         "3.0.0-prod",
    })


@app.route("/api/health")
def health_check():
    """Liveness probe — returns 200 if the service is up."""
    return jsonify({
        "status":        "ok",
        "service":       "PaperMind AI",
        "model_primary": summarizer.model_name,
        "model_active":  summarizer.active_model or summarizer.model_name,
        "version":       "3.0.0-prod",
    })


# ── Helpers ───────────────────────────────────────────────────────────────

def _safe_remove(path: str) -> None:
    """Delete a file silently; log a warning if it fails."""
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError as exc:
        logger.warning("Could not delete file %s: %s", path, exc)


# ── Entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Starting PaperMind AI - Production Edition")
    print("URL:   http://127.0.0.1:7860")
    print(f"Model: {summarizer.model_name} (fallback active)")
    app.run(host="0.0.0.0", port=7860, debug=False, threaded=True)
