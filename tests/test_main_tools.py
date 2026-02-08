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
