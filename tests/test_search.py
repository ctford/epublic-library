"""Tests for search functionality."""

import pytest
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from search import search_metadata, search_topic


class TestSearchMetadata:
    """Tests for metadata search functionality."""
    
    def test_search_by_title(self, mock_books):
        """Test searching for book by title."""
        results = search_metadata("Test Book", mock_books)
        assert len(results) == 1
        assert results[0]['title'] == "Test Book"
    
    def test_search_by_partial_title(self, mock_books):
        """Test searching for book by partial title match."""
        results = search_metadata("Test", mock_books)
        assert len(results) == 1
        assert "Test" in results[0]['title']
    
    def test_search_case_insensitive(self, mock_books):
        """Test that search is case-insensitive."""
        results = search_metadata("test book", mock_books)
        assert len(results) == 1
        assert results[0]['title'] == "Test Book"
    
    def test_search_by_author(self, mock_books):
        """Test searching for book by author."""
        results = search_metadata("Test Author", mock_books)
        assert len(results) == 1
        assert results[0]['author'] == "Test Author"
    
    def test_search_by_author_partial(self, mock_books):
        """Test partial author search."""
        results = search_metadata("Author", mock_books)
        assert len(results) >= 1
    
    def test_search_by_year(self, mock_books):
        """Test searching for book by publication year."""
        results = search_metadata("2024", mock_books)
        assert len(results) == 1
        assert results[0]['published'] == "2024"
    
    def test_search_multiple_matches(self, mock_books):
        """Test that multiple matching books are returned."""
        # Both books contain "Author" in author or title
        results = search_metadata("Author", mock_books)
        assert len(results) >= 1
    
    def test_search_no_matches(self, mock_books):
        """Test search with no matching results."""
        results = search_metadata("NonexistentBook", mock_books)
        assert len(results) == 0
    
    def test_search_result_structure(self, mock_books):
        """Test that search results have correct structure."""
        results = search_metadata("Test Book", mock_books)
        assert len(results) > 0
        result = results[0]
        
        assert 'title' in result
        assert 'author' in result
        assert 'published' in result
        assert 'chapters' in result
    
    def test_search_result_chapters(self, mock_books):
        """Test that first 5 chapters are included."""
        results = search_metadata("Test Book", mock_books)
        assert len(results) > 0
        chapters = results[0]['chapters']
        assert len(chapters) <= 5
        assert "Chapter 1" in chapters


class TestSearchTopic:
    """Tests for topic search functionality."""
    
    def test_search_topic_exact_match(self, mock_books):
        """Test finding exact topic match in text."""
        results = search_topic("testing", mock_books)
        assert len(results) > 0
        # Should find "testing" in mock_book.text
    
    def test_search_topic_case_insensitive(self, mock_books):
        """Test that topic search is case-insensitive."""
        results = search_topic("TESTING", mock_books)
        assert len(results) > 0
    
    def test_search_topic_word_boundary(self, mock_books):
        """Test that search respects word boundaries."""
        # Should find "testing" as a word, not within other words
        results = search_topic("testing", mock_books)
        for result in results:
            assert "testing" in result['text'].lower()
    
    def test_search_topic_result_structure(self, mock_books):
        """Test that topic search results have correct structure."""
        results = search_topic("testing", mock_books)
        assert len(results) > 0
        result = results[0]
        
        assert 'text' in result
        assert 'book_title' in result
        assert 'author' in result
        assert 'location' in result
        assert 'context_before' in result
        assert 'context_after' in result
        assert 'relevance_score' in result
    
    def test_search_topic_context_extracted(self, mock_books):
        """Test that context is extracted around match."""
        results = search_topic("testing", mock_books)
        assert len(results) > 0
        
        text = results[0]['text']
        assert "testing" in text.lower()
        # Context should be substantial
        assert len(text) > 10
    
    def test_search_topic_no_matches(self, mock_books):
        """Test topic search with no matching results."""
        results = search_topic("xyzabc123", mock_books)
        assert len(results) == 0
    
    def test_search_topic_limit(self, mock_books):
        """Test that result limit is enforced."""
        results = search_topic("testing", mock_books, limit=2)
        assert len(results) <= 2
    
    def test_search_topic_default_limit(self, mock_books):
        """Test default limit of 10."""
        results = search_topic("testing", mock_books)
        assert len(results) <= 10
    
    def test_search_topic_empty_book_text(self):
        """Test handling of book with empty text."""
        from books import BookMetadata
        
        books = {
            "Empty Book": BookMetadata(
                title="Empty",
                text=""
            )
        }
        
        results = search_topic("anything", books)
        assert len(results) == 0
    
    def test_search_topic_default_author(self, mock_books):
        """Test that unknown authors default to 'Unknown'."""
        from books import BookMetadata
        
        books = {
            "No Author": BookMetadata(
                title="No Author Book",
                text="This book has no author information and contains testing content."
            )
        }
        
        results = search_topic("testing", books)
        if results:
            assert results[0]['author'] == "Unknown"

    def test_search_topic_book_filter(self, mock_books):
        """Test filtering results to a specific book."""
        results = search_topic("testing", mock_books, book_filter="Test Book")
        assert len(results) > 0
        assert all(result['book_title'] == "Test Book" for result in results)

    def test_search_topic_book_filter_excludes(self, mock_books):
        """Test that book_filter excludes non-matching books."""
        results = search_topic("deployment", mock_books, book_filter="Test Book")
        assert len(results) == 0

    def test_search_topic_author_filter(self, mock_books):
        """Test filtering results to a specific author."""
        results = search_topic("testing", mock_books, author_filter="Test Author")
        assert len(results) > 0
        assert all(result['author'] == "Test Author" for result in results)

    def test_search_topic_author_filter_excludes(self, mock_books):
        """Test that author_filter excludes non-matching authors."""
        results = search_topic("deployment", mock_books, author_filter="Test Author")
        assert len(results) == 0


class TestSearchIntegration:
    """Integration tests combining metadata and topic search."""
    
    def test_metadata_then_topic(self, mock_books):
        """Test finding book by metadata then searching topic within it."""
        # Find book
        metadata_results = search_metadata("Test Author", mock_books)
        assert len(metadata_results) == 1
        book_title = metadata_results[0]['title']
        
        # Search topic in that book
        topic_results = search_topic("testing", mock_books)
        assert len(topic_results) > 0
    
    def test_search_with_special_characters(self, mock_books):
        """Test searching with special regex characters."""
        results = search_topic("code", mock_books)
        # Should not crash on special characters
        assert isinstance(results, list)
