"""Search functionality for books."""

import re
from typing import List, Dict, Any, Optional
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


def search_topic(
    query: str,
    books: Dict[str, BookMetadata],
    limit: int = 10,
    book_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Search for topic in book content."""
    results = []
    query_lower = query.lower()
    
    for title, book in books.items():
        if book_filter and not _fuzzy_match(book_filter, book.title):
            continue

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
