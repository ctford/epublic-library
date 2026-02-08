# ePublic Library

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
find_topic(topic="effective teams")
```

Returns passages with full attribution:
- Book title
- Author
- Chapter/section
- Exact quote with context

## Implementation Notes

- Books are parsed from the directory specified in Claude Desktop config
- Currently supports EPUB format
- Full text is stored in memory for fast searching
- Search is case-insensitive
- Results include surrounding context for better understanding

## Troubleshooting

- Tools not appearing: verify the `command` path in the config and restart Claude Desktop.
- Book parsing errors: only EPUB is supported; ensure files are in the scan paths.
- Slow startup: large libraries are parsed on startup and cached in memory.
