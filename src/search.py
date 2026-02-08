"""Search functionality for books."""

import logging
import os
import re
import sqlite3
import time
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable

from platformdirs import user_cache_dir

logger = logging.getLogger(__name__)
from dataclasses import asdict, dataclass
from books import BookMetadata

# Try to import fuzzy matching, but make it optional
try:
    from fuzzywuzzy import fuzz
    HAS_FUZZY = True
except ImportError:
    HAS_FUZZY = False


@dataclass
class SearchResult:
    """A single search result with attribution."""
    book: str
    author: str
    chapter: str
    quote: str
    context: str  # surrounding text


def _exact_match(query: str, target: str) -> bool:
    """Check if query is a substring of target (case-insensitive)."""
    return query.lower() in target.lower()


def _fuzzy_match(query: str, target: str, threshold: int = 80) -> bool:
    """Check if query fuzzy matches target above threshold."""
    if not HAS_FUZZY:
        return _exact_match(query, target)
    
    # Use token_set_ratio for better handling of word order variations
    similarity = fuzz.token_set_ratio(query.lower(), target.lower())
    return similarity >= threshold


def search_metadata(query: str, books: Dict[str, BookMetadata], 
                   fuzzy: bool = True, fuzzy_threshold: int = 80) -> List[Dict[str, Any]]:
    """
    Search book metadata (title, author, published year).
    
    Args:
        query: Search term
        books: Dictionary of books to search
        fuzzy: Enable fuzzy matching for typo tolerance (requires fuzzywuzzy)
        fuzzy_threshold: Similarity threshold for fuzzy matching (0-100)
    
    Returns:
        List of matching books with metadata
    """
    results = []
    matcher = _fuzzy_match if fuzzy else _exact_match
    
    for title, book in books.items():
        # Check if query matches title, author, or year
        title_match = matcher(query, title)
        author_match = book.author and matcher(query, book.author)
        year_match = book.published and _exact_match(query, book.published)  # Year always exact
        
        if title_match or author_match or year_match:
            results.append({
                'title': book.title,
                'author': book.author or 'Unknown',
                'published': book.published or 'Unknown',
                'chapters': [ch[0] for ch in book.toc[:5]]  # First 5 chapters
            })
    
    return results


