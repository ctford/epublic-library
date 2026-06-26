import json

import pytest

import main
from books import BookMetadata


@pytest.fixture(autouse=True)
def _books_cache():
    original = main.books_cache
    main.books_cache = {
        "Alpha": BookMetadata(title="Alpha", author="A", text="alpha content"),
        "Beta": BookMetadata(title="Beta", author="B", text="beta content"),
    }
    yield
    main.books_cache = original


@pytest.mark.anyio
async def test_search_books_response_shape(monkeypatch):
    def fake_search_metadata(query, books):
        return [{"title": "Alpha"}]

    monkeypatch.setattr(main, "search_metadata", fake_search_metadata)
    payload = await main.handle_call_tool("search_books", {"query": "alpha"})
    data = json.loads(payload)

    assert data["query"] == "alpha"
    assert data["total"] == 1
    assert data["results"] == [{"title": "Alpha"}]


@pytest.mark.anyio
async def test_list_books_rejects_large_limit():
    payload = await main.handle_call_tool("list_books", {"limit": 501})
    data = json.loads(payload)
    assert data["error"] == "limit must be <= 500"


@pytest.mark.anyio
async def test_find_topic_rejects_large_limit():
    payload = await main.handle_call_tool(
        "find_topic",
        {"topic": "testing", "limit": 501},
    )
    data = json.loads(payload)
    assert data["error"] == "limit must be <= 500"


@pytest.mark.anyio
async def test_find_topic_accepts_phrase():
    payload = await main.handle_call_tool(
        "find_topic", {"topic": "alpha", "phrase": True}
    )
    data = json.loads(payload)
    assert data.get("phrase") is True


@pytest.mark.anyio
async def test_suggest_source_tool():
    payload = await main.handle_call_tool("suggest_source", {"concept": "alpha"})
    data = json.loads(payload)
    assert data["concept"] == "alpha"
    assert "sources" in data and "no_strong_source" in data


@pytest.mark.anyio
async def test_doctor_tool():
    payload = await main.handle_call_tool("doctor", {})
    data = json.loads(payload)
    assert "books" in data and "with_issues" in data


@pytest.mark.anyio
async def test_audit_citations_tool():
    payload = await main.handle_call_tool(
        "audit_citations",
        {"entries": ["Alpha — A", "Clean Architecture — Robert C. Martin"]},
    )
    data = json.loads(payload)
    assert "results" in data and "summary" in data
    status = {r["entry"]: r["status"] for r in data["results"]}
    assert status["Clean Architecture — Robert C. Martin"] == "MISSING"


@pytest.mark.anyio
async def test_audit_citations_requires_entries():
    payload = await main.handle_call_tool("audit_citations", {"entries": []})
    assert json.loads(payload)["error"]


def test_mcp_server_has_orientation_instructions():
    """Server-level instructions must orient an agent to every tool."""
    text = main.SERVER_INSTRUCTIONS
    assert text.strip()
    for tool in ("list_books", "search_books", "find_topic",
                 "suggest_source", "audit_citations", "doctor"):
        assert tool in text, f"instructions don't mention {tool}"


def test_mcp_and_cli_expose_same_capabilities():
    """Every shared capability must exist on both the MCP and CLI surfaces."""
    import argparse
    import cli

    mcp_tools = {t.name for t in main.get_tools()}
    sub = [a for a in cli.build_parser()._actions
           if isinstance(a, argparse._SubParsersAction)][0]
    cli_cmds = set(sub.choices)

    # capability -> (cli subcommand, mcp tool name)
    capabilities = {
        "list": ("list", "list_books"),
        "search": ("search", "search_books"),
        "topic": ("topic", "find_topic"),
        "suggest": ("suggest", "suggest_source"),
        "doctor": ("doctor", "doctor"),
        "audit": ("audit", "audit_citations"),
    }
    for cap, (cli_name, mcp_name) in capabilities.items():
        assert cli_name in cli_cmds, f"CLI missing capability: {cap}"
        assert mcp_name in mcp_tools, f"MCP missing capability: {cap}"
