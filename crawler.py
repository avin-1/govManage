"""
Trusted Regulatory Crawling & Knowledge Ingestion
--------------------------------------------------
Uses Firecrawl to crawl pre-approved regulatory/compliance sites.
Content is hashed (SHA-256); only changed pages trigger re-chunking and
ChromaDB re-embedding.  All crawled pages are stored in MongoDB.
"""

import hashlib
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Optional deps — graceful degradation
# ---------------------------------------------------------------------------

try:
    from firecrawl import FirecrawlApp
    _firecrawl_ok = True
except ImportError:
    _firecrawl_ok = False
    print("[Crawler] firecrawl-py not installed — run: pip install firecrawl-py")

try:
    from vector_store import delete_document_chunks, upsert_chunks
    _chroma_ok = True
except Exception as _ce:
    _chroma_ok = False
    print(f"[Crawler] ChromaDB unavailable: {_ce}")

from database import db
from file_parser import chunk_text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _embed_page(
    doc_id: str,
    content: str,
    title: str,
    source: Dict[str, Any],
    url: str,
) -> int:
    """Chunk content and upsert into ChromaDB. Returns chunk count."""
    if not _chroma_ok:
        return 0
    chunks = chunk_text(content)
    if not chunks:
        return 0
    upsert_chunks(
        document_id=doc_id,
        chunks=chunks,
        metadata={
            "name": title[:200],
            "source_type": "crawled",
            "source_id": source.get("source_id", ""),
            "region": source.get("region", ""),
            "framework": source.get("framework_type", ""),
            "url": url[:500],
        },
    )
    return len(chunks)


# ---------------------------------------------------------------------------
# Core crawl function
# ---------------------------------------------------------------------------

def crawl_source(source_id: str) -> Dict[str, Any]:
    """
    Crawl all pages for a trusted source.
    Returns: { source_id, pages_crawled, pages_updated, pages_unchanged, errors[] }
    """
    source = db.get_trusted_source(source_id)
    if not source:
        return {"error": f"Source '{source_id}' not found"}

    if not _firecrawl_ok:
        return {"error": "firecrawl-py not installed — run: pip install firecrawl-py"}

    api_key = os.getenv("FIRECRAWL_API_KEY", "").strip()
    if not api_key:
        return {"error": "FIRECRAWL_API_KEY not set in .env"}

    base_url = source.get("base_url", "").strip()
    if not base_url:
        return {"error": "Source has no base_url"}

    fc = FirecrawlApp(api_key=api_key)

    pages_crawled = 0
    pages_updated = 0
    pages_unchanged = 0
    errors: List[str] = []

    try:
        result = fc.crawl_url(
            base_url,
            params={
                "limit": source.get("crawl_limit", 50),
                "scrapeOptions": {"formats": ["markdown"]},
            },
        )
        raw_pages = result.get("data", []) if isinstance(result, dict) else []
    except Exception as exc:
        err_msg = f"Firecrawl error on {base_url}: {exc}"
        print(f"[Crawler] {err_msg}")
        db.update_trusted_source(source_id, {"last_crawled": _now(), "last_error": err_msg})
        return {"source_id": source_id, "error": err_msg,
                "pages_crawled": 0, "pages_updated": 0, "pages_unchanged": 0}

    for page_data in raw_pages:
        try:
            meta = page_data.get("metadata", {})
            url = (
                meta.get("sourceURL")
                or meta.get("url")
                or page_data.get("url", "")
            ).strip()
            if not url:
                continue

            content = (
                page_data.get("markdown")
                or page_data.get("content")
                or page_data.get("text")
                or ""
            ).strip()

            if len(content) < 50:
                continue

            title = meta.get("title") or url
            pages_crawled += 1
            content_hash = _sha256(content)

            existing = db.get_crawled_page_by_url(url)

            if existing and existing.get("content_hash") == content_hash:
                pages_unchanged += 1
                continue

            # New or changed — rechunk + re-embed
            doc_id = existing.get("document_id") if existing else f"crawl_{uuid.uuid4().hex[:12]}"

            if existing and _chroma_ok:
                try:
                    delete_document_chunks(doc_id)
                except Exception:
                    pass

            chunks = chunk_text(content)
            chunk_count = _embed_page(doc_id, content, title, source, url)

            page_doc: Dict[str, Any] = {
                "document_id": doc_id,
                "source_id": source_id,
                "url": url,
                "title": title[:500],
                "raw_text": content,
                "content_hash": content_hash,
                "region": source.get("region", ""),
                "framework": source.get("framework_type", ""),
                "chunk_count": chunk_count or len(chunks),
                "crawl_timestamp": _now(),
            }

            if existing:
                db.update_crawled_page(url, page_doc)
            else:
                db.add_crawled_page(page_doc)

            pages_updated += 1

        except Exception as page_err:
            err = f"Page error: {page_err}"
            errors.append(err)
            print(f"[Crawler] {err}")

    db.update_trusted_source(
        source_id,
        {
            "last_crawled": _now(),
            "last_error": errors[0] if errors else None,
            "last_crawl_summary": {
                "pages_crawled": pages_crawled,
                "pages_updated": pages_updated,
                "pages_unchanged": pages_unchanged,
            },
        },
    )

    summary = {
        "source_id": source_id,
        "pages_crawled": pages_crawled,
        "pages_updated": pages_updated,
        "pages_unchanged": pages_unchanged,
        "errors": errors,
    }
    print(
        f"[Crawler] {source.get('name','?')} | crawled={pages_crawled} "
        f"updated={pages_updated} unchanged={pages_unchanged}"
    )
    return summary


# ---------------------------------------------------------------------------
# Scheduler — called from a background thread in app.py
# ---------------------------------------------------------------------------

def check_and_crawl_due_sources() -> List[Dict[str, Any]]:
    """
    Find all active sources whose next scheduled crawl is due and run them.
    Returns list of crawl summaries.
    """
    due = db.get_due_sources()
    results = []
    for source in due:
        sid = source.get("source_id", "")
        print(f"[Crawler] Scheduled crawl: {source.get('name', sid)}")
        result = crawl_source(sid)
        results.append(result)
    return results
