import sys

import questionary
from rich.console import Console

console = Console()

QUIT_CHOICE = "quit"


def pick_word(words: list[str], title: str = "Select a word") -> str | None:
    """Interactive arrow-key picker. Returns the chosen word, or None if cancelled."""
    if not words or not sys.stdin.isatty() or not sys.stdout.isatty():
        return None

    choices = [*words, questionary.Separator(), QUIT_CHOICE]
    try:
        result = questionary.select(
            title,
            choices=choices,
            instruction="[type to filter - enter looks up - esc/quit exits]",
            use_search_filter=True,
            use_jk_keys=False,
        ).ask()
    except KeyboardInterrupt:
        return None
    if result is None or result == QUIT_CHOICE:
        return None
    return result
