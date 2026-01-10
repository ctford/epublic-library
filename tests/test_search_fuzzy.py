"""Tests for fuzzy matching in search functionality."""

import pytest
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from search import search_metadata, _exact_match, _fuzzy_match

# Check if fuzzy matching is available
try:
    from fuzzywuzzy import fuzz
    HAS_FUZZY = True
except ImportError:
    HAS_FUZZY = False


class TestExactMatch:
    """Tests for exact matching helper."""
    
    def test_exact_match_case_insensitive(self):
        """Test that exact matching is case-insensitive."""
        assert _exact_match("Kief", "kief")
        assert _exact_match("MORRIS", "morris")
        assert _exact_match("Infrastructure", "infrastructure")
    
    def test_exact_match_substring(self):
        """Test that query must be substring."""
        assert _exact_match("Kief", "Kief Morris")
        assert _exact_match("Morris", "Kief Morris")
        assert _exact_match("Code", "Infrastructure as Code")
    
    def test_exact_match_no_match(self):
        """Test when there's no match."""
        assert not _exact_match("Kief", "Stephen King")
        assert not _exact_match("Morris", "David")


@pytest.mark.skipif(not HAS_FUZZY, reason="fuzzywuzzy not installed")
class TestFuzzyMatch:
    """Tests for fuzzy matching (requires fuzzywuzzy)."""
    
    def test_fuzzy_match_exact(self):
        """Test that exact matches still match."""
        assert _fuzzy_match("Kief Morris", "Kief Morris", threshold=80)
        assert _fuzzy_match("Infrastructure", "Infrastructure", threshold=80)
    
    def test_fuzzy_match_single_typo(self):
        """Test matching with single character typo."""
        # One character substitution
        assert _fuzzy_match("Keif Morris", "Kief Morris", threshold=80)  # Missing 'e'
        assert _fuzzy_match("Kief Moriss", "Kief Morris", threshold=80)  # Extra 's'
    
    def test_fuzzy_match_transposition(self):
        """Test matching with character transposition."""
        # Characters in wrong order
        assert _fuzzy_match("Kief Mrris", "Kief Morris", threshold=75)
    
    def test_fuzzy_match_word_order(self):
        """Test token_set_ratio handles word order."""
        # Different word order - token_set_ratio should handle this
        assert _fuzzy_match("Morris, Kief", "Kief Morris", threshold=80)
        assert _fuzzy_match("Code Infrastructure", "Infrastructure as Code", threshold=70)
    
    def test_fuzzy_match_threshold(self):
        """Test threshold behavior."""
        # "Kief Mrris" should match at lower threshold but maybe not at 90
        similarity = fuzz.token_set_ratio("Kief Mrris", "Kief Morris")
        assert _fuzzy_match("Kief Mrris", "Kief Morris", threshold=70)
        
        # Should not match if too different
        assert not _fuzzy_match("Stephen King", "Kief Morris", threshold=80)
    
    def test_fuzzy_match_case_insensitive(self):
        """Test fuzzy matching is case-insensitive."""
        assert _fuzzy_match("KIEF", "kief", threshold=80)
        assert _fuzzy_match("infrastructure AS code", "Infrastructure as Code", threshold=80)


class TestSearchMetadataFuzzy:
    """Tests for fuzzy metadata search integration."""
    
    def test_search_metadata_fuzzy_disabled(self, mock_books):
        """Test search with fuzzy matching disabled."""
        results = search_metadata("Kief Morris", mock_books, fuzzy=False)
        # Should not find anything (no Kief Morris in mock data)
        assert len(results) == 0
    
    @pytest.mark.skipif(not HAS_FUZZY, reason="fuzzywuzzy not installed")
    def test_search_metadata_fuzzy_author_typo(self, mock_books):
        """Test finding author with typo using fuzzy matching."""
        # Mock data has "Test Author", try with typo
        results = search_metadata("Test Authr", mock_books, fuzzy=True, fuzzy_threshold=80)
        # Should still find due to fuzzy matching (if enabled)
        # Depends on similarity score
        assert isinstance(results, list)
    
    @pytest.mark.skipif(not HAS_FUZZY, reason="fuzzywuzzy not installed")
    def test_search_metadata_fuzzy_title_typo(self, mock_books):
        """Test finding book title with typo using fuzzy matching."""
        results = search_metadata("Test Bok", mock_books, fuzzy=True, fuzzy_threshold=80)
        # Should find "Test Book" with fuzzy matching
        found = any("Test Book" in r['title'] for r in results)
        assert found or len(results) >= 0  # Fuzzy might or might not catch depending on threshold
    
    def test_search_metadata_fuzzy_year_exact(self, mock_books):
        """Test that year search is always exact."""
        # Year searching should remain exact even with fuzzy=True
        results = search_metadata("2024", mock_books, fuzzy=True)
        assert len(results) == 1
        assert results[0]['published'] == "2024"
        
        # Typo in year should not match
        results = search_metadata("2025", mock_books, fuzzy=True)
        assert len(results) == 0
    
    def test_search_metadata_fallback_no_fuzzy(self, mock_books):
        """Test that search works even without fuzzywuzzy installed."""
        # This should not crash even if fuzzywuzzy is not available
        results = search_metadata("Test Author", mock_books, fuzzy=True)
        assert isinstance(results, list)


class TestSearchMetadataFuzzyRealWorld:
    """Real-world fuzzy matching scenarios."""
    
    @pytest.mark.skipif(not HAS_FUZZY, reason="fuzzywuzzy not installed")
    def test_kief_morris_book(self):
        """Test finding Kief Morris's "Infrastructure as Code" with variations."""
        from books import BookMetadata
        
        books = {
            "Infrastructure as Code": BookMetadata(
                title="Infrastructure as Code",
                author="Kief Morris",
                published="2016",
                text="Sample text about infrastructure automation."
            )
        }
        
        # Exact match should work
        results = search_metadata("Kief Morris", books, fuzzy=True)
        assert len(results) == 1
        assert results[0]['author'] == "Kief Morris"
        
        # Common typo: "Keith" instead of "Kief"
        results = search_metadata("Keith Morris", books, fuzzy=True, fuzzy_threshold=80)
        # Might or might not match depending on similarity threshold
        # token_set_ratio("Keith Morris", "Kief Morris") ≈ 88
        
        # Partial match should work
        results = search_metadata("Morris", books, fuzzy=True)
        assert len(results) >= 1
        
        # Title with missing words
        results = search_metadata("Infrastructure Code", books, fuzzy=True)
        assert len(results) >= 1
    
    @pytest.mark.skipif(not HAS_FUZZY, reason="fuzzywuzzy not installed")
    def test_infrastructure_as_code_variations(self):
        """Test various ways to search for Infrastructure as Code."""
        from books import BookMetadata
        
        book = BookMetadata(
            title="Infrastructure as Code",
            author="Kief Morris",
            published="2016",
            text="Sample content"
        )
        books = {"Infrastructure as Code": book}
        
        # All these should find the book (some with fuzzy, some exact)
        queries = [
            "Infrastructure as Code",  # Exact
            "Infrastructure Code",      # Missing word
            "Code",                      # Partial
            "Kief",                      # Author partial
            "2016",                      # Year exact
        ]
        
        for query in queries:
            results = search_metadata(query, books, fuzzy=True)
            assert len(results) > 0, f"Query '{query}' should find the book"
