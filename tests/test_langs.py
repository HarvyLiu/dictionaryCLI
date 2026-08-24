from pathlib import Path

import pytest

from dictcli.langs import LANG_PAIRS, resolve_from_tokens, resolve_pair
from dictcli.scraper import parse_html

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def zhs_page():
    html = (FIXTURES / "apple_zhs.html").read_text(encoding="utf-8")
    return parse_html(html, word="apple")


class TestRegistry:
    def test_all_codes_unique_with_paths(self):
        for code, pair in LANG_PAIRS.items():
            assert pair.code == code
            assert pair.path
            assert pair.name

    def test_resolve_direct(self):
        assert resolve_pair("en-zhs").path == "english-chinese-simplified"
        assert resolve_pair("EN") is not None
        assert resolve_pair("nope") is None

    def test_resolve_from_two_tokens(self):
        assert resolve_from_tokens(["en", "zhs"]).code == "en-zhs"
        assert resolve_from_tokens(["en", "zht"]).code == "en-zht"

    def test_aliases(self):
        assert resolve_from_tokens(["us", "zh"]).code == "en-zhs"
        assert resolve_from_tokens(["en", "zh-hant"]).code == "en-zht"
        assert resolve_from_tokens(["en-zhs"]).code == "en-zhs"


class TestBilingualParse:
    def test_word_extracted(self, zhs_page):
        assert zhs_page.word == "apple"
        assert zhs_page.found

    def test_translation_extracted(self, zhs_page):
        entry = zhs_page.entries[0]
        all_translations = [
            t for g in entry.sense_groups for d in g.definitions for t in d.translations
        ]
        assert any("苹果" in t for t in all_translations)

    def test_pos_and_ipa_still_parsed(self, zhs_page):
        entry = zhs_page.entries[0]
        assert entry.pos == "noun"
        assert entry.ipa_uk

    def test_example_with_translation(self, zhs_page):
        entry = zhs_page.entries[0]
        examples = [
            ex for g in entry.sense_groups for d in g.definitions for ex in d.examples
        ]
        assert any("peel an apple" in ex and "削苹果" in ex for ex in examples)

    def test_cache_roundtrip_with_translations(self, zhs_page, tmp_path):
        from dictcli.cache import Cache

        cache = Cache(base_dir=tmp_path, enabled=True)
        assert cache.save_page(zhs_page, pair="en-zhs") is True
        loaded = cache.load_word("apple", pair="en-zhs")
        assert loaded is not None and loaded.found
        translations = [
            t for g in loaded.entries[0].sense_groups
            for d in g.definitions for t in d.translations
        ]
        assert any("苹果" in t for t in translations)

    def test_cache_keys_separated_per_lang(self, tmp_path):
        from dictcli.cache import cache_key

        assert cache_key("apple") == "apple"
        assert cache_key("apple", "en-zhs") == "apple.en-zhs"
        assert cache_key("give up", "ja") == "give-up.ja"
