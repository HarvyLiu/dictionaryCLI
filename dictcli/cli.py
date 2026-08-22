import argparse
import json
import sys
import time
from pathlib import Path

from rich.console import Console
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from .audio import play_url
from .cache import Cache, Prefetcher, _page_to_dict, default_dir, slugify
from .formatter import render_word_page
from .models import WordPage
from .picker import pick_word
from .quiz import build_questions
from .scraper import (
    LookupError,
    NetworkError,
    WordNotFoundError,
    fetch_word,
    suggest_words,
)
from .wordlist import Wordlist

console = Console()

VERSION = "0.6.0"

BANNER = r"""
  ____                ____  _      _    ____ _     ___
 / ___|__ _ _ __ ___ |  _ \(_) ___| |_ / ___| |   |_ _|
| |   / _` | '_ ` _ \| | | | |/ __| __| |   | |    | |
| |__| (_| | | | | | | |_| | | (__| |_| |___| |___ | |
 \____\__,_|_| |_| |_|____/|_|\___|\__|\____|_____|___|
"""

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
            "  dict apple --audio     look up and play UK pronunciation\n"
            "  dict apple --audio us  look up and play US pronunciation\n"
            "  dict give up        look up a phrase\n"
            "  dict search app     show matching words like the website dropdown\n"
            "  dict search app -p2 look up the 2nd match directly\n"
            "  dict add serendipity  star a word and keep an offline copy\n"
            "  dict list           browse starred words with arrow keys,\n"
            "                      enter looks one up (--plain for a plain list)\n"
            "  dict remove apple   unstar a word\n"
            "  dict quiz           MCQ quiz from your starred words\n"
            "  dict export my-words.txt    save wordlist as plain text\n"
            "  dict import my-words.txt    star every word in a text file\n"
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
    parser.add_argument(
        "--plain",
        action="store_true",
        help="with 'list': print words instead of the arrow-key picker",
    )
    parser.add_argument(
        "--audio",
        nargs="?",
        const="uk",
        choices=["uk", "us"],
        metavar="UK|US",
        help="play pronunciation after a lookup - 'uk' (default) or 'us'",
    )
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="with 'import': star words without downloading their definitions",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="with lookup/search: print machine-readable JSON instead of formatted text",
    )
    return parser


def _play_audio(page: WordPage, variant: str) -> None:
    for entry in page.entries:
        url = entry.audio_uk if variant == "uk" else entry.audio_us
        url = url or entry.audio_uk or entry.audio_us
        if not url:
            continue
        ok, msg = play_url(url)
        if ok:
            console.print(f"[dim]played {variant} pronunciation[/]")
        else:
            console.print(f"[yellow]audio unavailable:[/] {msg}")
        return
    console.print("[yellow]no audio found for this word.[/]")


def _page_json(page: WordPage) -> dict:
    data = _page_to_dict(page)
    data["found"] = True
    return data


def _lookup_full(
    word: str, say: str | None = None, as_json: bool = False
) -> tuple[int, str | None]:
    cache = Cache()
    try:
        page = fetch_word(word)
    except WordNotFoundError:
        page = WordPage(word=word)
    except NetworkError as exc:
        if as_json:
            print(json.dumps({"ok": False, "error": str(exc)}))
            return 2, None
        return _offline_lookup(word, f"Network request failed ({exc})"), None

    if page.found:
        if cache.enabled:
            cache.save_page(page)
        if as_json:
            print(json.dumps(_page_json(page), ensure_ascii=False))
            return 0, page.word
        render_word_page(page)
        if say:
            _play_audio(page, say)
        return 0, page.word

    try:
        page.suggestions = suggest_words(word)
    except NetworkError as exc:
        if as_json:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
            return 2, None
        return _offline_lookup(word, f"Network request failed ({exc})"), None

    if as_json:
        print(
            json.dumps(
                {"word": page.word, "found": False, "suggestions": page.suggestions},
                ensure_ascii=False,
            )
        )
        return 1, None
    render_word_page(page)
    return 1, None


def _lookup(word: str, say: str | None = None, as_json: bool = False) -> int:
    return _lookup_full(word, say=say, as_json=as_json)[0]


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
    chosen = pick_word(candidates, title="Matches")
    if chosen is None:
        console.print("[dim]cancelled.[/]")
    return chosen


def _search(
    query: str,
    pick: int | None,
    interactive: bool = True,
    say: str | None = None,
    as_json: bool = False,
) -> int:
    try:
        candidates = suggest_words(query, limit=SEARCH_LIMIT)
    except NetworkError as exc:
        if as_json:
            print(json.dumps({"ok": False, "error": str(exc)}))
            return 2
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if not candidates:
        if as_json:
            print(json.dumps({"query": query, "candidates": []}))
            return 1
        console.print(f"[bold red]No matches for '{query}'.[/]")
        return 1

    if as_json:
        if pick is not None:
            if not 1 <= pick <= len(candidates):
                print(json.dumps({"ok": False, "error": "-p out of range"}))
                return 1
            console.print()
            return _lookup(candidates[pick - 1], say=say, as_json=True)
        print(json.dumps({"query": query, "candidates": candidates}, ensure_ascii=False))
        return 0

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
    return _lookup(chosen, say=say)


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


