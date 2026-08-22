from pathlib import Path

import pytest

from dictcli.scraper import parse_html

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def happy_page():
    html = (FIXTURES / "happy.html").read_text(encoding="utf-8")
    return parse_html(html, word="happy")


class TestSynonyms:
    def test_happy_has_synonyms(self, happy_page):
        syns = [s.lower() for e in happy_page.entries for s in e.synonyms]
        assert "cheerful" in syns
        assert "glad" in syns
        assert "pleased" in syns

    def test_see_more_link_excluded(self, happy_page):
        for e in happy_page.entries:
            assert all("more results" not in s.lower() for s in e.synonyms)

    def test_apple_page_without_box_is_empty(self, apple_page):
        assert all(e.synonyms == [] for e in apple_page.entries)

    def test_cap_at_eight(self):
        from dictcli import scraper

        class FakeA:
            def __init__(self, t):
                self._t = t

            def get(self, k, default=None):
                return "/thesaurus/x"

            def get_text(self):
                return self._t

        class FakeEl:
            def select(self, sel):
                return [FakeA(f"w{i}") for i in range(20)]

        assert len(scraper._parse_synonyms(FakeEl())) == 8
