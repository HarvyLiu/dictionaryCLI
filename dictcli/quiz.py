import random
from dataclasses import dataclass

from .cache import Cache


@dataclass
class Question:
    direction: str
    prompt: str
    options: list[str]
    correct_index: int
    answer_word: str


def _first_definition(page) -> str | None:
    for entry in page.entries:
        for group in entry.sense_groups:
            for definition in group.definitions:
                if definition.text:
                    return definition.text
    return None


def _first_translation(page) -> str | None:
    for entry in page.entries:
        for group in entry.sense_groups:
            for definition in group.definitions:
                if definition.translations:
                    return definition.translations[0]
    return None


def _short(text: str, limit: int = 90) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "\u2026"


def _load_pool(cache: Cache, words: list[str]) -> dict[str, str]:
    pool: dict[str, str] = {}
    seen: set[str] = set()
    for word in words:
        page = cache.load_word(word)
        if page is None or not page.found or page.word.lower() in seen:
            continue
        definition = _first_definition(page)
        if not definition:
            continue
        seen.add(page.word.lower())
        pool[page.word] = definition
    return pool


def _load_translations(
    cache: Cache, words: list[str], pair: str
) -> dict[str, tuple[str, str]]:
    pool: dict[str, tuple[str, str]] = {}
    seen: set[str] = set()
    for word in words:
        page = cache.load_word(word, pair)
        if page is None or not page.found or page.word.lower() in seen:
            continue
        definition = _first_definition(page)
        translation = _first_translation(page)
        if not definition or not translation:
            continue
        seen.add(page.word.lower())
        pool[page.word] = (definition, translation)
    return pool


def _mcq_options(answer: str, pool_values: list[str], rng) -> tuple[list[str], int]:
    distractors = rng.sample([v for v in pool_values if v != answer], 3)
    shown = [*distractors, answer]
    rng.shuffle(shown)
    return shown, shown.index(answer)


def build_questions(
    cache: Cache,
    words: list[str],
    count: int = 10,
    rng: random.Random = random,
    pair: str = "en",
) -> list[Question] | None:
    """Build MCQ questions from cached starred words.

    pair="en": alternates definition -> word and word -> definition.
    pair like "en-zhs": alternates translation -> word and word -> translation,
    using the bilingual cached copies.
    Returns None when fewer than 4 usable words are available.
    """
    bilingual = pair != "en"
    if bilingual:
        pool = _load_translations(cache, words, pair)
        if len(pool) < 4:
            return None
        items = list(pool.items())
        rng.shuffle(items)
        questions = []
        for i, (word, (definition, translation)) in enumerate(items[: min(count, len(items))]):
            if i % 2 == 0:
                options, correct = _mcq_options(word, list(pool), rng)
                questions.append(
                    Question("trans->word", translation, options, correct, word)
                )
            else:
                options, correct = _mcq_options(
                    translation, [t for _, t in pool.values()], rng
                )
                questions.append(
                    Question("word->trans", word, options, correct, word)
                )
        return questions

    pool = _load_pool(cache, words)
    if len(pool) < 4:
        return None

    items = list(pool.items())
    rng.shuffle(items)
    questions: list[Question] = []

    for i, (answer, definition) in enumerate(items[: min(count, len(items))]):
        direction = "def->word" if i % 2 == 0 else "word->def"
        distractors = rng.sample([w for w, _ in items if w != answer], 3)

        if direction == "def->word":
            options = [*distractors, answer]
            rng.shuffle(options)
            questions.append(
                Question(
                    direction=direction,
                    prompt=_short(definition),
                    options=options,
                    correct_index=options.index(answer),
                    answer_word=answer,
                )
            )
        else:
            shown = [_short(pool[w]) for w in distractors] + [_short(definition)]
            correct_text = shown[-1]
            combined = list(zip(shown, [*distractors, answer]))
            rng.shuffle(combined)
            options = [text for text, _ in combined]
            questions.append(
                Question(
                    direction=direction,
                    prompt=answer,
                    options=options,
                    correct_index=options.index(correct_text),
                    answer_word=answer,
                )
            )

    return questions
