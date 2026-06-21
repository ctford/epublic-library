"""Tests for the command-line interface."""

import json

import pytest

import cli


@pytest.fixture
def patched_library(monkeypatch, mock_books):
    """Make the CLI load a fixed set of mock books."""
    by_path = {b.path: b for b in mock_books.values()}
    monkeypatch.setattr(cli, "get_books", lambda paths: (mock_books, False))
    monkeypatch.setattr(
        cli, "parse_epub_chapters",
        lambda path: [("Chapter 1", by_path[path].text)],
    )
    monkeypatch.setenv("EPUBLIC_LIBRARY_PATHS", "/fake/library")


def test_list_human_readable(patched_library, capsys):
    rc = cli.main(["list"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "2 book(s) in library" in out
    assert "Test Book" in out
    assert "Another Book" in out


def test_list_json_with_fields(patched_library, capsys):
    rc = cli.main(["--json", "list", "--author", "--published"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert data["total"] == 2
    assert all("author" in b and "published" in b for b in data["books"])


def test_search_metadata(patched_library, capsys):
    rc = cli.main(["search", "Different Author"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Another Book" in out


def test_topic_finds_passage(patched_library, capsys):
    rc = cli.main(["topic", "testing"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "passage(s) for 'testing'" in out


def test_topic_multiple_is_or(patched_library, capsys):
    rc = cli.main(["--json", "topic", "deployment", "testing"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert data["total_results"] >= 1


def test_missing_paths_errors(monkeypatch):
    monkeypatch.delenv("EPUBLIC_LIBRARY_PATHS", raising=False)
    with pytest.raises(SystemExit):
        cli.main(["list"])


def test_limit_out_of_range_errors(patched_library):
    with pytest.raises(SystemExit):
        cli.main(["list", "--limit", "99999"])
