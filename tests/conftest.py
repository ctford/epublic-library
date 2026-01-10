"""Pytest configuration and fixtures."""

import pytest
from pathlib import Path
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))


@pytest.fixture
def mock_book():
    """Create a mock book for testing."""
    from books import BookMetadata
    
    return BookMetadata(
        title="Test Book",
        author="Test Author",
        published="2024",
        path="/path/to/test.epub",
        toc=[("Chapter 1", "ch1", 0), ("Chapter 2", "ch2", 0)],
        text="""
        This is a test book with some content.
        It contains multiple paragraphs about testing.
        Testing is important for quality assurance.
        We should always test our code thoroughly.
        Another paragraph about testing frameworks.
        """
    )


@pytest.fixture
def mock_books(mock_book):
    """Create multiple mock books for testing."""
    from books import BookMetadata
    
    book2 = BookMetadata(
        title="Another Book",
        author="Different Author",
        published="2023",
        path="/path/to/another.epub",
        toc=[("Intro", "intro", 0), ("Main", "main", 0)],
        text="""
        This book is about deployment strategies.
        Continuous deployment is important.
        We use testing frameworks for validation.
        """
    )
    
    return {
        "Test Book": mock_book,
        "Another Book": book2
    }
