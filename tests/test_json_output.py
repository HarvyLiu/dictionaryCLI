import json

import pytest

import dictcli.cli as cli
from dictcli.models import WordPage


class TestJsonLookup:
    def test_found_word_outputs_json(self, monkeypatch, apple_page, capsys):
        monkeypatch.setattr(cli, "fetch_word", lambda w, pair="en": apple_page)
        rc, word = cli._lookup_full("apple", as_json=True)

        assert rc == 0
        assert word == "apple"
        data = json.loads(capsys.readouterr().out)
        assert data["found"] is True
        assert data["word"] == "apple"
        assert data["entries"][0]["pos"] == "noun"

    def test_not_found_includes_suggestions(self, monkeypatch, capsys):
        page = WordPage(word="zzz")
        monkeypatch.setattr(cli, "fetch_word", lambda w, pair="en": page)
        monkeypatch.setattr(cli, "suggest_words", lambda w, limit=5: ["applesauce"])

        rc, _ = cli._lookup_full("zzz", as_json=True)

        assert rc == 1
        data = json.loads(capsys.readouterr().out)
        assert data["found"] is False
        assert data["suggestions"] == ["applesauce"]

    def test_network_error_json(self, monkeypatch, capsys):
        from dictcli.scraper import NetworkError

        def boom(w, pair="en"):
            raise NetworkError("offline")

        monkeypatch.setattr(cli, "fetch_word", boom)
        rc, _ = cli._lookup_full("x", as_json=True)

        assert rc == 2
        data = json.loads(capsys.readouterr().out)
        assert data["ok"] is False
        assert "error" in data


class TestJsonSearch:
    def test_candidates_json(self, monkeypatch, capsys):
        monkeypatch.setattr(cli, "suggest_words", lambda q, limit=5: ["aa", "bb"])
        rc = cli._search("query", None, interactive=False, as_json=True)

        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert data == {"query": "query", "candidates": ["aa", "bb"]}

    def test_no_matches_json(self, monkeypatch, capsys):
        monkeypatch.setattr(cli, "suggest_words", lambda q, limit=5: [])
        rc = cli._search("nothing", None, interactive=False, as_json=True)

        assert rc == 1
        data = json.loads(capsys.readouterr().out)
        assert data["candidates"] == []
