"""Tests for the command-line interface."""

import json
import os

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


def test_topic_phrase_mode(patched_library, capsys):
    rc = cli.main(["--json", "topic", "quality assurance", "--phrase"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert data["phrase"] is True
    assert data["total_results"] >= 1
    assert all(r["relevance_score"] == 1.0 for r in data["results"])


def test_suggest_finds_source(patched_library, capsys):
    rc = cli.main(["--json", "suggest", "deployment"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert "Another Book" in [s["book_title"] for s in data["sources"]]


def test_suggest_reports_no_source(patched_library, capsys):
    rc = cli.main(["--json", "suggest", "quantum chromodynamics lagrangian"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert data["sources"] == []
    assert data["no_strong_source"] is True


def test_doctor_reports_no_text_layer(patched_library, monkeypatch, capsys):
    # "Another Book" gets plenty of text; "Test Book" gets almost none.
    def fake_text(path):
        return "x" * 1000 if path.endswith("another.epub") else "tiny"

    monkeypatch.setattr(cli, "parse_epub_text", fake_text)
    rc = cli.main(["--json", "doctor"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    flagged = {b["title"]: b["issues"] for b in data["books"]}
    assert "Test Book" in flagged
    assert "no text layer" in flagged["Test Book"]
    assert "Another Book" not in flagged


def test_paths_before_subcommand_not_swallowed():
    parser = cli.build_parser()
    args = parser.parse_args(["--paths", "/lib", "search", "foo"])
    assert args.command == "search"
    assert args.query == "foo"
    assert cli._resolve_paths(args.paths) == ["/lib"]


def test_paths_repeatable_and_pathsep_split():
    parser = cli.build_parser()
    args = parser.parse_args(
        ["--paths", "/a", "--paths", f"/b{os.pathsep}/c", "list"]
    )
    assert cli._resolve_paths(args.paths) == ["/a", "/b", "/c"]


def test_paths_flag_end_to_end(monkeypatch, mock_books, capsys):
    seen = {}

    def fake_get_books(paths):
        seen["paths"] = paths
        return mock_books, False

    monkeypatch.setattr(cli, "get_books", fake_get_books)
    monkeypatch.delenv("EPUBLIC_LIBRARY_PATHS", raising=False)
    rc = cli.main(["--paths", "/my/lib", "search", "Test"])
    assert rc == 0
    assert seen["paths"] == ["/my/lib"]


def _audit_lib(monkeypatch):
    from books import BookMetadata
    lib = {"/a.epub": BookMetadata(title="Infrastructure as Code", author="Kief Morris",
                                   published="2016", path="/a.epub", text="x" * 1000)}
    monkeypatch.setattr(cli, "get_books", lambda paths: (lib, False))
    monkeypatch.setattr(cli, "parse_epub_text", lambda p: "")
    monkeypatch.setenv("EPUBLIC_LIBRARY_PATHS", "/fake")


def test_audit_exit_nonzero_on_gap(monkeypatch, tmp_path, capsys):
    _audit_lib(monkeypatch)
    f = tmp_path / "cites.txt"
    f.write_text("Infrastructure as Code — Kief Morris\n"
                 "Clean Architecture — Robert C. Martin\n")
    rc = cli.main(["audit", str(f)])
    out = capsys.readouterr().out
    assert "PRESENT" in out and "MISSING" in out
    assert rc == 1


def test_audit_exit_zero_when_all_present(monkeypatch, tmp_path):
    _audit_lib(monkeypatch)
    f = tmp_path / "cites.txt"
    f.write_text("# a comment\nInfrastructure as Code — Kief Morris\n")
    assert cli.main(["audit", str(f)]) == 0


def test_missing_paths_errors(monkeypatch):
    monkeypatch.delenv("EPUBLIC_LIBRARY_PATHS", raising=False)
    with pytest.raises(SystemExit):
        cli.main(["list"])


def test_limit_out_of_range_errors(patched_library):
    with pytest.raises(SystemExit):
        cli.main(["list", "--limit", "99999"])
