import argparse
import sys

from rich.console import Console

from .cache import Cache, Prefetcher, default_dir
from .formatter import render_word_page
from .models import WordPage
from .scraper import (
    NetworkError,
    WordNotFoundError,
    fetch_word,
    suggest_words,
)
from .wordlist import Wordlist

console = Console()

VERSION = "0.4.0"

SEARCH_LIMIT = 8

CACHE_HELP = (
    "OFFLINE CACHE: {status}.\n"
    "  Caching is opt-in and always starts OFF - nothing is written to your\n"
    "  disk until you turn it on yourself:\n"
    "    dict cache on       start saving every word you look up\n"
    "    dict cache off      stop saving (already-saved words are kept)\n"
    "    dict cache status   see where data lives and how much space it uses\n"
    "    dict cache clear    delete ALL saved words\n"
    "  With caching ON you can still look up saved words with no internet."
)


def _force_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def build_parser() -> argparse.ArgumentParser:
    cache = Cache()
    description = (
        "Look up words in the Cambridge Dictionary from your terminal.\n\n"
        + CACHE_HELP.format(status="ON" if cache.enabled else "OFF")
    )
    parser = argparse.ArgumentParser(
        prog="dict",
        description=description,
        epilog=(
            "examples:\n"
            "  dict apple          look up 'apple'\n"
            "  dict give up        look up a phrase\n"
            "  dict search app     show matching words like the website dropdown\n"
            "  dict search app -p2 look up the 2nd match directly\n"
            "  dict add serendipity  star a word and keep an offline copy\n"
            "  dict list           show your starred words\n"
            "  dict remove apple   unstar a word\n"
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


def _lookup_full(word: str) -> tuple[int, str | None]:
    cache = Cache()
    try:
        page = fetch_word(word)
    except WordNotFoundError:
        page = WordPage(word=word)
    except NetworkError as exc:
        return _offline_lookup(word, f"Network request failed ({exc})"), None

    if page.found:
        if cache.enabled:
            cache.save_page(page)
        render_word_page(page)
        return 0, page.word

    try:
        page.suggestions = suggest_words(word)
    except NetworkError as exc:
        return _offline_lookup(word, f"Network request failed ({exc})"), None
    render_word_page(page)
    return 1, None


def _lookup(word: str) -> int:
    return _lookup_full(word)[0]


def _offline_lookup(word: str, reason: str) -> int:
    cache = Cache()
    cached = cache.load_word(word)
    if cached is not None and cached.found:
        render_word_page(cached, cached=True)
        return 0

    if not cache.enabled:
        print(f"error: {reason}", file=sys.stderr)
        console.print("[dim]tip: 'dict cache on' lets saved words work offline.[/]")
        return 2

    console.print(f"[bold red]Offline:[/] '{word}' has no saved copy.")
    nearest = cache.nearest(word)
    if nearest:
        console.print("Closest saved words:")
        for w in nearest:
            console.print(f"  [yellow]- {w}[/]")
    else:
        stats = cache.stats()
        console.print(
            f"[dim]Your cache holds {stats['count']} words "
            f"({stats['size_bytes'] / 1024:.0f} KB). Connect to the internet to "
            f"fetch new ones.[/]"
        )
    return 2


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


def _format_size(size_bytes: int) -> str:
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    return f"{size_bytes / 1024:.0f} KB"


def _cache_cmd(args: list[str]) -> int:
    action = args[0].lower() if args else "status"
    cache = Cache()

    if action in {"status", ""}:
        stats = cache.stats()
        state = "[green]ON[/]" if cache.enabled else "[red]OFF[/]"
        console.print(f"Offline cache: {state}")
        console.print(f"Location:  [dim]{cache.dir}[/]")
        console.print(
            f"Saved words: {stats['count']} ([dim]{_format_size(stats['size_bytes'])}[/])"
        )
        if not cache.enabled:
            console.print("[dim]Enable with 'dict cache on'.[/]")
        return 0

    if action == "on":
        cache.set_enabled(True)
        console.print(f"[green]Offline cache enabled.[/] Saving lookups to:")
        console.print(f"  [dim]{cache.words_dir}[/]")
        return 0

    if action == "off":
        cache.set_enabled(False)
        stats = cache.stats()
        console.print(
            f"[yellow]Offline cache disabled.[/] No new words will be saved. "
            f"{stats['count']} saved words kept - remove them with 'dict cache clear'."
        )
        return 0

    if action == "clear":
        removed = cache.clear()
        console.print(f"[yellow]Deleted {removed} saved words.[/]")
        return 0

    if action == "list":
        words = cache.cached_words()
        if not words:
            console.print("[dim]No saved words yet.[/]")
            return 0
        for w in words:
            console.print(f"  {w}")
        console.print(f"[dim]{len(words)} saved words total.[/]")
        return 0

    console.print(f"[red]Unknown cache command:[/] {action}")
    console.print("[dim]usage: dict cache [on|off|status|list|clear][/]")
    return 1


def _add_word(word: str) -> int:
    if not word:
        console.print("[dim]usage: dict add <word>[/]")
        return 1

    wordlist = Wordlist()
    cache = Cache()

    if wordlist.has(word):
        cached = cache.load_word(word)
        if cached is None:
            try:
                page = fetch_word(word)
                if page.found and cache.save_page(page, force=True):
                    console.print(
                        f"[yellow]'{page.word}' is already starred; offline copy refreshed.[/]"
                    )
                    return 0
                console.print(f"[red]'{word}' was not found on Cambridge.[/]")
                return 1
            except NetworkError as exc:
                print(f"error: {exc}", file=sys.stderr)
                return 2
        console.print(f"[yellow]'{cached.word}' is already in your wordlist.[/]")
        return 0

    try:
        page = fetch_word(word)
    except WordNotFoundError:
        page = WordPage(word=word)
    except NetworkError as exc:
        cached = cache.load_word(word)
        if cached is not None and cached.found:
            wordlist.add(cached.word)
            console.print(
                f"[green]Starred '{cached.word}'[/] [dim](using existing offline copy).[/]"
            )
            return 0
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if page.found:
        cache.save_page(page, force=True)
        wordlist.add(page.word)
        console.print(
            f"[green]Starred '{page.word}'[/] [dim]- offline copy saved.[/]"
        )
        return 0

    suggestions = []
    try:
        suggestions = suggest_words(word, limit=5)
    except NetworkError:
        pass
    console.print(f"[bold red]'{word}' not found - nothing starred.[/]")
    if suggestions:
        console.print("Did you mean:")
        for s in suggestions:
            console.print(f"  [yellow]- {s}[/]")
    return 1


def _remove_word(word: str) -> int:
    if not word:
        console.print("[dim]usage: dict remove <word>[/]")
        return 1
    wordlist = Wordlist()
    removed = wordlist.remove(word)
    if not removed:
        console.print(f"[red]'{word}' is not in your wordlist.[/]")
        return 1
    console.print(f"[green]Removed '{word}' from your wordlist.[/] "
                  f"[dim](saved lookup data kept - 'dict cache clear' deletes it.)[/]")
    return 0


def _list_words() -> int:
    wordlist = Wordlist()
    cache = Cache()
    entries = wordlist.entries()
    if not entries:
        console.print("[dim]Your wordlist is empty. Star words with:[/] dict add <word>")
        return 0
    console.print(f"[bold]Wordlist[/] [dim]({len(entries)})[/]")
    for e in entries:
        w = e.get("word", "?")
        mark = "[green]cached[/]" if cache.has(w) else "[red]no copy[/]"
        console.print(f"  {w}  [dim]{mark}[/]")
    return 0


def _is_cache_cmd(line: str) -> bool:
    parts = line.lower().split()
    return len(parts) >= 1 and parts[0] == "cache"


def _repl() -> int:
    cache = Cache()
    wordlist = Wordlist()
    prefetcher = Prefetcher(cache)
    prefetcher.start()

    state = "[green]ON[/]" if cache.enabled else "[red]OFF[/]"
    console.print(
        "[bold cyan]Cambridge Dictionary CLI[/] "
        f"[dim]- type a word, :s <query> search, :a add last, :rm, :q quit | cache: {state}[/]"
    )
    last_word: str | None = None
    last_status = 0
    try:
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
            if lowered in {":a", ":add"}:
                if not last_word:
                    console.print("[dim]nothing looked up yet.[/]")
                    continue
                last_status = _add_word(last_word)
                continue
            if lowered.startswith(":add ") or lowered.startswith(":a "):
                arg = line.split(" ", 1)[1].strip()
                last_status = _add_word(arg) if arg else 1
                continue
            if lowered.startswith(":rm") or lowered.startswith(":remove"):
                parts = line.split(None, 1)
                target = parts[1].strip() if len(parts) > 1 else last_word
                if not target:
                    console.print("[dim]usage: :rm <word>[/]")
                    continue
                last_status = _remove_word(target)
                continue
            if lowered.startswith(":s"):
                query = line[2:].strip()
                if not query:
                    console.print("[dim]usage: :s <query>[/]")
                    continue
                last_status = _search(query, None)
            elif lowered.startswith(":cache"):
                arg = line[6:].strip()
                _cache_cmd(arg.split() if arg else [])
            elif lowered.startswith(":"):
                console.print(f"[red]unknown command[/] {line.split()[0]}")
            else:
                last_status, resolved = _lookup_full(line)
                if resolved:
                    last_word = resolved
                if last_status == 0 and cache.enabled:
                    prefetcher.enqueue_related(resolved or line)
    finally:
        prefetcher.stop()
    return last_status


def main(argv: list[str] | None = None) -> int:
    _force_utf8_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)
    words = args.words

    if not words:
        return _repl()

    if words[0].lower() == "cache":
        return _cache_cmd(words[1:])

    if words[0].lower() == "add":
        return _add_word(" ".join(words[1:]).strip())

    if words[0].lower() in {"remove", "rm"}:
        return _remove_word(" ".join(words[1:]).strip())

    if words[0].lower() in {"list", "ls"}:
        return _list_words()

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
