"""Search functionality for books."""

import re
from typing import List, Dict, Any
from dataclasses import asdict, dataclass
from books import BookMetadata


@dataclass
class SearchResult:
    """A single search result with attribution."""
    book: str
    author: str
    chapter: str
    quote: str
    context: str  # surrounding text


def search_metadata(query: str, books: Dict[str, BookMetadata]) -> List[Dict[str, Any]]:
    """Search book metadata (title, author, published year)."""
    query_lower = query.lower()
    results = []
    
    for title, book in books.items():
        # Check if query matches title, author, or year
        title_match = query_lower in title.lower()
        author_match = book.author and query_lower in book.author.lower()
        year_match = book.published and query_lower in book.published
        
        if title_match or author_match or year_match:
            results.append({
                'title': book.title,
                'author': book.author or 'Unknown',
                'published': book.published or 'Unknown',
                'chapters': [ch[0] for ch in book.toc[:5]]  # First 5 chapters
            })
    
    return results


def search_topic(query: str, books: Dict[str, BookMetadata], limit: int = 10) -> List[Dict[str, Any]]:
    """Search for topic in book content."""
    results = []
    query_lower = query.lower()
    
    for title, book in books.items():
        if not book.text:
            continue
        
        # Find all occurrences of the query
        text_lower = book.text.lower()
        matches = []
        
        # Simple regex search for the query as whole words
        pattern = r'\b' + re.escape(query_lower) + r'\b'
        for match in re.finditer(pattern, text_lower, re.IGNORECASE):
            matches.append(match.start())
        
        # Extract context around each match
        for pos in matches[:3]:  # Limit to 3 matches per book
            # Find start of context (250 chars before)
            start = max(0, pos - 250)
            # Find end of context (250 chars after)
            end = min(len(book.text), pos + 250 + len(query))
            
            context = book.text[start:end].strip()
            
            # Clean up whitespace
            context = re.sub(r'\s+', ' ', context)
            
            # Try to find which chapter this is in
            chapter = "Unknown section"
            if book.toc:
                chapter = book.toc[0][0]  # Default to first chapter
            
            results.append({
                'book': book.title,
                'author': book.author or 'Unknown',
                'chapter': chapter,
                'quote': context,
                'relevance': 'found'
            })
            
            if len(results) >= limit:
                break
        
        if len(results) >= limit:
            break
    
    return results
