import pytest

from dictcli.models import WordPage
from dictcli.scraper import parse_html


class TestApplePage:
    def test_word_extracted(self, apple_page):
        assert apple_page.word == "apple"

    def test_has_entries(self, apple_page):
        assert len(apple_page.entries) >= 1
        assert apple_page.found

    def test_pos_and_grammar(self, apple_page):
        entry = apple_page.entries[0]
        assert entry.pos == "noun"
        assert entry.grammar is not None and "C" in entry.grammar

    def test_ipa_present(self, apple_page):
        entry = apple_page.entries[0]
        assert entry.ipa_uk and entry.ipa_uk.startswith("/")
        assert entry.ipa_us and entry.ipa_us.startswith("/")

    def test_first_definition(self, apple_page):
        entry = apple_page.entries[0]
        first_def = entry.sense_groups[0].definitions[0]
        assert "round fruit" in first_def.text
        assert first_def.cefr == "A1"

    def test_examples_extracted(self, apple_page):
        entry = apple_page.entries[0]
        all_examples = [
            ex for g in entry.sense_groups for d in g.definitions for ex in d.examples
        ]
        assert any("peel an apple" in ex for ex in all_examples)
        assert any("apple pie" in ex for ex in all_examples)

    def test_american_dictionary_excluded(self, apple_page):
        assert all("edible fruit having" not in d.text
                   for g in apple_page.entries[0].sense_groups
                   for d in g.definitions)


def test_no_entries_returns_suggestions():
    html = "<html><body><div class='pr dictionary'><p>nope</p></div></body></html>"
    page = parse_html(html, word="xyzzy")
    assert not page.found


def test_url_for_sanitizes_slashes():
    from dictcli.scraper import _url_for

    url = _url_for("ward someone/something off", "en")
    assert "%2F" not in url
    assert "ward%20someone-something%20off" in url
