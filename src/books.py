"""Book parsing and metadata extraction."""

import json
import logging
import os
import re
import time
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional, List, Dict, Any

import ebooklib
from ebooklib import epub
from platformdirs import user_cache_dir

logger = logging.getLogger(__name__)


@dataclass
class BookMetadata:
    """Metadata for a single book."""
    title: str
    author: Optional[str] = None
    published: Optional[str] = None
    path: str = ""
    toc: List[tuple] = None  # List of (title, chapter_id, depth)
    text: str = ""  # Full text of the book
    
    def __post_init__(self):
        if self.toc is None:
            self.toc = []


# Parsing helpers
class HTMLToText(HTMLParser):
    """Convert HTML to plain text."""
    
    def __init__(self):
        super().__init__()
        self.text = []
        self.skip = False
    
    def handle_starttag(self, tag, attrs):
        if tag in ['script', 'style']:
            self.skip = True
    
    def handle_endtag(self, tag):
        if tag in ['script', 'style']:
            self.skip = False
        elif tag in ['p', 'div', 'br']:
            # Double newline improves paragraph detection for context extraction
            self.text.append('\n\n')
    
    def handle_data(self, data):
        if not self.skip:
            self.text.append(data)
    
    def get_text(self):
        return ''.join(self.text)


def _read_epub(path: str):
    try:
        return epub.read_epub(path)
    except Exception as e:
        logger.error("Error reading EPUB %s: %s", Path(path).name, e)
        return None


def parse_epub_metadata(path: str) -> BookMetadata | None:
    """Parse EPUB file and extract metadata and table of contents."""
    book = _read_epub(path)
    if not book:
        return None

    # Extract metadata
    title = Path(path).stem
    author = None
    published = None

    # Get title from metadata
    if hasattr(book, 'title') and book.title:
        title = book.title

    # Extract author and date from metadata
    if hasattr(book, 'metadata') and book.metadata:
        metadata = book.metadata
        if 'http://purl.org/dc/elements/1.1/' in metadata:
            dc = metadata['http://purl.org/dc/elements/1.1/']
            if 'creator' in dc and dc['creator']:
                author = str(dc['creator'][0][0]) if dc['creator'] else None
            if 'date' in dc and dc['date']:
                published = str(dc['date'][0][0]) if dc['date'] else None

    # Extract TOC
    toc = []
    if book.toc:
        for item in book.toc:
            if isinstance(item, tuple):
                title_text, uid = item
                title_value = getattr(title_text, "title", title_text)
                toc.append((str(title_value), str(uid), 0))
            else:
                title_value = item.title if hasattr(item, "title") else item
                toc.append((str(title_value), "", 0))

    return BookMetadata(
        title=title,
        author=author,
        published=published,
        path=path,
        toc=toc,
        text="",
    )


def parse_epub_text(path: str) -> str:
    """Parse EPUB file and extract full text content."""
    book = _read_epub(path)
    if not book:
        return ""

    text_content = []

    # Build a dict of items by ID for quick lookup
    items_by_id = {item.get_id(): item for item in book.get_items()}

    for item in book.spine:
        # item can be a string ID or a tuple (id, linear)
        if isinstance(item, tuple):
            item_id = item[0]
        else:
            item_id = item

        try:
            doc = items_by_id.get(item_id)
            if doc and hasattr(doc, 'get_content'):
                content = doc.get_content()
                if isinstance(content, bytes):
                    content = content.decode('utf-8', errors='ignore')

                # Convert HTML to text
                parser = HTMLToText()
                parser.feed(content)
                text = parser.get_text()
                text_content.append(text)
        except Exception:
            pass  # Skip items that fail

    return '\n'.join(text_content)


def parse_epub(path: str) -> BookMetadata | None:
    """Parse EPUB file and extract metadata and content."""
    metadata = parse_epub_metadata(path)
    if not metadata:
        return None
    metadata.text = parse_epub_text(path)
    return metadata


def _normalize_search_paths(paths: Optional[list[str]]) -> list[Path]:
    if paths:
        return [Path(p).expanduser() for p in paths if p]
    env_paths = os.getenv("EPUBLIC_LIBRARY_PATHS")
    if env_paths:
        return [Path(p).expanduser() for p in env_paths.split(os.pathsep) if p]
    return []


