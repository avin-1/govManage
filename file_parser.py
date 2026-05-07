import io
from typing import List

ALLOWED_EXTENSIONS = {"pdf", "docx", "doc", "txt", "md"}


def parse_file(filename: str, file_bytes: bytes) -> str:
    """Dispatch to the correct extractor based on file extension."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "txt"
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file type '.{ext}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}")
    if ext == "pdf":
        return _parse_pdf(file_bytes)
    if ext in ("docx", "doc"):
        return _parse_docx(file_bytes)
    return file_bytes.decode("utf-8", errors="replace")


def _parse_pdf(file_bytes: bytes) -> str:
    try:
        import pypdf
    except ImportError as exc:
        raise RuntimeError("pypdf is required for PDF parsing: pip install pypdf") from exc

    reader = pypdf.PdfReader(io.BytesIO(file_bytes))
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)
    return "\n".join(pages)


def _parse_docx(file_bytes: bytes) -> str:
    try:
        import docx
    except ImportError as exc:
        raise RuntimeError("python-docx is required for DOCX parsing: pip install python-docx") from exc

    doc = docx.Document(io.BytesIO(file_bytes))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    """
    Word-based sliding-window chunking.
    chunk_size=500 words, overlap=50 words between consecutive chunks.
    """
    words = text.split()
    if not words:
        return []

    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i : i + chunk_size])
        chunks.append(chunk)
        if i + chunk_size >= len(words):
            break
        i += chunk_size - overlap

    return chunks
