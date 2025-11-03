import fitz  # PyMuPDF

def extract_text_from_pdf(path: str) -> str:
    """Extracts and returns full text from a PDF file using PyMuPDF."""
    doc = fitz.open(path)
    parts = []
    for page in doc:
        parts.append(page.get_text("text"))
    doc.close()
    return "\n\n".join(parts)
