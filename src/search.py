"""Search functionality for books."""

import re
from typing import List, Dict, Any, Optional, Callable
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
    query: str | None,
    books: Dict[str, BookMetadata],
    limit: int = 10,
    offset: int = 0,
    book_filter: Optional[str] = None,
    author_filter: Optional[str] = None,
    match_type: str = "fuzzy",
    topics: Optional[list[str]] = None,
    text_loader: Optional[Callable[[BookMetadata], str]] = None,
) -> Dict[str, Any]:
    """Search for topic in book content."""
    results = []
    if query is not None:
        topic_list = [query]
    else:
        topic_list = []

    if topics:
        topic_list = list(topics)

    if not topic_list:
        return {
            "total_results": 0,
            "offset": offset,
            "limit": limit,
            "results": [],
        }

    if match_type not in {"exact", "fuzzy"}:
        raise ValueError("match_type must be 'exact' or 'fuzzy'")

    filter_matcher = _fuzzy_match if match_type == "fuzzy" else _exact_match

    def _normalize(text: str) -> str:
        return re.sub(r'\s+', ' ', text).strip()

    def _extract_paragraph(text: str, pos: int) -> tuple[str, Optional[str], Optional[str]]:
        prev_break = text.rfind("\n\n", 0, pos)
        start = 0 if prev_break == -1 else prev_break + 2
        next_break = text.find("\n\n", pos)
        end = len(text) if next_break == -1 else next_break

        paragraph = _normalize(text[start:end])

        before = None
        if prev_break != -1:
            prev_prev = text.rfind("\n\n", 0, prev_break)
            before_start = 0 if prev_prev == -1 else prev_prev + 2
            before = _normalize(text[before_start:prev_break])

        after = None
        if next_break != -1:
            after_next = text.find("\n\n", next_break + 2)
            after_end = len(text) if after_next == -1 else after_next
            after = _normalize(text[next_break + 2:after_end])

        return paragraph, before, after
    
    for title, book in books.items():
        if book_filter and not filter_matcher(book_filter, book.title):
            continue
        if author_filter:
            if not book.author or not filter_matcher(author_filter, book.author):
                continue

        text = book.text
        if not text and text_loader:
            text = text_loader(book)
        if not text:
            continue
        
        # Find all occurrences of the query
        text_lower = text.lower()
        matches = []
        
        # Simple regex search for the query/topics as whole words
        topic_patterns = []
        for topic in topic_list:
            if not topic:
                continue
            topic_patterns.append(r'\b' + re.escape(topic.lower()) + r'\b')

        if not topic_patterns:
            continue

        combined_pattern = "(" + "|".join(topic_patterns) + ")"
        for match in re.finditer(combined_pattern, text_lower, re.IGNORECASE):
            matches.append(match.start())
        
        # Extract context around each match
        for pos in matches[:3]:  # Limit to 3 matches per book
            paragraph, before, after = _extract_paragraph(text, pos)

            # Try to find which chapter this is in
            location = "Unknown section"
            if book.toc:
                location = book.toc[0][0]  # Default to first chapter
            
            results.append({
                'text': paragraph,
                'book_title': book.title,
                'author': book.author or 'Unknown',
                'location': location,
                'context_before': before,
                'context_after': after,
                'relevance_score': None,
            })

    total_results = len(results)
    if limit <= 0:
        paged_results = results[offset:]
    else:
        paged_results = results[offset:offset + limit]

    return {
        "total_results": total_results,
        "offset": offset,
        "limit": limit,
        "results": paged_results,
    }
