"""Tests for search functionality."""

import pytest
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from search import audit_citations, search_metadata, search_topic, suggest_citation


class TestSearchMetadata:
    """Tests for metadata search functionality."""
    
    def test_search_by_title(self, mock_books):
        """Test searching for book by title."""
        results = search_metadata("Test Book", mock_books)
        assert len(results) == 1
        assert results[0]['title'] == "Test Book"
    
    def test_search_returns_same_titled_books(self):
        """Books sharing a title (keyed by path) are both returned."""
        from books import BookMetadata
        books = {
            "/lib/a.epub": BookMetadata(title="Refactoring", author="Fowler",
                                        published="1999", path="/lib/a.epub"),
            "/lib/b.epub": BookMetadata(title="Refactoring", author="Fowler",
                                        published="2018", path="/lib/b.epub"),
        }
        results = search_metadata("Refactoring", books)
        assert len(results) == 2
        assert {r["published"] for r in results} == {"1999", "2018"}

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
        assert len(results["results"]) > 0
        # Should find "testing" in mock_book.text
    
    def test_search_topic_case_insensitive(self, mock_books):
        """Test that topic search is case-insensitive."""
        results = search_topic("TESTING", mock_books)
        assert len(results["results"]) > 0
    
    def test_search_topic_word_boundary(self, mock_books):
        """Test that search respects word boundaries."""
        # Should find "testing" as a word, not within other words
        results = search_topic("testing", mock_books)
        for result in results["results"]:
            assert "testing" in result['text'].lower()
    
    def test_search_topic_result_structure(self, mock_books):
        """Test that topic search results have correct structure."""
        results = search_topic("testing", mock_books)
        assert len(results["results"]) > 0
        result = results["results"][0]
        
        assert 'text' in result
        assert 'book_title' in result
        assert 'author' in result
        assert 'location' in result
        assert 'context_before' in result
        assert 'context_after' in result
        assert 'relevance_score' in result
        assert 0.0 <= result['relevance_score'] <= 1.0
    
    def test_search_topic_context_extracted(self, mock_books):
        """Test that context is extracted around match."""
        results = search_topic("testing", mock_books)
        assert len(results["results"]) > 0
        
        text = results["results"][0]['text']
        assert "testing" in text.lower()
        # Context should be substantial
        assert len(text) > 10
    
    def test_search_topic_no_matches(self, mock_books):
        """Test topic search with no matching results."""
        results = search_topic("xyzabc123", mock_books)
        assert len(results["results"]) == 0
        assert results["total_results"] == 0
    
    def test_search_topic_limit(self, mock_books):
        """Test that result limit is enforced."""
        results = search_topic("testing", mock_books, limit=2)
        assert len(results["results"]) <= 2
        assert results["limit"] == 2
    
    def test_search_topic_default_limit(self, mock_books):
        """Test default limit of 10."""
        results = search_topic("testing", mock_books)
        assert len(results["results"]) <= 10
        assert results["limit"] == 10

    def test_search_topic_offset(self, mock_books):
        """Test that offset skips results."""
        results = search_topic("testing", mock_books, limit=1, offset=1)
        assert results["total_results"] >= 2
        assert len(results["results"]) == 1
        assert results["offset"] == 1

    def test_search_topic_limit_zero_no_limit(self, mock_books):
        """Limit of zero should return all results after offset."""
        results = search_topic("testing", mock_books, limit=0)
        assert results["limit"] == 0
        assert len(results["results"]) == results["total_results"]

    def test_search_topic_limit_zero_with_offset(self, mock_books):
        """Limit of zero should still honor offset."""
        results = search_topic("testing", mock_books, limit=0, offset=1)
        assert results["limit"] == 0
        assert results["offset"] == 1
        assert len(results["results"]) == max(results["total_results"] - 1, 0)
    
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
        assert len(results["results"]) == 0
    
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
        if results["results"]:
            assert results["results"][0]['author'] == "Unknown"

    def test_search_topic_book_filter(self, mock_books):
        """Test filtering results to a specific book."""
        results = search_topic("testing", mock_books, book_filter="Test Book")
        assert len(results["results"]) > 0
        assert all(result['book_title'] == "Test Book" for result in results["results"])

    def test_search_topic_book_filter_excludes(self, mock_books):
        """Test that book_filter excludes non-matching books."""
        results = search_topic("deployment", mock_books, book_filter="Test Book")
        assert len(results["results"]) == 0

    def test_search_topic_author_filter(self, mock_books):
        """Test filtering results to a specific author."""
        results = search_topic("testing", mock_books, author_filter="Test Author")
        assert len(results["results"]) > 0
        assert all(result['author'] == "Test Author" for result in results["results"])

    def test_search_topic_author_filter_excludes(self, mock_books):
        """Test that author_filter excludes non-matching authors."""
        results = search_topic("deployment", mock_books, author_filter="Test Author")
        assert len(results["results"]) == 0

    def test_search_topic_combined_filters(self, mock_books):
        """Test that book and author filters are applied together."""
        results = search_topic(
            "testing",
            mock_books,
            book_filter="Test Book",
            author_filter="Test Author",
        )
        assert len(results["results"]) > 0
        assert all(result["book_title"] == "Test Book" for result in results["results"])
        assert all(result["author"] == "Test Author" for result in results["results"])

    def test_search_topic_match_type_exact(self, mock_books):
        """Exact match type should be strict for filters."""
        results = search_topic(
            "testing",
            mock_books,
            author_filter="test author",
            match_type="exact",
        )
        assert len(results["results"]) > 0

    def test_search_topic_match_type_fuzzy(self, mock_books):
        """Fuzzy match type should allow partial matches for filters."""
        results = search_topic(
            "testing",
            mock_books,
            author_filter="Author",
            match_type="fuzzy",
        )
        assert len(results["results"]) > 0

    def test_search_topic_multiple_topics(self, mock_books):
        """Multiple topics should match any topic (OR)."""
        results = search_topic(
            None,
            mock_books,
            topics=["testing", "deployment"],
        )
        assert len(results["results"]) > 0

    def test_search_topic_missing_topics(self, mock_books):
        """Missing topic/topics should return no results."""
        results = search_topic(None, mock_books, topics=None)
        assert results["total_results"] == 0
        assert results["results"] == []

    def test_search_topic_indexing_in_progress_returns_error(self, mock_books):
        """Indexing in progress should return a friendly error."""
        from search import _index_build_lock

        _index_build_lock.acquire()
        try:
            results = search_topic("testing", mock_books)
            assert results["error"] == "indexing in progress; try again shortly"
        finally:
            _index_build_lock.release()

    def test_search_topic_invalid_match_type(self, mock_books):
        """Invalid match_type should raise an error."""
        import pytest

        with pytest.raises(ValueError):
            search_topic(
                "testing",
                mock_books,
                match_type="semantic",
            )


