# Quick Start

## 1. Verify Installation

```bash
cd /path/to/epublic-library
source venv/bin/activate
python3 test_books.py
```

Expected output: Shows parsed books and search results.

## 2. Configure Claude Desktop

```bash
# Edit the config file
open ~/Library/Application\ Support/Claude/claude_desktop_config.json

# Add this to mcpServers section:
{
  "epublic": {
    "command": "/path/to/epublic-library/venv/bin/python3",
    "args": ["/path/to/epublic-library/src/main.py"]
  }
}
```

## 3. Restart Claude Desktop

Fully close and reopen Claude Desktop.

## 4. Use in Claude

In Claude, you'll now have access to:

- `search_books(query="...")` - Find books by title/author/year
- `find_topic(topic="...")` - Find passages about a topic

## Example Queries

**Research a book:**
```
search_books(query="David MacKay")
```

**Find advice on a topic:**
```
find_topic(topic="entropy and information", limit=5)
```

## Adding Books

Place EPUB files in:
```
~/Library/Application Support/Amazon/Kindle/
```

Or for testing:
```
~/Sync/
```

Restart the MCP server to load new books.

## Docs

- **CLAUDE_DESKTOP_SETUP.md** - Detailed setup with troubleshooting
- **IMPLEMENTATION_SUMMARY.md** - Technical details and design decisions
- **PLAN.md** - Original architecture and plan
