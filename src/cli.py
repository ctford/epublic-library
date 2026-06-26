"""Command-line interface for the ePublic Library.

Exposes the same capabilities as the MCP server (`list`, `search`, `topic`)
for use directly from a shell. Library paths come from the EPUBLIC_LIBRARY_PATHS
environment variable or the --paths option.
"""

import argparse
import json
import logging
import os
import sys

from books import diagnose_book, get_books, parse_epub_chapters, parse_epub_text
from collections import Counter

from search import audit_citations, search_metadata, search_topic, suggest_citation

MAX_LIMIT = 500


def _resolve_paths(cli_paths):
    """Return library paths from --paths, falling back to the env var.

    Each --paths value may itself be an os.pathsep-separated list.
    """
    if cli_paths:
        return [p for entry in cli_paths for p in entry.split(os.pathsep) if p]
    env_paths = os.getenv("EPUBLIC_LIBRARY_PATHS")
    if env_paths:
        return [p for p in env_paths.split(os.pathsep) if p]
    return []


def _load_library(paths):
    books, _ = get_books(paths)
    return books


def _print(data, as_json):
    if as_json:
        print(json.dumps(data, indent=2))
        return False
    return True  # caller should render human-readable output


def cmd_list(args, books):
    books_list = sorted(books.values(), key=lambda b: b.title.lower())
    total = len(books_list)
    sliced = books_list[args.offset:args.offset + args.limit if args.limit else None]

    if args.json:
        results = []
        for book in sliced:
            entry = {"title": book.title}
            if args.author:
                entry["author"] = book.author or "Unknown"
            if args.published:
                entry["published"] = book.published or "Unknown"
            results.append(entry)
        print(json.dumps(
            {"total": total, "offset": args.offset, "limit": args.limit, "books": results},
            indent=2,
        ))
        return

    print(f"{total} book(s) in library; showing {len(sliced)} (offset {args.offset})\n")
    for book in sliced:
        line = book.title
        if args.author:
            line += f" — {book.author or 'Unknown'}"
        if args.published:
            line += f" ({book.published or 'Unknown'})"
        print(line)


def cmd_search(args, books):
    results = search_metadata(args.query, books)
    if args.json:
        print(json.dumps(
            {"query": args.query, "total": len(results), "results": results}, indent=2,
        ))
        return

    if not results:
        print(f"No books matched '{args.query}'.")
        return
    strong = [r for r in results if r.get("match_strength") != "weak"]
    weak = [r for r in results if r.get("match_strength") == "weak"]
    print(f"{len(results)} match(es) for '{args.query}' "
          f"({len(strong)} strong, {len(weak)} weak):\n")
    for r in results:
        title = r.get("title", "Unknown")
        author = r.get("author", "Unknown")
        published = r.get("published", "Unknown")
        mark = "  [weak]" if r.get("match_strength") == "weak" else ""
        print(f"{title} — {author} ({published}){mark}")


def cmd_topic(args, books):
    topics = args.topic
    primary = topics[0] if len(topics) == 1 else None
    multi = topics if len(topics) > 1 else None

    results = search_topic(
        primary,
        books,
        args.limit,
        args.offset,
        book_filter=args.book,
        author_filter=args.author,
        match_type=args.match_type,
        topics=multi,
        phrase=args.phrase,
        chapter_loader=lambda book: parse_epub_chapters(book.path),
    )

    if args.json:
        print(json.dumps(results, indent=2))
        return

    if isinstance(results, dict) and results.get("error"):
        print(f"Error: {results['error']}")
        return

    matches = results.get("results", []) if isinstance(results, dict) else results
    total = results.get("total_results", len(matches)) if isinstance(results, dict) else len(matches)
    label = " / ".join(topics)
    if not matches:
        if args.phrase:
            print(f"No verbatim match for '{label}'.")
        else:
            print(f"No passages found for '{label}'.")
        return
    if results.get("low_confidence"):
        print("Note: all matches are weak — the text may not appear "
              "near-verbatim. Try --phrase for an exact lookup.\n")
    print(f"{total} passage(s) for '{label}'; showing {len(matches)} (offset {args.offset})\n")
    for m in matches:
        book_title = m.get("book_title", "Unknown")
        author = m.get("author", "Unknown")
        location = m.get("location") or "?"
        score = m.get("relevance_score")
        header = f"{book_title} — {author} [{location}]"
        if score is not None:
            header += f"  (score {score:.2f})"
        print(header)
        print(f"  {m.get('text', '').strip()}\n")


def cmd_suggest(args, books):
    res = suggest_citation(
        args.concept, books, limit=args.limit,
        chapter_loader=lambda book: parse_epub_chapters(book.path),
    )
    if args.json:
        print(json.dumps(res, indent=2))
        return
    if res.get("error"):
        print(f"Error: {res['error']}")
        return

    sources = res["sources"]
    if not sources:
        print(f"No source in the library covers '{args.concept}'.")
        return
    if res["no_strong_source"]:
        print(f"No strong source for '{args.concept}' — only weak matches "
              f"(consider acquiring a dedicated text):\n")
    else:
        print(f"Sources for '{args.concept}' (best first):\n")
    for s in sources:
        loc = f" [{s['location']}]" if s.get("location") else ""
        print(f"{s['book_title']} — {s['author']}  "
              f"(score {s['best_score']:.2f}, {s['hits']} passage(s)){loc}")
        if s.get("passage"):
            print(f"   {s['passage'].strip()[:300]}")
        print()


