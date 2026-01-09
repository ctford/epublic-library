"""Book parsing and metadata extraction."""

import os
import re
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from html.parser import HTMLParser
import ebooklib
from ebooklib import epub


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
            self.text.append('\n')
    
    def handle_data(self, data):
        if not self.skip:
            self.text.append(data)
    
    def get_text(self):
        return ''.join(self.text)


def parse_epub(path: str) -> BookMetadata:
    """Parse EPUB file and extract metadata and content."""
    try:
        book = epub.read_epub(path)
    except Exception as e:
        print(f"Error reading EPUB {path}: {e}")
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
                toc.append((str(title_text), uid, 0))
            else:
                toc.append((str(item.title) if hasattr(item, 'title') else str(item), "", 0))
    
    # Extract text content
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
        except Exception as e:
            pass  # Skip items that fail
    
    full_text = '\n'.join(text_content)
    
    return BookMetadata(
        title=title,
        author=author,
        published=published,
        path=path,
        toc=toc,
        text=full_text
    )


def scan_kindle_library() -> Dict[str, BookMetadata]:
    """Scan Kindle library and parse all books."""
    kindle_path = Path.home() / "Library" / "Application Support" / "Amazon" / "Kindle"
    
    books = {}
    supported_formats = {'.epub', '.mobi', '.azw3', '.azw'}
    
    # Try primary Kindle path
    search_paths = [kindle_path]
    
    # Also search Sync folder for testing
    sync_path = Path.home() / "Sync"
    if sync_path.exists():
        search_paths.append(sync_path)
    
    for base_path in search_paths:
        if not base_path.exists():
            continue
        
        # Search for ebook files
        for root, dirs, files in os.walk(base_path):
            for file in files:
                if Path(file).suffix.lower() in supported_formats:
                    file_path = os.path.join(root, file)
                    
                    # For now, focus on EPUB (easier to parse)
                    if file.lower().endswith('.epub'):
                        print(f"Parsing: {file}")
                        book = parse_epub(file_path)
                        if book:
                            books[book.title] = book
    
    if not books:
        print(f"No books found in {kindle_path} or {sync_path}")
    
    return books


def get_books() -> Dict[str, BookMetadata]:
    """Get all books from Kindle library (with caching in production)."""
    return scan_kindle_library()