class TestSearchMetadataPrecision:
    """Coverage-based matching must not let one shared generic word hide a gap."""

    def _lib(self, *items):
        from books import BookMetadata
        return {
            f"/{i}.epub": BookMetadata(title=t, author=a, published="2020", path=f"/{i}.epub")
            for i, (t, a) in enumerate(items)
        }

    def test_shared_generic_word_is_not_a_match(self):
        books = self._lib(
            ("AI Engineering", "Chip Huyen"),
            ("The Mythical Man-Month: Essays on Software Engineering", "Frederick P. Brooks"),
            ("Modern Software Engineering", "David Farley"),
        )
        res = search_metadata("AI Engineering", books)
        titles = [r["title"] for r in res]
        assert "AI Engineering" in titles
        assert "The Mythical Man-Month: Essays on Software Engineering" not in titles
        assert "Modern Software Engineering" not in titles

    def test_missing_book_reports_gap(self):
        books = self._lib(
            ("Fundamentals of Software Architecture", "Mark Richards"),
            ("Software Architecture: The Hard Parts", "Neal Ford"),
        )
        # No "Clean Architecture" present -> must be a gap, not 2 false matches.
        assert search_metadata("Clean Architecture", books) == []

    def test_short_overlap_excluded(self):
        books = self._lib(
            ("Infrastructure as Code", "Kief Morris"),
            ("Code", "Charles Petzold"),
        )
        titles = [r["title"] for r in search_metadata("Infrastructure Code", books)]
        assert "Infrastructure as Code" in titles
        assert "Code" not in titles

    def test_fuzzy_does_not_collide_similar_words(self):
        books = self._lib(("Recording Unhinged", "Sylvia Massy"))
        assert search_metadata("Refactoring", books) == []

    def test_generic_only_query_is_weak(self):
        books = self._lib(("Fundamentals of Software Architecture", "Mark Richards"))
        res = search_metadata("Software Architecture", books)
        assert res and all(r["match_strength"] == "weak" for r in res)

    def test_results_ranked_strong_first_by_score(self):
        books = self._lib(
            ("Refactoring Databases", "Scott Ambler"),
            ("Refactoring", "Martin Fowler"),
        )
        res = search_metadata("Refactoring", books)
        assert res[0]["title"] == "Refactoring"          # exact title outranks superset
        assert res[0]["relevance_score"] >= res[1]["relevance_score"]

    def test_result_has_strength_fields(self):
        books = self._lib(("Team Topologies", "Matthew Skelton"))
        r = search_metadata("Team Topologies", books)[0]
        assert r["match_strength"] == "strong"
        assert 0.0 <= r["relevance_score"] <= 1.0
        assert "title" in r["matched_on"]


