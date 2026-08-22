import argparse
import sys

from .formatter import render_word_page
from .models import WordPage
from .scraper import (
    LookupError,
    NetworkError,
    WordNotFoundError,
    fetch_word,
    suggest_words,
)


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
    )
    parser.add_argument("word", nargs="+", help="word or phrase to look up")
    return parser


def main(argv: list[str] | None = None) -> int:
    _force_utf8_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)
    word = " ".join(args.word).strip()

    try:
        page = fetch_word(word)
    except WordNotFoundError:
        page = WordPage(word=word)
    except NetworkError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if not page.found:
        page.suggestions = suggest_words(word)
        render_word_page(page)
        return 1

    render_word_page(page)
    return 0


if __name__ == "__main__":
    sys.exit(main())