def _list_words(plain: bool = False) -> int:
    wordlist = Wordlist()
    cache = Cache()
    entries = wordlist.entries()
    if not entries:
        console.print("[dim]Your wordlist is empty. Star words with:[/] dict add <word>")
        return 0

    words = [e.get("word", "?") for e in entries]

    interactive = (
        not plain
        and sys.stdin.isatty()
        and sys.stdout.isatty()
    )
    if interactive:
        while True:
            chosen = pick_word(words, title="Your words")
            if chosen is None:
                return 0
            console.print()
            _lookup_full(chosen)
            if sys.stdin.isatty() and sys.stdout.isatty():
                continue
            return 0

    console.print(f"[bold]Wordlist[/] [dim]({len(entries)})[/]")
    for e in entries:
        w = e.get("word", "?")
        mark = "[green]cached[/]" if cache.has(w) else "[red]no copy[/]"
        console.print(f"  {w}  [dim]{mark}[/]")
    return 0


def _export_words(path_str: str) -> int:
    if not path_str:
        console.print("[dim]usage: dict export <file.txt>[/]")
        return 1
    entries = Wordlist().entries()
    if not entries:
        console.print("[dim]Wordlist is empty - nothing to export.[/]")
        return 1
    path = Path(path_str)
    try:
        with open(path, "w", encoding="utf-8") as f:
            for e in entries:
                f.write(f"{e.get('word', '')}\n")
    except OSError as exc:
        print(f"error: could not write {path} ({exc})", file=sys.stderr)
        return 2
    console.print(f"[green]Exported {len(entries)} words to[/] {path}")
    return 0


def _import_words(path_str: str, fetch: bool = True) -> int:
    if not path_str:
        console.print("[dim]usage: dict import <file.txt> [--no-fetch][/]")
        return 1
    path = Path(path_str)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        print(f"error: could not read {path} ({exc})", file=sys.stderr)
        return 2

    words = []
    seen: set[str] = set()
    for line in lines:
        w = line.strip()
        if not w or w.startswith("#"):
            continue
        slug = slugify(w)
        if slug not in seen:
            seen.add(slug)
            words.append(w)

    if not words:
        console.print("[dim]No words found in file (one word per line).[/]")
        return 1

    wordlist = Wordlist()
    cache = Cache()
    added = skipped = failed = 0
    for i, w in enumerate(words):
        if wordlist.has(w):
            skipped += 1
            continue
        if fetch:
            try:
                page = fetch_word(w)
            except (NetworkError, WordNotFoundError):
                failed += 1
                console.print(f"  [red]failed:[/] {w}")
                continue
            if not page.found:
                failed += 1
                console.print(f"  [red]not found:[/] {w}")
                continue
            cache.save_page(page, force=True)
            wordlist.add(page.word)
            added += 1
            console.print(f"  [green]+ {page.word}[/]")
            if i < len(words) - 1:
                time.sleep(0.3)
        else:
            wordlist.add(w)
            added += 1
            console.print(f"  [green]+ {w}[/] [dim](no offline copy)[/]")

    summary = f"[green]{added} starred[/], {skipped} already present"
    if failed:
        summary += f", [red]{failed} failed[/]"
    if not fetch:
        summary += "[dim] (run 'dict add <word>' later to save offline copies)[/]"
    console.print(f"Import from {path}: {summary}")
    return 0 if not failed or added or skipped else 1


def _repl_audio(target: str | None, variant: str, cache: Cache) -> None:
    if not target:
        console.print("[dim]usage: :v[k|s] <word>  (or look one up first)[/]")
        return
    page = cache.load_word(target)
    if page is None:
        try:
            page = fetch_word(target)
        except LookupError as exc:
            console.print(f"[yellow]audio unavailable:[/] {exc}")
            return
    if page.found:
        _play_audio(page, variant)
    else:
        console.print(f"[red]'{target}' not found.[/]")