def _discover_book_paths(search_paths: list[Path]) -> list[str]:
    supported_formats = {".epub", ".mobi", ".azw3", ".azw"}
    paths: list[str] = []

    for base_path in search_paths:
        if not base_path.exists():
            continue
        for root, _, files in os.walk(base_path):
            for file in files:
                if Path(file).suffix.lower() not in supported_formats:
                    continue
                if not file.lower().endswith(".epub"):
                    continue
                paths.append(os.path.join(root, file))

    if not paths:
        logger.warning("No books found in search paths: %s", ", ".join(str(p) for p in search_paths))

    return paths


def _library_signature_from_paths(paths: list[str], roots: list[str]) -> dict:
    entries = []
    for path in paths:
        try:
            stat = Path(path).stat()
        except OSError:
            continue
        entries.append({"path": path, "mtime": stat.st_mtime, "size": stat.st_size})
    entries.sort(key=lambda e: e["path"])
    return {"roots": roots, "count": len(entries), "entries": entries}


def _load_metadata_cache(cache_path: Path) -> Optional[dict]:
    if not cache_path.exists():
        return None
    try:
        return json.loads(cache_path.read_text())
    except Exception:
        return None


def _save_metadata_cache(cache_path: Path, payload: dict) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(payload, separators=(",", ":")))


# Public API
def scan_kindle_library(search_paths: list[str]) -> Dict[str, BookMetadata]:
    """Scan the library and parse all book metadata."""
    books = {}
    normalized_paths = _normalize_search_paths(search_paths)
    for file_path in _discover_book_paths(normalized_paths):
        logger.info("Parsing metadata: %s", Path(file_path).name)
        book = parse_epub_metadata(file_path)
        if book:
            books[book.title] = book
    return books


def _books_from_cache_payload(payload: dict) -> Dict[str, BookMetadata]:
    books = {}
    for item in payload.get("books", []):
        raw_toc = item.get("toc") or []
        normalized_toc = []
        for entry in raw_toc:
            if not isinstance(entry, (list, tuple)) or len(entry) < 1:
                continue
            title = str(entry[0])
            uid = str(entry[1]) if len(entry) > 1 else ""
            depth = entry[2] if len(entry) > 2 else 0
            normalized_toc.append((title, uid, depth))
        books[item["title"]] = BookMetadata(
            title=item["title"],
            author=item.get("author"),
            published=item.get("published"),
            path=item.get("path", ""),
            toc=normalized_toc,
            text="",
        )
    return books


def _metadata_cache_path() -> Path:
    cache_dir = Path(user_cache_dir("epublic-library"))
    return cache_dir / "metadata.json"


def load_cached_books(search_paths: list[str]) -> tuple[Dict[str, BookMetadata], bool]:
    """Load cached books without scanning the filesystem; may return empty."""
    cache_path = _metadata_cache_path()
    cached = _load_metadata_cache(cache_path)
    if cached:
        cached_roots = cached.get("roots", [])
        if cached_roots != search_paths:
            return {}, False
        books = _books_from_cache_payload(cached)
        logger.info("Loaded metadata cache for %s books", len(books))
        return books, True
    return {}, False


def refresh_books_cache(search_paths: list[str]) -> Dict[str, BookMetadata]:
    """Rebuild metadata cache with a full scan if the library has changed."""
    cache_path = _metadata_cache_path()

    normalized_paths = _normalize_search_paths(search_paths)
    if not normalized_paths:
        logger.error("No library paths configured; set EPUBLIC_LIBRARY_PATHS or pass paths in args")
        return {}
    paths = _discover_book_paths(normalized_paths)
    signature = _library_signature_from_paths(paths, [str(p) for p in normalized_paths])

    cached = _load_metadata_cache(cache_path)
    if cached and cached.get("signature") == signature:
        books = _books_from_cache_payload(cached)
        logger.info("Metadata cache is up to date")
        return books

    start = time.perf_counter()
    books = scan_kindle_library(search_paths)
    payload = {
        "roots": [str(p) for p in normalized_paths],
        "signature": signature,
        "books": [
            {
                "title": book.title,
                "author": book.author,
                "published": book.published,
                "path": book.path,
                "toc": book.toc,
            }
            for book in books.values()
        ],
    }
    _save_metadata_cache(cache_path, payload)
    elapsed = time.perf_counter() - start
    logger.info("Rebuilt metadata cache for %s books in %.2fs", len(books), elapsed)
    return books


def get_books(search_paths: Optional[list[str]] = None) -> tuple[Dict[str, BookMetadata], bool]:
    """Get all books from Kindle library, using a metadata cache."""
    paths = search_paths or []
    books, from_cache = load_cached_books(paths)
    if books:
        return books, from_cache
    return refresh_books_cache(paths), False
