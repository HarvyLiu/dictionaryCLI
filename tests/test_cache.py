import json

import pytest

from dictcli.cache import Cache, slugify
from dictcli.models import Definition, Entry, SenseGroup, WordPage
from dictcli.scraper import parse_html
from tests.test_scraper import FIXTURES


@pytest.fixture()
def cache(tmp_path):
    return Cache(base_dir=tmp_path, enabled=True)


@pytest.fixture(scope="module")
def apple_page() -> WordPage:
    html = (FIXTURES / "apple.html").read_text(encoding="utf-8")
    return parse_html(html, word="apple")


class TestSlugify:
    def test_basic(self):
        assert slugify("Apple") == "apple"

    def test_phrase(self):
        assert slugify("give up") == "give-up"

    def test_strips_illegal_windows_chars(self):
        assert "/" not in slugify('a/b:c*d?"e<f>g|h')
        assert "\\" not in slugify("back\\slash")

    def test_empty_falls_back(self):
        assert slugify("!!!") == "_"


class TestCacheRoundtrip:
    def test_save_and_load(self, cache, apple_page):
        assert cache.save_page(apple_page) is True
        loaded = cache.load_word("apple")
        assert loaded is not None and loaded.found
        assert loaded.word == "apple"
        orig, back = apple_page.entries[0], loaded.entries[0]
        assert back.pos == orig.pos
        assert back.grammar == orig.grammar
        assert back.ipa_uk == orig.ipa_uk
        assert back.sense_groups[0].definitions[0].text == (
            orig.sense_groups[0].definitions[0].text
        )
        assert back.sense_groups[0].definitions[0].examples == (
            orig.sense_groups[0].definitions[0].examples
        )
        assert back.sense_groups[0].definitions[0].cefr == "A1"

    def test_load_missing_returns_none(self, cache):
        assert cache.load_word("never-saved") is None

    def test_has(self, cache, apple_page):
        assert not cache.has("apple")
        cache.save_page(apple_page)
        assert cache.has("apple")

    def test_refuses_to_save_not_found_pages(self, cache):
        empty = WordPage(word="xyzzy")
        assert cache.save_page(empty) is False


class TestDisabledByDefault:
    def test_default_disabled(self, tmp_path, monkeypatch):
        monkeypatch.setattr("dictcli.cache.default_dir", lambda: tmp_path)
        c = Cache()
        assert c.enabled is False

    def test_disabled_cache_does_not_write(self, tmp_path):
        c = Cache(base_dir=tmp_path, enabled=False)
        page = WordPage(word="apple", entries=[Entry(pos="noun")])
        assert c.save_page(page) is False
        assert not (tmp_path / "words").exists()


class TestManagement:
    def test_set_enabled_persists(self, tmp_path):
        c1 = Cache(base_dir=tmp_path, enabled=False)
        c1.set_enabled(True)
        c2 = Cache(base_dir=tmp_path)
        assert c2.enabled is True
        c2.set_enabled(False)
        assert Cache(base_dir=tmp_path).enabled is False

    def test_clear(self, cache, apple_page):
        cache.save_page(apple_page)
        assert cache.stats()["count"] == 1
        assert cache.clear() == 1
        assert cache.stats()["count"] == 0

    def test_stats_size(self, cache, apple_page):
        cache.save_page(apple_page)
        stats = cache.stats()
        assert stats["size_bytes"] > 0

    def test_cached_words_list(self, cache, apple_page):
        cache.save_page(apple_page)
        assert cache.cached_words() == ["apple"]

    def test_nearest_fuzzy_match(self, cache, apple_page):
        cache.save_page(apple_page)
        nearest = cache.nearest("aple")
        assert "apple" in nearest


class TestCorruptFiles:
    def test_corrupt_json_tolerated(self, cache):
        cache.words_dir.mkdir(parents=True)
        (cache.words_dir / "broken.json").write_text("{not json", encoding="utf-8")
        assert cache.load_slug("broken") is None
