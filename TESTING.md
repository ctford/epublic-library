# Testing Guide

## Overview

This project includes a comprehensive test suite using pytest. Tests cover:

- HTML parsing and text extraction
- Book metadata handling
- Metadata search functionality
- Topic search functionality
- Integration tests

## Setup

### Install Test Dependencies

```bash
cd /path/to/epublic-library
pip install -e ".[dev]"
```

This installs the project and pytest.

## Running Tests

### Run All Tests

```bash
pytest tests/ -v
```

### Run Specific Test File

```bash
pytest tests/test_books.py -v
pytest tests/test_search.py -v
```

### Run Specific Test Class

```bash
pytest tests/test_books.py::TestHTMLToText -v
```

### Run Specific Test

```bash
pytest tests/test_books.py::TestHTMLToText::test_paragraph_tags -v
```

### Show Print Output

```bash
pytest tests/ -v -s
```

### Run with Coverage Report

```bash
pytest tests/ --cov=src --cov-report=html
# Open htmlcov/index.html to view detailed report
```

## Test Structure

### `tests/conftest.py`

Contains pytest fixtures used across test files:

- `mock_book`: A single test BookMetadata instance with sample content
- `mock_books`: Dictionary of multiple BookMetadata instances

These fixtures provide realistic test data without needing actual EPUB files.

### `tests/test_books.py`

Tests for `src/books.py`:

**TestBookMetadata**
- Dataclass creation with all fields
- Minimal field creation
- Default TOC initialization

**TestHTMLToText**
- Basic text parsing
- Paragraph/div/br tag handling
- Script/style tag filtering
- Whitespace handling
- Nested tag handling
- Empty HTML

**TestBookMetadataWithMock**
- Integration with mock fixtures

### `tests/test_search.py`

Tests for `src/search.py`:

**TestSearchMetadata**
- Title search (exact and partial)
- Author search
- Year search
- Case-insensitive matching
- Multiple matches
- No matches
- Result structure validation
- Chapter list inclusion

**TestSearchTopic**
- Topic word match
- Case-insensitive matching
- Word boundary respect
- Result structure
- Context extraction
- Result limiting
- Empty text handling

**TestSearchIntegration**
- Combined metadata and topic search
- Special character handling

## Test Statistics

- **Total Tests**: ~40
- **Lines of Test Code**: ~350
- **Coverage**: Core business logic (books and search modules)

## Fixtures

All test data is created through fixtures in `tests/conftest.py`. This approach:

- Avoids dependency on real EPUB files
- Makes tests fast and reliable
- Provides consistent test data
- Easy to extend with new fixtures

## Git Pre-Commit Hook

Tests can be automatically run before commits using a git hook.

### Install the Hook

```bash
bash scripts/install-hooks.sh
```

This creates `.git/hooks/pre-commit` which runs all tests before allowing a commit.

### Bypass the Hook (if needed)

```bash
git commit --no-verify
```

## Adding New Tests

### Test File Naming

- All test files go in `tests/`
- Test files start with `test_` (e.g., `test_main.py`)
- Test functions start with `test_` (e.g., `test_basic_parsing()`)

### Test Class Naming

```python
class TestFeatureName:
    """Tests for specific feature."""
    
    def test_something(self):
        assert True
```

### Using Fixtures

```python
def test_with_fixture(mock_book):
    assert mock_book.title == "Test Book"
```

### Adding Mock Data

Edit `tests/conftest.py` to add new fixtures:

```python
@pytest.fixture
def mock_special_book():
    return BookMetadata(...)
```

## Common Testing Patterns

### Testing Exceptions

```python
def test_error_handling():
    with pytest.raises(ValueError):
        function_that_raises()
```

### Testing with Multiple Inputs

```python
@pytest.mark.parametrize("input,expected", [
    ("test", "TEST"),
    ("hello", "HELLO"),
])
def test_multiple_inputs(input, expected):
    assert convert(input) == expected
```

## Troubleshooting

### Import Errors

Ensure pytest can find the `src` module:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
```

### Tests Not Running

Check that test files are in `tests/` and start with `test_`:

```bash
pytest --collect-only  # Shows what pytest would run
```

### Fixture Not Found

Ensure the fixture is defined in `tests/conftest.py` or in the test file itself.
