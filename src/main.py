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
            description="Find advice or content on a specific topic with full attribution",
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
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (default 10)"
                    }
                },
                "required": ["topic"]
            }
        )
    ]


async def handle_call_tool(name: str, arguments: dict) -> str:
    """Handle tool calls."""
    global books_cache
    
    if not books_cache:
        return json.dumps({"error": "Books not loaded yet"})
    
    try:
        if name == "search_books":
            query = arguments.get("query", "")
            results = search_metadata(query, books_cache)
            return json.dumps(results, indent=2)
        
        elif name == "find_topic":
            topic = arguments.get("topic", "")
            book_filter = arguments.get("book_filter")
            limit = arguments.get("limit", 10)
            results = search_topic(topic, books_cache, limit, book_filter=book_filter)
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
