import random

import pytest

from dictcli.cache import Cache
from dictcli.models import Definition, Entry, SenseGroup, WordPage
from dictcli.quiz import build_questions


def make_page(word: str, definition: str) -> WordPage:
    entry = Entry(
        pos="noun",
        sense_groups=[SenseGroup(definitions=[Definition(text=definition)])],
    )
    return WordPage(word=word, entries=[entry])


WORDS = {
    "apple": "a round fruit with firm white flesh",
    "banana": "a long curved fruit with a yellow skin",
    "cherry": "a small soft red fruit with a single hard seed",
    "date": "a sweet sticky brown fruit with a long seed",
    "elderberry": "a small dark purple fruit used for wine and jams",
}


@pytest.fixture()
def cache(tmp_path):
    c = Cache(base_dir=tmp_path, enabled=True)
    for word, definition in WORDS.items():
        c.save_page(make_page(word, definition))
    return c


class TestBuildQuestions:
    def test_none_when_pool_too_small(self, cache):
        assert build_questions(cache, ["apple", "banana", "cherry"]) is None

    def test_basic_build(self, cache):
        questions = build_questions(cache, list(WORDS), rng=random.Random(42))
        assert questions is not None
        assert len(questions) == 5

    def test_count_capped_by_pool(self, cache):
        questions = build_questions(
            cache, list(WORDS), count=50, rng=random.Random(1)
        )
        assert len(questions) == 5

    def test_alternating_directions(self, cache):
        questions = build_questions(cache, list(WORDS), rng=random.Random(7))
        directions = [q.direction for q in questions]
        expected = [
            "def->word" if i % 2 == 0 else "word->def" for i in range(len(questions))
        ]
        assert directions == expected

    def test_options_have_four_choices_with_valid_answer(self, cache):
        questions = build_questions(cache, list(WORDS), rng=random.Random(3))
        for q in questions:
            assert len(q.options) == 4
            assert len(set(q.options)) == 4
            assert 0 <= q.correct_index < 4

    def test_def_to_word_prompt_is_definition_answer_is_word(self, cache):
        questions = build_questions(cache, list(WORDS), count=2, rng=random.Random(9))
        first = questions[0]
        assert first.direction == "def->word"
        assert first.prompt in WORDS.values() or first.prompt.endswith("\u2026")
        assert first.answer_word in WORDS

    def test_word_to_def_prompt_is_word(self, cache):
        questions = build_questions(cache, list(WORDS), count=4, rng=random.Random(11))
        word_q = next(q for q in questions if q.direction == "word->def")
        assert word_q.prompt in WORDS
        correct_text = word_q.options[word_q.correct_index]
        assert (
            WORDS[word_q.prompt] == correct_text
            or correct_text.startswith(WORDS[word_q.prompt][:80])
        )

    def test_skips_words_without_cached_copy(self, cache):
        questions = build_questions(
            cache, [*WORDS, "unstarred-ghost"], rng=random.Random(5)
        )
        prompts = {q.answer_word for q in questions}
        assert "unstarred-ghost" not in prompts
