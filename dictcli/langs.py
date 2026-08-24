from dataclasses import dataclass


@dataclass(frozen=True)
class LangPair:
    code: str
    path: str
    name: str


LANG_PAIRS: dict[str, LangPair] = {
    pair.code: pair
    for pair in [
        LangPair("en", "english", "English (monolingual, default)"),
        LangPair("en-zhs", "english-chinese-simplified", "English to Chinese (Simplified)"),
        LangPair("en-zht", "english-chinese-traditional", "English to Chinese (Traditional)"),
        LangPair("zhs-en", "chinese-simplified-english", "Chinese (Simplified) to English"),
        LangPair("zht-en", "chinese-traditional-english", "Chinese (Traditional) to English"),
        LangPair("en-ja", "english-japanese", "English to Japanese"),
        LangPair("ja-en", "japanese-english", "Japanese to English"),
        LangPair("en-ko", "english-korean", "English to Korean"),
        LangPair("en-fr", "english-french", "English to French"),
        LangPair("fr-en", "french-english", "French to English"),
        LangPair("en-de", "english-german", "English to German"),
        LangPair("de-en", "german-english", "German to English"),
        LangPair("en-it", "english-italian", "English to Italian"),
        LangPair("it-en", "italian-english", "Italian to English"),
        LangPair("en-es", "english-spanish", "English to Spanish"),
        LangPair("es-en", "spanish-english", "Spanish to English"),
        LangPair("en-pt", "english-portuguese", "English to Portuguese"),
        LangPair("en-ru", "english-russian", "English to Russian"),
        LangPair("en-tr", "english-turkish", "English to Turkish"),
        LangPair("en-vi", "english-vietnamese", "English to Vietnamese"),
    ]
}

_ALIASES = {
    "us": "en",
    "uk": "en",
    "zh": "zhs",
    "zh-hans": "zhs",
    "zh-hant": "zht",
    "chinese": "zhs",
    "jp": "ja",
}


def resolve_pair(code: str) -> LangPair | None:
    return LANG_PAIRS.get(code.lower())


def resolve_from_tokens(tokens: list[str]) -> LangPair | None:
    """Accept 'en zhs', 'us zh', or a single 'en-zhs' token."""
    if not tokens:
        return None
    if len(tokens) == 1:
        return resolve_pair(tokens[0])
    normalized = [_ALIASES.get(t.lower(), t.lower()) for t in tokens[:2]]
    return resolve_pair(f"{normalized[0]}-{normalized[1]}")


def list_pairs() -> list[LangPair]:
    return list(LANG_PAIRS.values())
