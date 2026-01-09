# Kindle MCP Server - Implementation Status

## ✅ COMPLETED

## Goals
1. **Metadata Research**: Query book metadata (author, publication year, title)
2. **Topic Search**: Find advice/content on specific topics with full attribution (book, section, page)

## Architecture

### Python MCP Server
- Entry point: `src/main.py`
- Runs continuously, listens for MCP requests

### Core Modules

#### `books.py`
- Scan `~/Library/Application Support/Amazon/Kindle/` for MOBI, AZW3, EPUB
- Parse each book to extract:
  - Metadata (title, author, publication date)
  - Table of Contents (chapter/section hierarchy)
  - Full text with page/section markers
- Cache parsed data in memory

#### `search.py`
- Search TOC for topic/chapter matches
- Search full text for topic mentions with context
- Return results with attribution (book, chapter, page number, exact quote)

### MCP Tools

1. **`search_books`** (string: query)
   - Search metadata + TOC
   - Return: List of matching books with author, year, relevant chapters

2. **`find_topic`** (string: topic, optional: book filter)
   - Full-text search for topic
   - Return: Passages with attribution (book, chapter, page, quote, author)

### Data Flow

```
Kindle Books
    ↓
Parse (on startup)
    ↓
In-memory cache (metadata + TOC + full text)
    ↓
MCP Tools
    ↓
Claude
```

## Implementation Steps

1. **Setup** - Create project structure, dependencies (ebooklib, python-mcp)
2. **Book Parsing** - Extract metadata, TOC, text from MOBI/AZW3/EPUB
3. **Metadata Cache** - Store parsed books in memory with attribution
4. **Search Implementation** - TOC search + full-text search
5. **MCP Integration** - Expose tools via MCP protocol
6. **Testing** - Query against real Kindle library

## Dependencies
- `ebooklib` - Parse EPUB/MOBI/AZW3
- `mcp` - Python MCP SDK
- `python-dotenv` - Config

## Notes
- Page numbers may not be available in all formats; use section/chapter + context
- Attribution requires preserving book/author metadata throughout pipeline
- Full text search may be slow on large libraries; consider caching results
