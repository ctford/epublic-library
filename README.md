# ePublic Library

An MCP server that makes your EPUB book library searchable from Claude Code and Claude Desktop.

## Features

- **Metadata Search**: Find books by title, author, or publication year
- **Topic Search**: Find advice and content on specific topics with full attribution (book, author, chapter)

## Setup

```bash
cd /path/to/epublic-library
pip install -e .
```

## Testing

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

See [TESTING.md](TESTING.md) for comprehensive testing guide.

## Running the Server

```bash
python src/main.py
```

## Integration with Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "epublic": {
      "command": "/path/to/epublic-library/venv/bin/python3",
      "args": ["/path/to/epublic-library/src/main.py", "/path/to/your/epub/books"]
    }
  }
}
```

Replace `/path/to/your/epub/books` with the directory containing your EPUB files.

## Integration with Claude Code

Add to `~/.claude/config.json`:

```json
{
  "mcpServers": {
    "epublic": {
      "command": "/path/to/epublic-library/venv/bin/python3",
      "args": ["/path/to/epublic-library/src/main.py", "/path/to/your/epub/books"]
    }
  }
}
```

If `~/.claude/config.json` doesn't exist, create it with the above configuration.

Replace `/path/to/your/epub/books` with the directory containing your EPUB files.

## Tools

### `search_books`
Search book metadata by title, author, or publication year.

**Example:**
```
search_books(query="Continuous Deployment")
```

Returns book metadata including author, publication year, and chapter list.

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