class TestSearchTopicPhrase:
    """Tests for phrase mode, boilerplate filtering, and weak-match signalling."""

    def _books(self):
        from books import BookMetadata
        return {"/b.epub": BookMetadata(title="Book", author="Auth", path="/b.epub")}

    def _loader(self, chapters):
        return lambda book: chapters

    def test_phrase_finds_substring_fts_misses(self):
        books = self._books()
        loader = self._loader([("Chapter 1", "He studied antidisestablishmentarianism for years.")])

        ranked = search_topic("disestablish", books, index_path=":memory:",
                              chapter_loader=loader, phrase=False)
        phrased = search_topic("disestablish", books, index_path=":memory:",
                               chapter_loader=loader, phrase=True)

        assert ranked["total_results"] == 0          # not a token, FTS misses it
        assert phrased["total_results"] == 1         # substring match succeeds
        assert phrased["phrase"] is True
        assert phrased["results"][0]["relevance_score"] == 1.0

    def test_boilerplate_locations_excluded(self):
        books = self._books()
        loader = self._loader([
            ("Cover Page", "all about testing here"),
            ("Index", "testing 12, 44"),
            ("Chapter 1", "real prose about testing"),
        ])
        res = search_topic("testing", books, index_path=":memory:", chapter_loader=loader)
        locations = {r["location"] for r in res["results"]}
        assert locations == {"Chapter 1"}

    def test_context_reconstructed_from_neighbours(self):
        books = self._books()
        loader = self._loader([(
            "Chapter 1",
            "First paragraph here.\n\n"
            "The match is in this middle paragraph.\n\n"
            "Third paragraph here.",
        )])
        res = search_topic("middle", books, index_path=":memory:", chapter_loader=loader)
        assert res["total_results"] == 1
        hit = res["results"][0]
        assert "First paragraph" in hit["context_before"]
        assert "Third paragraph" in hit["context_after"]

    def test_context_empty_at_chapter_boundaries(self):
        books = self._books()
        loader = self._loader([
            ("Chapter 1", "Only paragraph of chapter one with token alpha."),
            ("Chapter 2", "Only paragraph of chapter two with token alpha."),
        ])
        res = search_topic("alpha", books, index_path=":memory:", chapter_loader=loader)
        # Each match is alone in its chapter, so no cross-chapter context bleeds in.
        for hit in res["results"]:
            assert hit["context_before"] == ""
            assert hit["context_after"] == ""

    def test_low_confidence_flag_present_and_bool(self):
        books = self._books()
        loader = self._loader([("Chapter 1", "real prose about testing frameworks")])
        res = search_topic("testing", books, index_path=":memory:", chapter_loader=loader)
        assert isinstance(res["low_confidence"], bool)
        # Exact phrase hits are never flagged low-confidence.
        phr = search_topic("real prose", books, index_path=":memory:",
                           chapter_loader=loader, phrase=True)
        assert phr["low_confidence"] is False


class TestSuggestCitation:
    """Inverse search: concept in, ranked citable sources out."""

    def _books(self):
        from books import BookMetadata
        return {"/b.epub": BookMetadata(title="Flow", author="Reinertsen", path="/b.epub")}

    def test_aggregates_and_attributes(self):
        books = self._books()
        loader = lambda b: [("Ch1", "The cost of delay is central.\n\n"
                                    "Managing the cost of delay drives decisions.")]
        res = suggest_citation("cost of delay", books, index_path=":memory:", chapter_loader=loader)
        assert res["sources"]
        top = res["sources"][0]
        assert top["book_title"] == "Flow" and top["author"] == "Reinertsen"
        assert top["hits"] >= 1 and top["passage"]

    def test_no_source_is_reported_not_faked(self):
        books = self._books()
        loader = lambda b: [("Ch1", "An unrelated paragraph about gardening tools.")]
        res = suggest_citation("monadic parser combinators", books,
                               index_path=":memory:", chapter_loader=loader)
        assert res["sources"] == []
        assert res["no_strong_source"] is True


class TestAuditCitations:
    """Citation list -> per-entry status."""

    def _lib(self, *items):
        from books import BookMetadata
        return {
            f"/{i}.epub": BookMetadata(title=t, author=a, published="2020",
                                       path=f"/{i}.epub", text=txt)
            for i, (t, a, txt) in enumerate(items)
        }

    def test_all_four_statuses(self):
        books = self._lib(
            ("Infrastructure as Code", "Kief Morris", "x" * 1000),
            ("Scanned Facsimile", "Anon", "tiny"),
            ("Fundamentals of Software Architecture", "Mark Richards", "y" * 1000),
        )
        res = audit_citations([
            "Infrastructure as Code — Kief Morris",      # PRESENT
            "Scanned Facsimile — Anon",                   # NO-TEXT
            "Clean Architecture — Robert C. Martin",      # MISSING
            "Software Architecture",                       # WEAK-MATCH (generic only)
        ], books)
        status = {r["entry"]: r["status"] for r in res}
        assert status["Infrastructure as Code — Kief Morris"] == "PRESENT"
        assert status["Scanned Facsimile — Anon"] == "NO-TEXT"
        assert status["Clean Architecture — Robert C. Martin"] == "MISSING"
        assert status["Software Architecture"] == "WEAK-MATCH"

    def test_wrong_author_is_not_present(self):
        books = self._lib(("Refactoring", "Martin Fowler", "z" * 1000))
        res = audit_citations(["Refactoring — Some Other Person"], books)
        assert res[0]["status"] == "WEAK-MATCH"


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
        """Test searching with special FTS characters."""
        results = search_topic('foo"bar', mock_books)
        # Should not crash on special characters
        assert isinstance(results, dict)