def _normalize(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip()


def _split_paragraphs(text: str) -> list[str]:
    parts = [p.strip() for p in text.split("\n\n")]
    return [p for p in parts if p]


def _books_signature(books: Dict[str, BookMetadata]) -> dict:
    entries = []
    for book in books.values():
        if not book.path:
            continue
        try:
            stat = Path(book.path).stat()
        except OSError:
            continue
        entries.append(
            {
                "path": book.path,
                "mtime": stat.st_mtime,
                "size": stat.st_size,
            }
        )
    entries.sort(key=lambda e: e["path"])
    return {"count": len(entries), "entries": entries}


def _load_signature(signature_path: Path) -> Optional[dict]:
    if not signature_path.exists():
        return None
    try:
        return json.loads(signature_path.read_text())
    except Exception:
        return None


def _save_signature(signature_path: Path, signature: dict) -> None:
    signature_path.parent.mkdir(parents=True, exist_ok=True)
    signature_path.write_text(json.dumps(signature, separators=(",", ":")))


def _ensure_index(
    books: Dict[str, BookMetadata],
    text_loader: Optional[Callable[[BookMetadata], str]],
    index_path: str,
    conn: Optional[sqlite3.Connection] = None,
) -> None:
    if index_path != ":memory:":
        Path(index_path).parent.mkdir(parents=True, exist_ok=True)

    rebuild = os.getenv("EPUBLIC_REBUILD_INDEX") == "1"
    index_file = Path(index_path)
    signature_path = index_file.with_suffix(index_file.suffix + ".meta")
    signature = _books_signature(books)
    previous = _load_signature(signature_path) if index_path != ":memory:" else None
    needs_rebuild = previous != signature

    if not rebuild and not needs_rebuild and index_path != ":memory:" and index_file.exists():
        return

    owns_conn = conn is None
    conn = conn or sqlite3.connect(index_path)
    try:
        start = None
        paragraph_count = 0
        if rebuild or index_path == ":memory:" or (index_path != ":memory:" and not Path(index_path).exists()):
            start = time.perf_counter()

        cur = conn.cursor()
        cur.execute("DROP TABLE IF EXISTS paragraphs_fts")
        cur.execute(
            "CREATE VIRTUAL TABLE paragraphs_fts USING fts5("
            "text, book_title, author, location, context_before, context_after)"
        )

        insert_sql = (
            "INSERT INTO paragraphs_fts "
            "(text, book_title, author, location, context_before, context_after) "
            "VALUES (?, ?, ?, ?, ?, ?)"
        )

        for book in books.values():
            text = book.text
            if not text and text_loader:
                text = text_loader(book)
            if not text:
                continue

            paragraphs = _split_paragraphs(text)
            if not paragraphs:
                continue

            for i, paragraph in enumerate(paragraphs):
                before = _normalize(paragraphs[i - 1]) if i > 0 else ""
                after = _normalize(paragraphs[i + 1]) if i + 1 < len(paragraphs) else ""
                location = book.toc[0][0] if book.toc else "Unknown section"
                cur.execute(
                    insert_sql,
                    (
                        _normalize(paragraph),
                        book.title,
                        book.author or "Unknown",
                        location,
                        before,
                        after,
                    ),
                )
                paragraph_count += 1

        conn.commit()
        if start is not None:
            elapsed = time.perf_counter() - start
            logger.info("Built FTS index with %s paragraphs in %.2fs", paragraph_count, elapsed)
        if index_path != ":memory:":
            _save_signature(signature_path, signature)
    finally:
        if owns_conn:
            conn.close()


def _build_fts_query(topic_list: list[str]) -> str:
    terms = [f"\"{t}\"" for t in topic_list if t]
    return " OR ".join(terms)


def search_topic(
    query: str | None,
    books: Dict[str, BookMetadata],
    limit: int = 10,
    offset: int = 0,
    book_filter: Optional[str] = None,
    author_filter: Optional[str] = None,
    match_type: str = "fuzzy",
    topics: Optional[list[str]] = None,
    text_loader: Optional[Callable[[BookMetadata], str]] = None,
    index_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Search for topic in book content using SQLite FTS."""
    if query is not None:
        topic_list = [query]
    else:
        topic_list = []

    if topics:
        topic_list = list(topics)

    seen_topics = set()
    deduped_topics = []
    for topic in topic_list:
        if topic not in seen_topics:
            deduped_topics.append(topic)
            seen_topics.add(topic)
    topic_list = deduped_topics

    if not topic_list:
        return {
            "total_results": 0,
            "offset": offset,
            "limit": limit,
            "results": [],
        }

    if match_type not in {"exact", "fuzzy"}:
        raise ValueError("match_type must be 'exact' or 'fuzzy'")

    if not index_path:
        index_path = os.getenv("EPUBLIC_INDEX_PATH")
    if not index_path:
        cache_dir = user_cache_dir("epublic-library")
        index_path = str(Path(cache_dir) / "index.sqlite")
    if index_path == ":memory:":
        conn = sqlite3.connect(":memory:")
        _ensure_index(books, text_loader, index_path, conn=conn)
    else:
        _ensure_index(books, text_loader, index_path)
        conn = sqlite3.connect(index_path)

    try:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        where = ["paragraphs_fts MATCH ?"]
        params: list[Any] = [_build_fts_query(topic_list)]

        if book_filter:
            if match_type == "exact":
                where.append("book_title = ? COLLATE NOCASE")
                params.append(book_filter)
            else:
                where.append("book_title LIKE ?")
                params.append(f"%{book_filter}%")

        if author_filter:
            if match_type == "exact":
                where.append("author = ? COLLATE NOCASE")
                params.append(author_filter)
            else:
                where.append("author LIKE ?")
                params.append(f"%{author_filter}%")

        where_sql = " AND ".join(where)

        total_sql = f"SELECT COUNT(*) FROM paragraphs_fts WHERE {where_sql}"
        total_results = cur.execute(total_sql, params).fetchone()[0]

        limit_sql = "" if limit <= 0 else " LIMIT ? OFFSET ?"
        query_sql = (
            "SELECT text, book_title, author, location, context_before, context_after, "
            "bm25(paragraphs_fts) AS score "
            f"FROM paragraphs_fts WHERE {where_sql} "
            "ORDER BY score ASC" + limit_sql
        )

        query_params = list(params)
        if limit > 0:
            query_params.extend([limit, offset])
        elif offset:
            # SQLite requires LIMIT when using OFFSET.
            query_sql += " LIMIT -1 OFFSET ?"
            query_params.append(offset)

        rows = cur.execute(query_sql, query_params).fetchall()
        results = []
        for row in rows:
            score = row["score"]
            if score is None:
                relevance_score = 0.0
            else:
                relevance_score = 1.0 / (1.0 + abs(score))
                if relevance_score < 0.0:
                    relevance_score = 0.0
                if relevance_score > 1.0:
                    relevance_score = 1.0
                relevance_score = round(relevance_score, 3)
            results.append(
                {
                    "text": row["text"],
                    "book_title": row["book_title"],
                    "author": row["author"],
                    "location": row["location"],
                    "context_before": row["context_before"],
                    "context_after": row["context_after"],
                    "relevance_score": relevance_score,
                }
            )

        return {
            "total_results": total_results,
            "offset": offset,
            "limit": limit,
            "results": results,
        }
    finally:
        conn.close()
