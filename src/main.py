"""MCP server for EPUB books."""

import asyncio
import json
from typing import Any
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import ServerCapabilities, Tool, TextContent, ToolsCapability
import logging

from books import get_books
from search import search_metadata, search_topic

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global book cache
books_cache = None


async def load_books():
    """Load books on startup."""
    global books_cache
    logger.info("Loading EPUB library...")
    books_cache = get_books()
    logger.info(f"Loaded {len(books_cache)} books")


def get_tools() -> list[Tool]:
    """Define available MCP tools."""
    return [
        Tool(
            name="list_books",
            description="List available books with optional pagination",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of books to return (default 50)"
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Number of books to skip before returning results (default 0)"
                    },
                    "include_fields": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional fields to include: author, published, path"
                    }
                }
            }
        ),
        Tool(
            name="search_books",
            description="Search book metadata by title, author, or publication year",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (title, author name, or year)"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="find_topic",
            description="Find advice or content on a specific topic with full attribution (filters can be combined)",
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Topic to search for"
                    },
                    "book_filter": {
                        "type": "string",
                        "description": "Optional: filter to specific book title"
                    },
                    "author_filter": {
                        "type": "string",
                        "description": "Optional: filter to specific author"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (default 10)"
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Number of results to skip before returning matches (default 0)"
                    },
                    "match_type": {
                        "type": "string",
                        "description": "Match strategy for book/author filters: exact or fuzzy (default fuzzy)"
                    },
                    "topics": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of topics; matches any topic (OR logic)"
                    }
                },
                "anyOf": [
                    {"required": ["topic"]},
                    {"required": ["topics"]}
                ]
            }
        )
    ]


async def handle_call_tool(name: str, arguments: dict) -> str:
    """Handle tool calls."""
    global books_cache
    
    if not books_cache:
        return json.dumps({"error": "Books not loaded yet"})
    
    try:
        if name == "list_books":
            limit = arguments.get("limit", 50)
            offset = arguments.get("offset", 0)
            include_fields = set(arguments.get("include_fields") or [])

            if not isinstance(limit, int) or limit < 0:
                return json.dumps({"error": "limit must be a non-negative integer"})
            if not isinstance(offset, int) or offset < 0:
                return json.dumps({"error": "offset must be a non-negative integer"})

            books_list = list(books_cache.values())
            books_list.sort(key=lambda book: book.title.lower())

            sliced = books_list[offset:offset + limit if limit else None]
            results = []
            for book in sliced:
                entry = {"title": book.title}
                if "author" in include_fields:
                    entry["author"] = book.author or "Unknown"
                if "published" in include_fields:
                    entry["published"] = book.published or "Unknown"
                if "path" in include_fields:
                    entry["path"] = book.path
                results.append(entry)

            return json.dumps(
                {
                    "total": len(books_list),
                    "offset": offset,
                    "limit": limit,
                    "books": results,
                },
                indent=2,
            )

        elif name == "search_books":
            query = arguments.get("query", "")
            results = search_metadata(query, books_cache)
            return json.dumps(results, indent=2)
        
        elif name == "find_topic":
            topic = arguments.get("topic", "")
            book_filter = arguments.get("book_filter")
            author_filter = arguments.get("author_filter")
            limit = arguments.get("limit", 10)
            offset = arguments.get("offset", 0)
            match_type = arguments.get("match_type", "fuzzy")
            topics = arguments.get("topics")
            if not topic and not topics:
                return json.dumps({"error": "topic or topics is required"})
            if not isinstance(limit, int) or limit < 0:
                return json.dumps({"error": "limit must be a non-negative integer"})
            if not isinstance(offset, int) or offset < 0:
                return json.dumps({"error": "offset must be a non-negative integer"})
            if match_type not in {"exact", "fuzzy"}:
                return json.dumps({"error": "match_type must be 'exact' or 'fuzzy'"})
            results = search_topic(
                topic if topic else None,
                books_cache,
                limit,
                offset,
                book_filter=book_filter,
                author_filter=author_filter,
                match_type=match_type,
                topics=topics,
            )
            return json.dumps(results, indent=2)
        
        else:
            return json.dumps({"error": f"Unknown tool: {name}"})
    
    except Exception as e:
        logger.error(f"Error handling tool {name}: {e}")
        return json.dumps({"error": str(e)})


async def main():
    """Start the MCP server."""
    # Load books on startup
    await load_books()
    
    # Create MCP server
    server = Server("epublic-library")
    
    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return get_tools()
    
    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        result = await handle_call_tool(name, arguments)
        return [TextContent(type="text", text=result)]
    
    # Run the server over stdio
    logger.info("Kindle MCP server started")
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="epublic-library",
                server_version="0.1.0",
                capabilities=ServerCapabilities(tools=ToolsCapability()),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