def cmd_audit(args, books):
    if args.file in (None, "-"):
        raw = sys.stdin.read()
    else:
        try:
            with open(args.file, encoding="utf-8") as fh:
                raw = fh.read()
        except OSError as exc:
            print(f"Cannot read {args.file}: {exc}", file=sys.stderr)
            return 2
    entries = [ln.strip() for ln in raw.splitlines()
               if ln.strip() and not ln.lstrip().startswith("#")]

    results = audit_citations(
        entries, books, text_loader=lambda book: parse_epub_text(book.path),
    )
    counts = Counter(r["status"] for r in results)

    if args.json:
        print(json.dumps({"results": results, "summary": dict(counts)}, indent=2))
    else:
        if not results:
            print("No citations to audit.")
        for r in results:
            line = f"{r['status']:11} {r['entry']}"
            if r["matched_title"] and r["status"] != "MISSING":
                line += f"  -> {r['matched_title']} — {r['matched_author'] or 'Unknown'}"
            print(line)
        if results:
            print("\n" + "  ".join(f"{k}={counts[k]}" for k in sorted(counts)))

    # Anything not solidly PRESENT fails (for CI over a key-texts list).
    failures = sum(v for k, v in counts.items() if k != "PRESENT")
    return 1 if failures else 0


def cmd_doctor(args, books):
    problems = []
    for book in sorted(books.values(), key=lambda b: (b.title or "").lower()):
        text = parse_epub_text(book.path) if book.path else ""
        issues = diagnose_book(book, text)
        if issues:
            problems.append((book, issues))

    if args.json:
        print(json.dumps({
            "total": len(books),
            "with_issues": len(problems),
            "books": [
                {"title": b.title, "path": b.path, "issues": issues}
                for b, issues in problems
            ],
        }, indent=2))
        return

    if not problems:
        print(f"No issues found across {len(books)} book(s).")
        return
    print(f"{len(problems)} of {len(books)} book(s) have issues:\n")
    for book, issues in problems:
        print(f"{book.title or '(untitled)'}")
        print(f"  issues: {', '.join(issues)}")
        print(f"  path:   {book.path}\n")


def build_parser():
    parser = argparse.ArgumentParser(
        prog="epublic",
        description="Search a personal EPUB library for finding and verifying "
                    "citations: look books up (search), find a source for a "
                    "concept (suggest), verify a quote (topic --phrase), "
                    "batch-check a bibliography (audit), or report unsearchable "
                    "books (doctor).",
    )
    parser.add_argument(
        "--paths", action="append", metavar="DIR",
        help="Library directory to scan; repeat for multiple, or separate with "
             f"'{os.pathsep}' (overrides EPUBLIC_LIBRARY_PATHS).",
    )
    parser.add_argument("--json", action="store_true", help="Output raw JSON.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show progress logging.")

    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="List books in the library.")
    p_list.add_argument("--limit", type=int, default=50, help="Max books to show (default 50).")
    p_list.add_argument("--offset", type=int, default=0, help="Books to skip (default 0).")
    p_list.add_argument("--author", action="store_true", help="Include author.")
    p_list.add_argument("--published", action="store_true", help="Include publication year.")
    p_list.set_defaults(func=cmd_list)

    p_search = sub.add_parser("search", help="Search book metadata (title/author/year).")
    p_search.add_argument("query", help="Search query.")
    p_search.set_defaults(func=cmd_search)

    p_topic = sub.add_parser("topic", help="Find passages on a topic with attribution.")
    p_topic.add_argument("topic", nargs="+", help="One or more topics (multiple = OR search).")
    p_topic.add_argument("--book", help="Filter to a specific book title.")
    p_topic.add_argument("--author", help="Filter to a specific author.")
    p_topic.add_argument("--limit", type=int, default=10, help="Max results (default 10).")
    p_topic.add_argument("--offset", type=int, default=0, help="Results to skip (default 0).")
    p_topic.add_argument(
        "--match-type", choices=["exact", "fuzzy"], default="fuzzy",
        help="Match strategy for book/author filters (default fuzzy).",
    )
    p_topic.add_argument(
        "--phrase", action="store_true",
        help="Verbatim substring lookup (for citation verification).",
    )
    p_topic.set_defaults(func=cmd_topic)

    p_suggest = sub.add_parser(
        "suggest",
        help="Suggest citable library sources for a concept (inverse search).",
    )
    p_suggest.add_argument("concept", help="Concept or phrase to find a source for.")
    p_suggest.add_argument("--limit", type=int, default=5, help="Max sources (default 5).")
    p_suggest.set_defaults(func=cmd_suggest)

    p_audit = sub.add_parser(
        "audit",
        help="Check a citation list against the library (exits non-zero on gaps).",
    )
    p_audit.add_argument(
        "file", nargs="?", default="-",
        help="File with one 'Title — Author' (or plain title) per line; '-' or "
             "omitted reads stdin. Lines starting with # are ignored.",
    )
    p_audit.set_defaults(func=cmd_audit)

    p_doctor = sub.add_parser(
        "doctor",
        help="Report books with missing metadata or no text layer.",
    )
    p_doctor.set_defaults(func=cmd_doctor)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(message)s",
    )

    limit = getattr(args, "limit", None)
    offset = getattr(args, "offset", None)
    if limit is not None and (limit < 0 or limit > MAX_LIMIT):
        parser.error(f"--limit must be between 0 and {MAX_LIMIT}")
    if offset is not None and offset < 0:
        parser.error("--offset must be non-negative")

    paths = _resolve_paths(args.paths)
    if not paths:
        parser.error(
            "No library paths configured. Set EPUBLIC_LIBRARY_PATHS or pass --paths."
        )

    books = _load_library(paths)
    if not books:
        print("No books found in the configured library paths.", file=sys.stderr)
        return 1

    rc = args.func(args, books)
    return rc if isinstance(rc, int) else 0


if __name__ == "__main__":
    sys.exit(main())
