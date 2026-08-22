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


def _short(text: str, limit: int = 90) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "\u2026"


def _load_pool(cache: Cache, words: list[str]) -> tuple[list[str], dict[str, str]]:
    pool: list[str] = []
    definitions: dict[str, str] = {}
    seen: set[str] = set()
    for word in words:
        page = cache.load_word(word)
        if page is None or not page.found or page.word.lower() in seen:
            continue
        definition = _first_definition(page)
        if not definition:
            continue
        seen.add(page.word.lower())
        pool.append(page.word)
        definitions[page.word] = definition
    return pool, definitions


def build_questions(
    cache: Cache,
    words: list[str],
    count: int = 10,
    rng: random.Random = random,
) -> list[Question] | None:
    """Build MCQ questions from cached starred words.

    Alternates direction: definition -> word, then word -> definition.
    Returns None when fewer than 4 usable words are available.
    """
    pool, definitions = _load_pool(cache, words)
    if len(pool) < 4:
        return None

    rng.shuffle(pool)
    questions: list[Question] = []
    total = min(count, len(pool))

    for i, answer in enumerate(pool[:total]):
        direction = "def->word" if i % 2 == 0 else "word->def"
        distractors = rng.sample([w for w in pool if w != answer], 3)

        if direction == "def->word":
            options = [*distractors, answer]
            rng.shuffle(options)
            questions.append(
                Question(
                    direction=direction,
                    prompt=_short(definitions[answer]),
                    options=options,
                    correct_index=options.index(answer),
                    answer_word=answer,
                )
            )
        else:
            shown = [_short(definitions[w]) for w in [*distractors, answer]]
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
