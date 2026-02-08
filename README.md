# ePublic Library

[![tests](https://github.com/ctford/epublic-library/actions/workflows/tests.yml/badge.svg)](https://github.com/ctford/epublic-library/actions/workflows/tests.yml)

An MCP server that makes your EPUB book library searchable from Claude Code and Claude Desktop.

## Features

- **Metadata Search**: Find books by title, author, or publication year
- **Topic Search**: Find advice and content on specific topics with full attribution (book, author, chapter)

## Quick Start

### 1. Install

```bash
cd /path/to/epublic-library
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

Optional fuzzy matching (typo tolerance):

```bash
pip install -e ".[fuzzy]"
```

### 2. Configure Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "epublic": {
      "command": "/path/to/epublic-library/venv/bin/python3",
      "args": ["/path/to/epublic-library/src/main.py"]
    }
  }
}
```

### 3. Restart Claude Desktop

Fully quit and reopen Claude Desktop.

## Integration with Claude Code

Add the same configuration to `~/.claude/config.json` (create the file if it does not exist).

## Where Books Come From

On startup, the server scans these locations:

- `~/Library/Application Support/Amazon/Kindle/`
- `~/Sync/` (useful for testing)

To use a different directory, update `src/books.py` and restart the server.

## Testing

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

See `TESTING.md` for the full testing guide.

## Tools

### `list_books`
List available books with optional pagination.

**Example:**
```
list_books(limit=25, offset=0, include_fields=["author","published"])
```

Returns:
- `total`: total books in library
- `offset` and `limit`: echo of pagination
- `books`: array of book entries (always `title`, optional `author`, `published`, `path`)

### `search_books`
Search book metadata by title, author, or publication year.

**Exact Match Example:**
```
search_books(query="Kief Morris")
```

**Typo Tolerant Example (with fuzzy matching installed):**
```
search_books(query="Keith Morris")  # Finds "Kief Morris"
search_books(query="Infrastructure Code")  # Finds "Infrastructure as Code"
```

Returns book metadata including author, publication year, and chapter list.

**Note**: Fuzzy matching is enabled by default if `fuzzywuzzy` is installed. It matches author names and titles with typos/variations. Years always require exact matches.

### `find_topic`
Find advice or content on a specific topic with attribution.

**Example:**
```
find_topic(topic="effective teams", author_filter="Marty Cagan", limit=5, offset=0)
```

**Combined filters:**
```
find_topic(topic="AI consciousness", author_filter="Martha Wells", book_filter="All Systems Red")
```

**Match type for filters:**
```
find_topic(topic="functional programming", author_filter="Hickey", match_type="fuzzy")
```

**Multiple topics (OR):**
```
find_topic(topics=["testing", "quality assurance", "TDD"], limit=15)
```

Returns:
- `total_results` with pagination metadata
- `results` array of passages with full attribution

Each result includes:
- `text` (paragraph containing the match)
- `book_title`
- `author`
- `location` (chapter/section when available)
- `context_before` / `context_after`
- `relevance_score` (0.0–1.0)

## Implementation Notes

- Books are parsed from the directory specified in Claude Desktop config
- Currently supports EPUB format
- Full text search is backed by a SQLite FTS index on disk
- Search is case-insensitive
- Results include surrounding context for better understanding

## Performance Notes

- Metadata is cached on disk and reused across restarts.
- Full-text search uses a SQLite FTS index stored on disk.
- By default the index lives in your OS cache directory (e.g. `~/Library/Caches/epublic-library/index.sqlite` on macOS).
- Set `EPUBLIC_INDEX_PATH` to choose a different index location.
- Set `EPUBLIC_REBUILD_INDEX=1` to force a rebuild.

## Troubleshooting

- Tools not appearing: verify the `command` path in the config and restart Claude Desktop.
- Book parsing errors: only EPUB is supported; ensure files are in the scan paths.
- Slow startup: large libraries are parsed on startup and cached in memory.
