import pytest

from dictcli.audio import play_url
from dictcli.scraper import parse_html


class TestAudioExtraction:
    def test_uk_audio_url(self, apple_page):
        entry = apple_page.entries[0]
        assert entry.audio_uk is not None
        assert entry.audio_uk.startswith("https://dictionary.cambridge.org/media/")
        assert entry.audio_uk.endswith(".mp3")

    def test_us_audio_url(self, apple_page):
        assert apple_page.entries[0].audio_us is not None
        assert "/us_pron/" in apple_page.entries[0].audio_us

    def test_missing_audio_is_none(self):
        html = "<html><body><div class='pr dictionary'><p>empty</p></div></body></html>"
        p = parse_html(html, word="x")
        assert not p.entries or all(e.audio_uk is None for e in p.entries)


class TestPlayUrl:
    def test_bad_url_reports_failure(self):
        ok, msg = play_url("https://dictionary.cambridge.org/media/english/nope.mp3")
        assert ok is False
        assert msg

    def test_unreachable_host(self):
        ok, msg = play_url("http://127.0.0.1:9/x.mp3")
        assert ok is False
