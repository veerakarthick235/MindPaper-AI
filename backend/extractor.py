"""
extractor.py
------------
Robust PDF text extraction using PyMuPDF (fitz).

Features:
- Encrypted/password-protected PDF detection with a user-friendly error
- Page-count cap (200 pages) to prevent OOM on massive documents
- Control-character stripping for clean downstream text processing
- Graceful error propagation with descriptive messages
"""

import re
import fitz  # PyMuPDF


# Maximum pages extracted — prevents OOM on huge academic compilations
MAX_PAGES = 200


def extract_text_from_pdf(path: str) -> str:
    """
    Extract and return the full plain text from a PDF file.

    Parameters
    ----------
    path : str
        Absolute path to the PDF file on disk.

    Returns
    -------
    str
        Concatenated page text, separated by double newlines.

    Raises
    ------
    ValueError
        If the PDF is encrypted, corrupt, or yields no extractable text.
    RuntimeError
        On unexpected I/O or fitz errors.
    """
    try:
        doc = fitz.open(path)
    except fitz.FileDataError as exc:
        raise ValueError(
            "The uploaded file appears to be corrupt or is not a valid PDF."
        ) from exc
    except Exception as exc:
        raise RuntimeError(f"Failed to open PDF: {exc}") from exc

    # Reject encrypted / password-protected PDFs immediately
    if doc.is_encrypted:
        doc.close()
        raise ValueError(
            "This PDF is password-protected. Please upload an unlocked version."
        )

    total_pages = len(doc)
    pages_to_read = min(total_pages, MAX_PAGES)

    parts: list[str] = []
    for page_num in range(pages_to_read):
        try:
            page = doc[page_num]
            text = page.get_text("text")  # plain text, preserving layout order
            if text.strip():
                parts.append(text)
        except Exception:
            # Skip unreadable pages rather than failing the whole document
            continue

    doc.close()

    if not parts or not "".join(parts).strip():
        raise ValueError(
            "No readable text could be extracted from this PDF. "
            "It may be a scanned image without an OCR layer or completely blank."
        )

    combined = "\n\n".join(parts)

    # Strip non-printable control characters (keep newlines and tabs)
    combined = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", combined)

    # Collapse runs of 3+ blank lines into exactly 2
    combined = re.sub(r"\n{3,}", "\n\n", combined)

    return combined.strip()
