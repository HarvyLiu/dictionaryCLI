import random

import pytest

import dictcli.cli as cli
from dictcli.cache import Cache
from dictcli.models import Definition, Entry, SenseGroup, WordPage
from dictcli.quiz import build_questions


def make_page(word: str, definition: str, translation: str | None = None) -> WordPage:
    d = Definition(text=definition)
    if translation is not None:
        d.translations = [translation]
    entry = Entry(pos="noun", sense_groups=[SenseGroup(definitions=[d])])
    return WordPage(word=word, entries=[entry])


WORDS = {
    "apple": ("a round fruit with firm white flesh", "苹果"),
    "banana": ("a long curved fruit with a yellow skin", "香蕉"),
    "cherry": ("a small soft red fruit", "樱桃"),
    "date": ("a sweet sticky brown fruit", "枣"),
    "elderberry": ("a small dark purple fruit", "接骨木果"),
}


@pytest.fixture()
def cache(tmp_path):
    c = Cache(base_dir=tmp_path, enabled=True)
    for word, (definition, _) in WORDS.items():
        c.save_page(make_page(word, definition))
    return c


@pytest.fixture()
def zhs_cache(tmp_path):
    c = Cache(base_dir=tmp_path, enabled=True)
    for word, (definition, translation) in WORDS.items():
        c.save_page(make_page(word, definition, translation), pair="en-zhs")
    return c


class TestParseQuizArgs:
    def test_count_only(self):
        assert cli._parse_quiz_args(["20"]) == (20, None)

    def test_lang_only(self):
        assert cli._parse_quiz_args(["--lang", "en-zhs"]) == (10, "en-zhs")

    def test_combined(self):
        assert cli._parse_quiz_args(["15", "-l", "en-zht"]) == (15, "en-zht")

    def test_empty(self):
        assert cli._parse_quiz_args([]) == (10, None)


class TestBilingualQuestions:
    def test_none_without_translations(self, cache):
        assert build_questions(cache, list(WORDS), pair="en-zhs") is None

    def test_bilingual_build(self, zhs_cache):
        questions = build_questions(
            zhs_cache, list(WORDS), rng=random.Random(42), pair="en-zhs"
        )
        assert questions is not None
        assert len(questions) == 5

    def test_alternating_bilingual_directions(self, zhs_cache):
        questions = build_questions(
            zhs_cache, list(WORDS), rng=random.Random(1), pair="en-zhs"
        )
        expected = ["trans->word" if i % 2 == 0 else "word->trans" for i in range(5)]
        assert [q.direction for q in questions] == expected

    def test_trans_to_word_prompt_is_translation(self, zhs_cache):
        questions = build_questions(
            zhs_cache, list(WORDS), rng=random.Random(3), pair="en-zhs"
        )
        q = next(q for q in questions if q.direction == "trans->word")
        assert q.prompt in [t for _, t in WORDS.values()]
        assert q.answer_word in WORDS
        assert len(q.options) == 4 and len(set(q.options)) == 4

    def test_word_to_trans_prompt_is_word(self, zhs_cache):
        questions = build_questions(
            zhs_cache, list(WORDS), rng=random.Random(5), pair="en-zhs"
        )
        q = next(q for q in questions if q.direction == "word->trans")
        assert q.prompt in WORDS
        correct = q.options[q.correct_index]
        assert correct in [t for _, t in WORDS.values()]
