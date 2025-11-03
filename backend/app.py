from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
import os
from dotenv import load_dotenv
from extractor import extract_text_from_pdf
from summarizer import PaperSummarizer
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
import io
import tempfile

# -----------------------------
# Environment Setup
# -----------------------------
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    raise EnvironmentError("❌ GOOGLE_API_KEY not found in .env file. Please add it before running.")

# -----------------------------
# Flask App Initialization
# -----------------------------
app = Flask(__name__, static_folder="../frontend", static_url_path="/")
CORS(app)

# Initialize Gemini Summarizer
summarizer = PaperSummarizer(gemini_api_key=GOOGLE_API_KEY)

# -----------------------------
# Routes
# -----------------------------
@app.route("/")
def index():
    """Serve the frontend index page."""
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/upload", methods=["POST"])
def upload_pdf():
    """Handle PDF upload, text extraction, and AI summarization."""
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file uploaded"}), 400

        file = request.files["file"]
        if not file.filename.lower().endswith(".pdf"):
            return jsonify({"error": "Please upload a valid PDF file"}), 400

        filename = file.filename
        upload_dir = "uploads"
        os.makedirs(upload_dir, exist_ok=True)
        saved_path = os.path.join(upload_dir, filename)
        file.save(saved_path)

        print(f"✅ Uploaded file saved to: {saved_path}")

        # Extract text from the PDF
        text = extract_text_from_pdf(saved_path)
        if not text or len(text.strip()) < 100:
            return jsonify({"error": "Failed to extract meaningful text from PDF."}), 400

        print(f"🧠 Extracted {len(text)} characters from PDF.")

        # Generate AI summary, critique, and future suggestions
        result = summarizer.process_document(text, meta={"filename": filename})

        # Cache result for PDF export
        app.config["last_result"] = result

        return jsonify(result)

    except Exception as e:
        print(f"❌ Error during processing: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/report", methods=["POST"])
def generate_report():
    """Generate a downloadable PDF report from AI output."""
    try:
        data = request.get_json()
        result = data or app.config.get("last_result")

        if not result:
            return jsonify({"error": "No processed data available. Upload and analyze a paper first."}), 400

        summary = result.get("summary", "")
        critique = result.get("critique", "")
        future = result.get("future_directions", "")
        excerpts = result.get("excerpts", [])
        citations = result.get("citations", [])
        filename = result.get("meta", {}).get("filename", "Unknown")

        # Create PDF in memory
        pdf_buffer = io.BytesIO()
        doc = SimpleDocTemplate(pdf_buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []

        story.append(Paragraph("<b>AI Research Paper Summary Report</b>", styles["Title"]))
        story.append(Spacer(1, 12))
        story.append(Paragraph(f"<b>File:</b> {filename}", styles["Normal"]))
        story.append(Spacer(1, 12))

        story.append(Paragraph("<b>Summary</b>", styles["Heading2"]))
        story.append(Paragraph(summary.replace("\n", "<br/>"), styles["Normal"]))
        story.append(Spacer(1, 12))

        story.append(Paragraph("<b>Critique</b>", styles["Heading2"]))
        story.append(Paragraph(critique.replace("\n", "<br/>"), styles["Normal"]))
        story.append(Spacer(1, 12))

        story.append(Paragraph("<b>Future Directions</b>", styles["Heading2"]))
        story.append(Paragraph(future.replace("\n", "<br/>"), styles["Normal"]))
        story.append(Spacer(1, 12))

        if excerpts:
            story.append(Paragraph("<b>Key Excerpts</b>", styles["Heading2"]))
            for ex in excerpts:
                story.append(Paragraph(f"• {ex}", styles["Normal"]))
            story.append(Spacer(1, 12))

        if citations:
            story.append(Paragraph("<b>Citations</b>", styles["Heading2"]))
            for c in citations[:20]:
                story.append(Paragraph(f"- {c}", styles["Normal"]))
            story.append(Spacer(1, 12))

        doc.build(story)
        pdf_buffer.seek(0)

        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name="AI_Research_Report.pdf",
            mimetype="application/pdf",
        )

    except Exception as e:
        print(f"❌ Error generating report: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/health")
def health_check():
    """Simple endpoint to verify backend status."""
    return jsonify({
        "status": "ok",
        "service": "AI Research Paper Summarizer",
        "model": "Gemini 2.5 Flash + RAG + Citation Detection"
    })


# -----------------------------
# Run Flask Server
# -----------------------------
if __name__ == "__main__":
    print("🚀 Starting AI Research Paper Summarizer backend...")
    print("🔗 Access it at: http://127.0.0.1:7860")
    app.run(host="0.0.0.0", port=7860, debug=True)
