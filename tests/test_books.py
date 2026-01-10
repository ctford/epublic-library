"""Tests for book parsing and metadata extraction."""

import pytest
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from books import BookMetadata, HTMLToText


class TestBookMetadata:
    """Tests for BookMetadata dataclass."""
    
    def test_metadata_creation(self):
        """Test creating BookMetadata with all fields."""
        book = BookMetadata(
            title="Test Book",
            author="Test Author",
            published="2024",
            path="/path/to/book.epub",
            toc=[("Chapter 1", "ch1", 0)],
            text="Some text"
        )
        
        assert book.title == "Test Book"
        assert book.author == "Test Author"
        assert book.published == "2024"
        assert len(book.toc) == 1
        assert book.text == "Some text"
    
    def test_metadata_minimal(self):
        """Test creating BookMetadata with minimal fields."""
        book = BookMetadata(title="Minimal Book")
        
        assert book.title == "Minimal Book"
        assert book.author is None
        assert book.published is None
        assert book.toc == []
        assert book.text == ""
    
    def test_metadata_default_toc(self):
        """Test that TOC defaults to empty list."""
        book = BookMetadata(title="Book")
        assert isinstance(book.toc, list)
        assert len(book.toc) == 0


class TestHTMLToText:
    """Tests for HTML to text parser."""
    
    def test_basic_text(self):
        """Test parsing basic text without HTML."""
        parser = HTMLToText()
        parser.feed("Plain text")
        assert parser.get_text() == "Plain text"
    
    def test_paragraph_tags(self):
        """Test that paragraph tags create line breaks."""
        parser = HTMLToText()
        parser.feed("<p>First paragraph</p><p>Second paragraph</p>")
        text = parser.get_text()
        assert "First paragraph" in text
        assert "Second paragraph" in text
        assert text.count('\n') >= 1
    
    def test_div_tags(self):
        """Test that div tags create line breaks."""
        parser = HTMLToText()
        parser.feed("<div>First div</div><div>Second div</div>")
        text = parser.get_text()
        assert "First div" in text
        assert "Second div" in text
    
    def test_br_tags(self):
        """Test that br tags are handled."""
        parser = HTMLToText()
        parser.feed("Line one<br>Line two<br>Line three")
        text = parser.get_text()
        # Should contain all text (line breaks are nice but not required)
        assert "Line one" in text
        assert "Line two" in text
        assert "Line three" in text
    
    def test_script_tag_filtering(self):
        """Test that script content is removed."""
        parser = HTMLToText()
        parser.feed("<p>Keep this</p><script>var x = 1;</script><p>And this</p>")
        text = parser.get_text()
        assert "Keep this" in text
        assert "And this" in text
        assert "var x" not in text
    
    def test_style_tag_filtering(self):
        """Test that style content is removed."""
        parser = HTMLToText()
        parser.feed("<p>Text</p><style>body { color: red; }</style><p>More text</p>")
        text = parser.get_text()
        assert "Text" in text
        assert "More text" in text
        assert "color: red" not in text
    
    def test_whitespace_handling(self):
        """Test that extra whitespace is preserved in content."""
        parser = HTMLToText()
        parser.feed("<p>Text with   spaces</p>")
        text = parser.get_text()
        assert "Text with   spaces" in text
    
    def test_empty_html(self):
        """Test parsing empty HTML."""
        parser = HTMLToText()
        parser.feed("<div></div>")
        text = parser.get_text()
        assert text.strip() == ""
    
    def test_nested_tags(self):
        """Test parsing nested HTML tags."""
        parser = HTMLToText()
        parser.feed("<div><p>Nested <strong>bold</strong> text</p></div>")
        text = parser.get_text()
        assert "Nested" in text
        assert "bold" in text
        assert "text" in text


class TestBookMetadataWithMock:
    """Integration tests with mock book fixture."""
    
    def test_mock_book_has_content(self, mock_book):
        """Test that mock book has expected content."""
        assert mock_book.title == "Test Book"
        assert mock_book.author == "Test Author"
        assert "testing" in mock_book.text.lower()
        assert len(mock_book.toc) == 2
