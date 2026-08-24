from rich.console import Console
from rich.rule import Rule
from rich.text import Text

from .models import Entry, WordPage

console = Console()

POS_STYLE = "bold yellow"
IPA_STYLE = "dim italic cyan"
GUIDEWORD_STYLE = "bold magenta"
CEFR_STYLE = "green"
LABEL_STYLE = "red dim"
EXAMPLE_STYLE = "italic"


def render_word_page(page: WordPage, cached: bool = False) -> None:
    if not page.found:
        _render_not_found(page)
        return

    console.print()
    header = Text(page.word, style="bold cyan")
    ipa_parts = []
    if page.entries:
        first = page.entries[0]
        if first.ipa_uk:
            ipa_parts.append((f"{first.ipa_uk} UK", IPA_STYLE))
        if first.ipa_us:
            ipa_parts.append((f"{first.ipa_us} US", IPA_STYLE))
    line = Text("  ").append_text(header)
    for text, style in ipa_parts:
        line.append(f"  {text}", style)
    console.print(line)
    if cached:
        console.print(Text("  [offline - showing saved copy]", style="dim yellow"))
    console.print(Rule(style="dim"))

    for i, entry in enumerate(page.entries):
        _render_entry(entry, number=len(page.entries) > 1 and i + 1 or None)
    console.print()


def _render_entry(entry: Entry, number: int | None = None) -> None:
    title = Text()
    if number is not None:
        title.append(f"{number}. ", style="dim")
    if entry.pos:
        title.append(entry.pos, style=POS_STYLE)
    if entry.grammar:
        title.append(f" {entry.grammar}", style="dim")
    console.print(title)
    if entry.synonyms:
        syn = Text("  synonyms: ", style="dim").append(
            " - ".join(entry.synonyms), style="magenta"
        )
        console.print(syn)

    def_number = 0
    for group in entry.sense_groups:
        if group.guideword:
            console.print(Text(f"  {group.guideword}", style=GUIDEWORD_STYLE))
        for definition in group.definitions:
            def_number += 1
            line = Text("  ")
            if len(entry.sense_groups) > 1 or len(
                [d for g in entry.sense_groups for d in g.definitions]
            ) > 1:
                line.append(f"{def_number}. ", style="dim bold")
            if definition.cefr:
                line.append(f"[{definition.cefr}] ", style=CEFR_STYLE)
            for label in definition.labels:
                line.append(f"({label}) ", style=LABEL_STYLE)
            line.append(definition.text)
            console.print(line)
            if definition.translations:
                trans = Text("       ", style="").append(
                    " / ".join(definition.translations), style="bold yellow"
                )
                console.print(trans)
            for example in definition.examples:
                ex = Text("       • ", style="dim").append(example, style=EXAMPLE_STYLE)
                console.print(ex)


def _render_not_found(page: WordPage) -> None:
    msg = Text(f"'{page.word}' was not found in the Cambridge Dictionary.", style="bold red")
    console.print(msg)
    if page.suggestions:
        console.print(Text("Did you mean:", style="bold"))
        for s in page.suggestions[:5]:
            console.print(Text(f"  • {s}", style="yellow"))
