from pathlib import Path

import pytest

from dictcli.scraper import parse_html

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def foist_page():
    html = (FIXTURES / "foist.html").read_text(encoding="utf-8")
    return parse_html(html, word="foist")


class TestPhraseEntryWithoutPrClass:
    """Regression: entries like 'foist' redirect to phrase pages whose
    entry wrapper lacks the 'pr' class (entry-body__el clrd js-share-holder)."""

    def test_entries_found(self, foist_page):
        assert foist_page.found
        assert len(foist_page.entries) >= 1

    def test_headword_is_phrase(self, foist_page):
        assert foist_page.word == "foist something on someone"

    def test_definitions_and_examples(self, foist_page):
        entry = foist_page.entries[0]
        defs = [d for g in entry.sense_groups for d in g.definitions]
        assert any("force" in d.text or "impose" in d.text or "unwanted" in d.text for d in defs)
        assert any(d.examples for d in defs)

    def test_pos_parsed(self, foist_page):
        pos = foist_page.entries[0].pos
        assert pos is not None and "verb" in pos.lower()
