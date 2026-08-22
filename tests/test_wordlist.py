import pytest

import dictcli.cli as cli
from dictcli.cache import Cache
from dictcli.wordlist import Wordlist

from tests.test_scraper import FIXTURES, parse_html


@pytest.fixture()
def wl(tmp_path):
    return Wordlist(base_dir=tmp_path)


class TestWordlistStorage:
    def test_add_and_has(self, wl):
        assert wl.add("apple") is True
        assert wl.has("apple") is True
        assert wl.has("Apple") is True

    def test_duplicate_ignored(self, wl):
        wl.add("apple")
        assert wl.add("APPLE") is False
        assert len(wl.entries()) == 1

    def test_remove(self, wl):
        wl.add("give up")
        assert wl.remove("Give Up") is True
        assert wl.has("give up") is False
        assert wl.remove("never added") is False

    def test_persists_across_instances(self, tmp_path):
        w1 = Wordlist(base_dir=tmp_path)
        w1.add("serendipity")
        w2 = Wordlist(base_dir=tmp_path)
        assert [e["word"] for e in w2.entries()] == ["serendipity"]

    def test_entries_have_timestamp(self, wl):
        wl.add("apple")
        entry = wl.entries()[0]
        assert "added_at" in entry


@pytest.fixture(scope="module")
def apple_page():
    html = (FIXTURES / "apple.html").read_text(encoding="utf-8")
    return parse_html(html, word="apple")


class TestAddFlow:
    def test_add_caches_even_when_cache_disabled(self, tmp_path, monkeypatch, apple_page):
        cache = Cache(base_dir=tmp_path / "c", enabled=False)
        monkeypatch.setattr("dictcli.cache.default_dir", lambda: tmp_path / "c")
        monkeypatch.setattr("dictcli.wordlist.default_dir", lambda: tmp_path)
        monkeypatch.setattr(cli, "fetch_word", lambda w: apple_page)

        rc = cli._add_word("apple")

        assert rc == 0
        wordlist = Wordlist(base_dir=tmp_path)
        assert wordlist.has("apple") is True
        forced_cache = Cache(base_dir=tmp_path / "c", enabled=False)
        assert forced_cache.load_word("apple") is not None

    def test_add_unknown_word_fails(self, tmp_path, monkeypatch):
        from dictcli.models import WordPage

        monkeypatch.setattr("dictcli.cache.default_dir", lambda: tmp_path / "c")
        monkeypatch.setattr("dictcli.wordlist.default_dir", lambda: tmp_path)
        monkeypatch.setattr(
            cli,
            "fetch_word",
            lambda w: WordPage(word=w),
        )
        monkeypatch.setattr(cli, "suggest_words", lambda w, limit=5: ["applesauce"])

        rc = cli._add_word("zzznotaword")
        assert rc == 1
        assert not Wordlist(base_dir=tmp_path).has("zzznotaword")

    def test_readd_reports_already_starred(self, tmp_path, monkeypatch, apple_page):
        monkeypatch.setattr("dictcli.cache.default_dir", lambda: tmp_path / "c")
        monkeypatch.setattr("dictcli.wordlist.default_dir", lambda: tmp_path)
        monkeypatch.setattr(cli, "fetch_word", lambda w: apple_page)

        cli._add_word("apple")
        rc = cli._add_word("apple")
        assert rc == 0
        assert len(Wordlist(base_dir=tmp_path).entries()) == 1


class TestRemoveFlow:
    def test_cli_remove_uses_default_dirs(self, tmp_path, monkeypatch):
        monkeypatch.setattr("dictcli.cache.default_dir", lambda: tmp_path)
        monkeypatch.setattr("dictcli.wordlist.default_dir", lambda: tmp_path)
        Wordlist(base_dir=tmp_path).add("apple")
        assert cli._remove_word("apple") == 0
        assert not Wordlist(base_dir=tmp_path).has("apple")

    def test_cli_remove_unknown_errors(self, tmp_path, monkeypatch):
        monkeypatch.setattr("dictcli.cache.default_dir", lambda: tmp_path)
        monkeypatch.setattr("dictcli.wordlist.default_dir", lambda: tmp_path)
        assert cli._remove_word("ghost") == 1
