import argparse
import sys

from rich.console import Console

from .formatter import render_word_page
from .models import WordPage
from .scraper import (
    LookupError,
    NetworkError,
    WordNotFoundError,
    fetch_word,
    suggest_words,
)

console = Console()

VERSION = "0.2.0"

SEARCH_LIMIT = 8


def _force_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dict",
        description="Look up words in the Cambridge Dictionary from your terminal.",
        epilog=(
            "examples:\n"
            "  dict apple          look up 'apple'\n"
            "  dict give up        look up a phrase\n"
            "  dict search app     show matching words like the website dropdown\n"
            "  dict search app -p2 look up the 2nd match directly\n"
            "  dict                enter interactive mode\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"dict {VERSION}")
    parser.add_argument(
        "words",
        nargs="*",
        help="word or phrase to look up; omit to enter interactive mode",
    )
    parser.add_argument(
        "-p",
        "--pick",
        type=int,
        metavar="N",
        help="with 'search': immediately look up the Nth result",
    )
    return parser


def _lookup(word: str) -> int:
    try:
        page = fetch_word(word)
    except WordNotFoundError:
        page = WordPage(word=word)
    except NetworkError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if not page.found:
        try:
            page.suggestions = suggest_words(word)
        except NetworkError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        render_word_page(page)
        return 1

    render_word_page(page)
    return 0


def _print_candidates(candidates: list[str], query: str) -> None:
    console.print(f"[bold]Matches for[/] [cyan]'{query}'[/][dim]:[/]")
    for i, candidate in enumerate(candidates, start=1):
        console.print(f"  [dim]{i}.[/] [yellow]{candidate}[/]")


def _choose_candidate(candidates: list[str]) -> str | None:
    while True:
        try:
            choice = console.input(
                f"[bold]Pick 1-{len(candidates)}[/] [dim](Enter cancels): [/]"
            ).strip()
        except (EOFError, KeyboardInterrupt):
            console.print()
            return None
        if not choice:
            return None
        if choice.isdigit() and 1 <= int(choice) <= len(candidates):
            return candidates[int(choice) - 1]
        console.print(f"[red]Invalid choice:[/] {choice}")


def _search(query: str, pick: int | None, interactive: bool = True) -> int:
    try:
        candidates = suggest_words(query, limit=SEARCH_LIMIT)
    except NetworkError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if not candidates:
        console.print(f"[bold red]No matches for '{query}'.[/]")
        return 1

    _print_candidates(candidates, query)

    if pick is not None:
        if not 1 <= pick <= len(candidates):
            console.print(f"[red]-p must be between 1 and {len(candidates)}[/]")
            return 1
        chosen = candidates[pick - 1]
    elif interactive and sys.stdin.isatty():
        chosen = _choose_candidate(candidates)
        if chosen is None:
            return 0
    else:
        return 0

    console.print()
    return _lookup(chosen)


def _repl() -> int:
    console.print(
        "[bold cyan]Cambridge Dictionary CLI[/] "
        "[dim]- type a word to look it up, :s <query> to search, :q to quit[/]"
    )
    last_status = 0
    while True:
        try:
            line = console.input("[bold cyan]dict[/][dim]> [/]").strip()
        except (EOFError, KeyboardInterrupt):
            console.print()
            break
        if not line:
            continue
        lowered = line.lower()
        if lowered in {":q", ":quit", ":exit"}:
            break
        if lowered.startswith(":s"):
            query = line[2:].strip()
            if not query:
                console.print("[dim]usage: :s <query>[/]")
                continue
            last_status = _search(query, None)
        else:
            last_status = _lookup(line)
    return last_status


def main(argv: list[str] | None = None) -> int:
    _force_utf8_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)
    words = args.words

    if not words:
        return _repl()

    if words[0].lower() == "search":
        query = " ".join(words[1:]).strip()
        if not query:
            parser.error("search requires a query")
        return _search(query, args.pick)

    if args.pick is not None:
        parser.error("-p/--pick only works with 'search'")

    return _lookup(" ".join(words))


if __name__ == "__main__":
    sys.exit(main())
