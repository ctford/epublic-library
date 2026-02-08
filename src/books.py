"""Book parsing and metadata extraction."""

import os
import re
import json
import logging
import time
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from html.parser import HTMLParser
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
                toc.append((str(title_text), str(uid), 0))
            else:
                toc.append((str(item.title) if hasattr(item, 'title') else str(item), "", 0))

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


def _search_paths() -> list[Path]:
    kindle_path = Path.home() / "Library" / "Application Support" / "Amazon" / "Kindle"
    search_paths = [kindle_path]

    # Also search Sync folder for testing
    sync_path = Path.home() / "Sync"
    if sync_path.exists():
        search_paths.append(sync_path)

    return search_paths


def _discover_book_paths() -> list[str]:
    supported_formats = {".epub", ".mobi", ".azw3", ".azw"}
    paths: list[str] = []
    search_paths = _search_paths()

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


def _books_signature_from_paths(paths: list[str]) -> dict:
    entries = []
    for path in paths:
        try:
            stat = Path(path).stat()
        except OSError:
            continue
        entries.append({"path": path, "mtime": stat.st_mtime, "size": stat.st_size})
    entries.sort(key=lambda e: e["path"])
    return {"count": len(entries), "entries": entries}


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


def scan_kindle_library() -> Dict[str, BookMetadata]:
    """Scan Kindle library and parse all books."""
    books = {}
    for file_path in _discover_book_paths():
        logger.info("Parsing metadata: %s", Path(file_path).name)
        book = parse_epub_metadata(file_path)
        if book:
            books[book.title] = book
    return books


def _books_from_cache_payload(payload: dict) -> Dict[str, BookMetadata]:
    books = {}
    for item in payload.get("books", []):
        books[item["title"]] = BookMetadata(
            title=item["title"],
            author=item.get("author"),
            published=item.get("published"),
            path=item.get("path", ""),
            toc=item.get("toc") or [],
            text="",
        )
    return books


def load_cached_books() -> tuple[Dict[str, BookMetadata], bool]:
    """Load cached books without scanning the filesystem."""
    cache_dir = Path(user_cache_dir("epublic-library"))
    cache_path = cache_dir / "metadata.json"
    cached = _load_metadata_cache(cache_path)
    if cached:
        books = _books_from_cache_payload(cached)
        logger.info("Loaded metadata cache for %s books", len(books))
        return books, True
    return {}, False


def refresh_books_cache() -> Dict[str, BookMetadata]:
    """Rebuild metadata cache if the library has changed."""
    cache_dir = Path(user_cache_dir("epublic-library"))
    cache_path = cache_dir / "metadata.json"

    paths = _discover_book_paths()
    signature = _books_signature_from_paths(paths)

    cached = _load_metadata_cache(cache_path)
    if cached and cached.get("signature") == signature:
        books = _books_from_cache_payload(cached)
        logger.info("Metadata cache is up to date")
        return books

    start = time.perf_counter()
    books = scan_kindle_library()
    payload = {
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


def get_books() -> tuple[Dict[str, BookMetadata], bool]:
    """Get all books from Kindle library, using a metadata cache."""
    books, from_cache = load_cached_books()
    if books:
        return books, from_cache
    return refresh_books_cache(), False