def _quiz_cmd(args_list: list[str]) -> int:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print("error: quiz needs an interactive terminal", file=sys.stderr)
        return 2

    count = 10
    if args_list and args_list[0].isdigit():
        count = max(3, min(50, int(args_list[0])))

    wordlist = Wordlist()
    cache = Cache()
    questions = build_questions(
        cache, [e.get("word", "") for e in wordlist.entries()], count=count
    )
    if questions is None:
        console.print("[bold red]Not enough words to build a quiz.[/]")
        console.print(
            "[dim]Star at least 4 words with offline copies first:[/] dict add <word>"
        )
        return 1

    import questionary
    from questionary import Choice

    letters = "ABCD"
    score = 0
    asked = 0
    total = len(questions)

    for i, q in enumerate(questions, start=1):
        console.print()
        console.print(Rule(f"[bold]Question {i} of {total}[/]", style="dim"))
        if q.direction == "def->word":
            console.print("[dim]Which word means:[/]")
            console.print(Text("  " + q.prompt, style="italic"))
        else:
            console.print("[dim]What does this mean?[/]")
            console.print(Text("  " + q.prompt, style="bold cyan"))

        choices = [
            Choice(title=f"({letters[j]}) {opt}", value=j)
            for j, opt in enumerate(q.options)
        ]
        try:
            picked = questionary.select(
                "Answer:",
                choices=choices,
                instruction="[arrow keys, enter to submit]",
                use_search_filter=False,
                use_jk_keys=False,
            ).ask()
        except KeyboardInterrupt:
            picked = None

        if picked is None:
            console.print(f"\n[yellow]Quiz ended early after {asked} of {total}.[/]")
            break

        asked += 1
        if picked == q.correct_index:
            score += 1
            console.print(f"  [green]\u2713 Correct![/]  [dim]score: {score}/{asked}[/]")
        else:
            right = f"({letters[q.correct_index]}) {q.options[q.correct_index]}"
            console.print(f"  [red]\u2717 Wrong.[/] Answer: {right}")
            console.print(f"  [yellow]{q.answer_word}[/]  [dim]score: {score}/{asked}[/]")

    console.print()
    pct = int(score * 100 / asked) if asked else 0
    style = "green" if pct >= 80 else "yellow" if pct >= 50 else "red"
    verdict = "Great job!" if pct >= 80 else "Not bad!" if pct >= 50 else "Keep practicing!"
    console.print(Rule(style="dim"))
    console.print(
        Text(f"Final score: {score}/{asked or total}", style=f"bold {style}")
        .append(f"  ({pct}%) - {verdict}", style=style)
    )
    return 0


def _is_cache_cmd(line: str) -> bool:
    parts = line.lower().split()
    return len(parts) >= 1 and parts[0] == "cache"


REPL_COMMANDS = [
    ("<word>", "look up a word or phrase"),
    (":s <query>", "search - matching words like the website dropdown"),
    (":w", "browse starred words with arrow keys, enter looks up"),
    (":a [word]", "star a word and keep an offline copy (default: last lookup)"),
    (":rm [word]", "unstar a word (default: last lookup)"),
    (":vk [word]", "play UK pronunciation"),
    (":vs [word]", "play US pronunciation"),
    (":quiz [count]", "MCQ quiz from your starred words"),
    (":cache on/off/status/list/clear", "manage the offline cache"),
    (":h", "show this help"),
    (":q", "quit"),
]


def _repl_help() -> None:
    table = Table(box=None, show_header=False, padding=(0, 2), pad_edge=False)
    table.add_column(style="bold cyan", no_wrap=True)
    table.add_column(style="dim")
    for cmd, desc in REPL_COMMANDS:
        table.add_row(cmd, desc)
    console.print(table)


def _repl() -> int:
    cache = Cache()
    wordlist = Wordlist()
    prefetcher = Prefetcher(cache)
    prefetcher.start()

    console.print(BANNER, style="bold cyan", markup=False, highlight=False)
    _repl_help()
    state = "[green]ON[/]" if cache.enabled else "[red]OFF[/]"
    stats = cache.stats()
    console.print(
        f"[dim]offline cache: {state}"
        f" - {stats['count']} words saved. Type a word to begin.[/]"
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
            if lowered.startswith(":quiz"):
                _quiz_cmd([line[5:].strip()] if line[5:].strip() else [])
                continue
            if lowered in {":h", ":help"}:
                _repl_help()
                continue
            if lowered in {":w", ":wl", ":words"}:
                starred = [e.get("word", "?") for e in wordlist.entries()]
                chosen = pick_word(starred, title="Your words")
                if chosen:
                    console.print()
                    last_status, resolved = _lookup_full(chosen)
                    if resolved:
                        last_word = resolved
                continue
            if lowered.startswith(":v"):
                parts = line.split(None, 1)
                cmd = parts[0].lower()
                arg = parts[1].strip() if len(parts) > 1 else ""
                variant = {"vk": "uk", "vs": "us"}.get(cmd.lstrip(":"), "uk")
                _repl_audio(arg or last_word, variant, cache)
                continue
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

    if words[0].lower() == "quiz":
        return _quiz_cmd(words[1:])

    if words[0].lower() == "cache":
        return _cache_cmd(words[1:])

    if words[0].lower() == "add":
        return _add_word(" ".join(words[1:]).strip())

    if words[0].lower() in {"remove", "rm"}:
        return _remove_word(" ".join(words[1:]).strip())

    if words[0].lower() in {"list", "ls"}:
        return _list_words(plain=args.plain)

    if words[0].lower() == "search":
        query = " ".join(words[1:]).strip()
        if not query:
            parser.error("search requires a query")
        return _search(query, args.pick, say=args.audio, as_json=args.json)

    if words[0].lower() == "export":
        return _export_words(" ".join(words[1:]).strip())

    if words[0].lower() == "import":
        return _import_words(" ".join(words[1:]).strip(), fetch=not args.no_fetch)

    if args.pick is not None:
        parser.error("-p/--pick only works with 'search'")

    return _lookup(" ".join(words), say=args.audio, as_json=args.json)


if __name__ == "__main__":
    sys.exit(main())
