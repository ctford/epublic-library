# ePublic Library

> This is a vibe-coded personal project; any usefulness to others is welcome but coincidental.

[![tests](https://github.com/ctford/epublic-library/actions/workflows/tests.yml/badge.svg)](https://github.com/ctford/epublic-library/actions/workflows/tests.yml)

Makes your EPUB book library searchable from Claude Code and Claude Desktop (via MCP) and from the shell (via the `epublic` command).

## Features

- **Metadata Search**: Find books by title, author, or publication year
- **Topic Search**: Find advice and content on specific topics with full attribution (book, author, chapter)
- **Two interfaces**: an MCP server for Claude, and an `epublic` command-line tool that exposes the same searches in a terminal

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
      "args": [
        "/path/to/epublic-library/src/main.py",
        "/path/to/epub-library"
      ]
    }
  }
}
```

### 3. Restart Claude Desktop

Fully quit and reopen Claude Desktop.

## Integration with Claude Code

Add the same configuration to `~/.claude/config.json` (create the file if it does not exist).

## Where Books Come From

On startup, the server scans the library paths passed in the Claude Desktop config.
You can pass multiple paths by adding more items to the `args` array.
Alternatively, set `EPUBLIC_LIBRARY_PATHS` (a path list separated by your OS path separator).

## Command Line (`epublic`)

Installing the package also installs the `epublic` command, which exposes the
same searches from a terminal. It reads the library location from
`EPUBLIC_LIBRARY_PATHS` (or a `--paths` option) and shares the same on-disk
metadata cache and FTS index as the MCP server.

```bash
export EPUBLIC_LIBRARY_PATHS="/path/to/epub-library"

# List books (optionally with author/year)
epublic list --limit 25 --author --published

# Search metadata by title, author, or year
epublic search "Kief Morris"

# Find passages on a topic, with attribution
epublic topic "effective teams" --author "Marty Cagan" --limit 5

# OR across several topics
epublic topic testing "quality assurance" TDD --limit 15

# Verify a verbatim quote (exact substring)
epublic topic "free of time and place" --phrase

# Suggest a citable source for a concept (inverse search)
epublic suggest "cost of delay" --limit 3

# Report library health (missing metadata / no text layer)
epublic doctor

# Audit a citation list (one "Title — Author" per line); exits non-zero on gaps
epublic audit key-texts.md

# Raw JSON for scripting
epublic --json search "Infrastructure as Code"
```

`audit` reads a file (or stdin with `-`) and classifies each entry as `PRESENT`,
`NO-TEXT`, `WEAK-MATCH`, or `MISSING`, exiting non-zero if anything isn't solidly
present — so it can gate CI over a `key-texts.md`.

`search` ranks results strongest-first and marks `[weak]` matches (those resting
only on a generic shared word like "Architecture"); **an empty result is a real
gap**, not a tool failure. `suggest` says so explicitly when nothing covers a
concept, rather than returning a weak match.

Run `epublic --help` (or `epublic <command> --help`) for the full option list.
If the package's `venv` is not on your `PATH`, call it by full path, e.g.
`/path/to/epublic-library/venv/bin/epublic`.

## Testing

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

See `TESTING.md` for the full testing guide.

## Tools (MCP)

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

Returns book metadata including author, publication year, and chapter list. Each
result carries a `match_strength` of `strong` or `weak` (weak = matched only on a
generic shared word) and a `relevance_score`; results are ranked strongest-first.

**Note**: An empty result is a real gap — the library does not contain that book,
so don't assume coverage. Fuzzy matching (typo tolerance) is enabled by default
if `fuzzywuzzy` is installed, but matching is coverage-based, so a single shared
generic word ("Engineering", "Architecture") no longer counts as a match. Years
always require exact matches.

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

**Verbatim quote check (citation verification):**
```
find_topic(topic="free of time and place", phrase=true)
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

### `suggest_source`
Inverse of search: given a concept, return library books that best cover it,
ranked, each with a supporting passage and attribution.

**Example:**
```
suggest_source(concept="cost of delay", limit=3)
```

Returns `concept`, a ranked `sources` array (`book_title`, `author`,
`best_score`, `hits`, `passage`, `location`), and `no_strong_source: true` when
nothing in the library covers the concept well.

### `doctor`
Report library health: books with missing `title`/`author`/`date` or no usable
text layer (image-only scans that can't be searched). Scans every book's text,
so it may be slow on a large library.

```
doctor()
```

### `audit_citations`
Check a list of citations against the library. Each entry (`Title — Author` or a
plain title) is classified `PRESENT`, `NO-TEXT`, `WEAK-MATCH`, or `MISSING`.

**Example:**
```
audit_citations(entries=["Team Topologies — Matthew Skelton", "Clean Architecture — Robert C. Martin"])
```

Returns a `results` array (one per entry, with `status`, `matched_title`,
`matched_author`) and a `summary` count by status. (The CLI equivalent,
`epublic audit`, adds file/stdin input and a non-zero exit code for CI.)

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
