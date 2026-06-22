"""Tests for metadata cache freshness (signature is authoritative)."""

import json
import os
import time
from pathlib import Path

import pytest

import books


@pytest.fixture
def library(tmp_path, monkeypatch):
    """A temp library dir plus a redirected metadata cache file."""
    lib = tmp_path / "lib"
    lib.mkdir()
    cache_file = tmp_path / "metadata.json"
    monkeypatch.setattr(books, "_metadata_cache_path", lambda: cache_file)
    return lib, cache_file


def _write_matching_cache(lib, cache_file, titles_to_paths):
    """Write a cache whose signature matches the current files in ``lib``."""
    discovered = books._discover_book_paths([Path(str(lib))])
    signature = books._library_signature_from_paths(discovered, [str(lib)])
    cache_file.write_text(json.dumps({
        "roots": [str(lib)],
        "signature": signature,
        "books": [
            {"title": t, "author": None, "published": None, "path": p, "toc": []}
            for t, p in titles_to_paths.items()
        ],
    }))


def test_cache_used_when_unchanged(library):
    lib, cache_file = library
    (lib / "a.epub").write_bytes(b"x")
    _write_matching_cache(lib, cache_file, {"A": str(lib / "a.epub")})

    loaded, from_cache = books.load_cached_books([str(lib)])
    assert from_cache is True
    assert {b.title for b in loaded.values()} == {"A"}


def test_cache_stale_when_file_added(library):
    lib, cache_file = library
    (lib / "a.epub").write_bytes(b"x")
    _write_matching_cache(lib, cache_file, {"A": str(lib / "a.epub")})

    (lib / "b.epub").write_bytes(b"y")  # new book the cache doesn't know about
    loaded, from_cache = books.load_cached_books([str(lib)])
    assert from_cache is False
    assert loaded == {}


def test_cache_stale_when_file_removed(library):
    lib, cache_file = library
    (lib / "a.epub").write_bytes(b"x")
    (lib / "b.epub").write_bytes(b"y")
    _write_matching_cache(
        lib, cache_file,
        {"A": str(lib / "a.epub"), "B": str(lib / "b.epub")},
    )

    (lib / "b.epub").unlink()
    loaded, from_cache = books.load_cached_books([str(lib)])
    assert from_cache is False
    assert loaded == {}


def test_cache_stale_when_file_modified(library):
    lib, cache_file = library
    book = lib / "a.epub"
    book.write_bytes(b"x")
    _write_matching_cache(lib, cache_file, {"A": str(book)})

    # Change size and mtime
    book.write_bytes(b"xxxxxxxx")
    os.utime(book, (time.time() + 10, time.time() + 10))
    loaded, from_cache = books.load_cached_books([str(lib)])
    assert from_cache is False
    assert loaded == {}


def test_cache_stale_when_root_changes(library, tmp_path):
    lib, cache_file = library
    (lib / "a.epub").write_bytes(b"x")
    _write_matching_cache(lib, cache_file, {"A": str(lib / "a.epub")})

    other = tmp_path / "other"
    other.mkdir()
    loaded, from_cache = books.load_cached_books([str(other)])
    assert from_cache is False
    assert loaded == {}
