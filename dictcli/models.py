from dataclasses import dataclass, field


@dataclass
class Definition:
    text: str
    cefr: str | None = None
    labels: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)


@dataclass
class SenseGroup:
    guideword: str | None = None
    definitions: list[Definition] = field(default_factory=list)


@dataclass
class Entry:
    pos: str | None = None
    grammar: str | None = None
    ipa_uk: str | None = None
    ipa_us: str | None = None
    audio_uk: str | None = None
    audio_us: str | None = None
    sense_groups: list[SenseGroup] = field(default_factory=list)


@dataclass
class WordPage:
    word: str
    entries: list[Entry] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    source_url: str | None = None

    @property
    def found(self) -> bool:
        return bool(self.entries)
