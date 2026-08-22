import sys

from rich.console import Console

console = Console()


def pick_word(words: list[str], title: str = "Select a word") -> str | None:
    """Interactive arrow-key picker. Returns the chosen word, or None if cancelled."""
    if not words or not sys.stdin.isatty() or not sys.stdout.isatty():
        return None
    try:
        import questionary
    except ImportError:
        return None

    try:
        result = questionary.select(
            title,
            choices=words,
            instruction="[up/down to move, enter to look up, q to cancel]",
            use_search_filter=True,
            use_jk_keys=False,
        ).ask()
    except KeyboardInterrupt:
        return None
    return result
