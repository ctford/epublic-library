"""Search functionality for books."""

import logging
import os
import re
import sqlite3
import time
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
import threading

from platformdirs import user_cache_dir

logger = logging.getLogger(__name__)
from books import BookMetadata, NO_TEXT_THRESHOLD
_index_build_lock = threading.Lock()

# Try to import fuzzy matching, but make it optional
try:
    from fuzzywuzzy import fuzz
    HAS_FUZZY = True
except ImportError:
    HAS_FUZZY = False


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
    
    for book in books.values():
        # Check if query matches title, author, or year
        title_match = matcher(query, book.title)
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


# Bump when the FTS schema changes so existing on-disk indexes are rebuilt.
INDEX_SCHEMA_VERSION = 2


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
    return {"schema": INDEX_SCHEMA_VERSION, "count": len(entries), "entries": entries}


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


def _open_connection(index_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(index_path)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA synchronous=NORMAL")
    except sqlite3.Error:
        pass
    return conn


def _ensure_index(
    books: Dict[str, BookMetadata],
    text_loader: Optional[Callable[[BookMetadata], str]],
    index_path: str,
    conn: Optional[sqlite3.Connection] = None,
    chapter_loader: Optional[Callable[[BookMetadata], list]] = None,
) -> bool:
    if index_path != ":memory:":
        Path(index_path).parent.mkdir(parents=True, exist_ok=True)

    rebuild = os.getenv("EPUBLIC_REBUILD_INDEX") == "1"
    index_file = Path(index_path)
    signature_path = index_file.with_suffix(index_file.suffix + ".meta")
    signature = _books_signature(books)
    previous = _load_signature(signature_path) if index_path != ":memory:" else None
    needs_rebuild = previous != signature

    if not rebuild and not needs_rebuild and index_path != ":memory:" and index_file.exists():
        return False

    owns_conn = conn is None
    conn = conn or _open_connection(index_path)
    try:
        with _index_build_lock:
            start = None
            paragraph_count = 0
            if rebuild or index_path == ":memory:" or (index_path != ":memory:" and not Path(index_path).exists()):
                start = time.perf_counter()

            cur = conn.cursor()
            cur.execute("DROP TABLE IF EXISTS paragraphs_fts")
            # Only `text` is indexed; metadata columns are stored (so they can be
            # returned and filtered) but kept out of the inverted index. Context
            # is reconstructed from neighbouring rows at query time rather than
            # stored, which previously tripled the on-disk size.
            cur.execute(
                "CREATE VIRTUAL TABLE paragraphs_fts USING fts5("
                "text, book_title UNINDEXED, author UNINDEXED, location UNINDEXED)"
            )

            insert_sql = (
                "INSERT INTO paragraphs_fts "
                "(text, book_title, author, location) "
                "VALUES (?, ?, ?, ?)"
            )

            for book in books.values():
                if chapter_loader:
                    book_chapters = chapter_loader(book)
                else:
                    text = book.text
                    if not text and text_loader:
                        text = text_loader(book)
                    book_chapters = [("", text)] if text else []

                book_text_len = sum(len(t) for _, t in book_chapters if t)
                if book_text_len < NO_TEXT_THRESHOLD:
                    logger.warning(
                        "Book has no usable text layer (%d chars); it cannot be "
                        "found by topic search: %s",
                        book_text_len,
                        book.title,
                    )

                for chapter_title, text in book_chapters:
                    if not text:
                        continue
                    paragraphs = _split_paragraphs(text)
                    if not paragraphs:
                        continue

                    location = chapter_title or (book.toc[0][0] if book.toc else "Unknown section")
                    for paragraph in paragraphs:
                        cur.execute(
                            insert_sql,
                            (
                                _normalize(paragraph),
                                book.title,
                                book.author or "Unknown",
                                location,
                            ),
                        )
                        paragraph_count += 1

            conn.commit()
            if start is not None:
                elapsed = time.perf_counter() - start
                logger.info("Built FTS index with %s paragraphs in %.2fs", paragraph_count, elapsed)
            if index_path != ":memory:":
                _save_signature(signature_path, signature)

        # Reclaim pages freed by the rebuild so the file shrinks on disk
        # (VACUUM cannot run inside the transaction above).
        if index_path != ":memory:":
            try:
                conn.execute("VACUUM")
            except sqlite3.Error as exc:
                logger.warning("VACUUM after index rebuild failed: %s", exc)
    finally:
        if owns_conn:
            conn.close()
    return True


# Front/back-matter locations that rarely contain citable prose; excluded from
# topic results so cover/TOC/index fragments don't crowd out real matches.
BOILERPLATE_LOCATION_PATTERNS = (
    "cover",
    "title page",
    "table of contents",
    "contents",
    "index",
    "copyright",
    "dedication",
    "acknowledg",
    "about the author",
    "colophon",
)

# If the best match in a (ranked) result set scores below this, the query
# probably has no strong match and the results are likely noise.
LOW_CONFIDENCE_SCORE = 0.2


def _escape_fts_phrase(term: str) -> str:
    term = term.strip()
    if not term:
        return ""
    # Escape double quotes inside an FTS phrase by doubling them.
    term = term.replace('"', '""')
    return f"\"{term}\""


def _build_fts_query(topic_list: list[str]) -> str:
    terms = [_escape_fts_phrase(t) for t in topic_list if t and t.strip()]
    return " OR ".join(terms)


def _neighbour_context(cur, rowid: int, book_title: str, location: str) -> tuple[str, str]:
    """Reconstruct (before, after) from adjacent rows in the same chapter.

    Paragraphs are inserted sequentially, so rowid-1 / rowid+1 are the previous
    and next paragraphs. A neighbour only counts as context if it belongs to the
    same book and location, matching how context used to be stored.
    """
    def fetch(target_rowid: int) -> str:
        row = cur.execute(
            "SELECT text, book_title, location FROM paragraphs_fts WHERE rowid = ?",
            (target_rowid,),
        ).fetchone()
        if row and row["book_title"] == book_title and row["location"] == location:
            return row["text"]
        return ""

    return fetch(rowid - 1), fetch(rowid + 1)


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
    chapter_loader: Optional[Callable[[BookMetadata], list]] = None,
    phrase: bool = False,
) -> Dict[str, Any]:
    """Search for a topic in book content using SQLite FTS.

    With ``phrase=True`` the query is matched as a verbatim, case-insensitive
    substring (a LIKE scan over the text column) rather than ranked FTS tokens —
    use this for citation verification, where a quote must be found exactly even
    if the ranker would not surface it. Cover/TOC/index fragments are always
    excluded, and ranked results carry a ``low_confidence`` flag when even the
    best match is weak.
    """
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

    if _index_build_lock.locked():
        return {
            "error": "indexing in progress; try again shortly"
        }

    if match_type not in {"exact", "fuzzy"}:
        raise ValueError("match_type must be 'exact' or 'fuzzy'")

    if not index_path:
        index_path = os.getenv("EPUBLIC_INDEX_PATH")
    if not index_path:
        cache_dir = user_cache_dir("epublic-library")
        index_path = str(Path(cache_dir) / "index.sqlite")
    if index_path == ":memory:":
        conn = _open_connection(":memory:")
        rebuilt = _ensure_index(books, text_loader, index_path, conn=conn, chapter_loader=chapter_loader)
    else:
        rebuilt = _ensure_index(books, text_loader, index_path, chapter_loader=chapter_loader)
        conn = _open_connection(index_path)

    try:
        if rebuilt:
            logger.warning(
                "FTS index was rebuilt on demand; first query may be slow"
            )
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        where: list[str] = []
        params: list[Any] = []

        if phrase:
            # Verbatim substring match on the text column (LIKE is
            # case-insensitive for ASCII), OR'd across topics.
            like_clauses = []
            for topic in topic_list:
                like_clauses.append("text LIKE ?")
                params.append(f"%{_normalize(topic)}%")
            where.append("(" + " OR ".join(like_clauses) + ")")
        else:
            where.append("paragraphs_fts MATCH ?")
            params.append(_build_fts_query(topic_list))

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

        # Always drop front/back-matter (cover, TOC, index, ...) noise.
        for pattern in BOILERPLATE_LOCATION_PATTERNS:
            where.append("location NOT LIKE ? COLLATE NOCASE")
            params.append(f"%{pattern}%")

        where_sql = " AND ".join(where)

        total_sql = f"SELECT COUNT(*) FROM paragraphs_fts WHERE {where_sql}"
        total_results = cur.execute(total_sql, params).fetchone()[0]

        # Phrase matches are exact, so order by document position; ranked
        # matches order by bm25 (ascending = most relevant first).
        if phrase:
            score_select = "0.0 AS score"
            order_sql = "ORDER BY rowid ASC"
        else:
            score_select = "bm25(paragraphs_fts) AS score"
            order_sql = "ORDER BY score ASC"

        query_sql = (
            "SELECT rowid, text, book_title, author, location, "
            f"{score_select} "
            f"FROM paragraphs_fts WHERE {where_sql} "
            + order_sql
        )

        query_params = list(params)
        if limit > 0:
            query_sql += " LIMIT ? OFFSET ?"
            query_params.extend([limit, offset])
        elif offset:
            # SQLite requires LIMIT when using OFFSET.
            query_sql += " LIMIT -1 OFFSET ?"
            query_params.append(offset)

        rows = cur.execute(query_sql, query_params).fetchall()
        results = []
        for row in rows:
            if phrase:
                # Exact substring hit: full confidence.
                relevance_score = 1.0
            else:
                score = row["score"]
                # bm25 is more negative for better matches; map |bm25| -> (0,1)
                # so a higher relevance_score means a stronger match.
                magnitude = abs(score) if score is not None else 0.0
                relevance_score = round(magnitude / (1.0 + magnitude), 3)
            before, after = _neighbour_context(
                cur, row["rowid"], row["book_title"], row["location"]
            )
            results.append(
                {
                    "text": row["text"],
                    "book_title": row["book_title"],
                    "author": row["author"],
                    "location": row["location"],
                    "context_before": before,
                    "context_after": after,
                    "relevance_score": relevance_score,
                }
            )

        low_confidence = (
            not phrase
            and bool(results)
            and max(r["relevance_score"] for r in results) < LOW_CONFIDENCE_SCORE
        )

        return {
            "total_results": total_results,
            "offset": offset,
            "limit": limit,
            "phrase": phrase,
            "low_confidence": low_confidence,
            "results": results,
        }
    finally:
        conn.close()


def prebuild_index(
    books: Dict[str, BookMetadata],
    text_loader: Optional[Callable[[BookMetadata], str]] = None,
    index_path: Optional[str] = None,
    chapter_loader: Optional[Callable[[BookMetadata], list]] = None,
) -> bool:
    if not index_path:
        index_path = os.getenv("EPUBLIC_INDEX_PATH")
    if not index_path:
        cache_dir = user_cache_dir("epublic-library")
        index_path = str(Path(cache_dir) / "index.sqlite")
    rebuilt = _ensure_index(books, text_loader, index_path, chapter_loader=chapter_loader)
    if rebuilt:
        logger.info("FTS index rebuilt on startup")
    else:
        logger.info("FTS index is up to date")
    return rebuilt
