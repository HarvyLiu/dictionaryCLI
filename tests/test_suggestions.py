from dictcli.scraper import _parse_suggestions


def test_parses_words_from_autocomplete_json():
    data = [
        {"word": "appellant", "url": "/search/direct/?datasetsearch=english&q=appellant", "beta": False},
        {"word": "appellate", "url": "/x", "beta": False},
        {"word": "appellate court", "url": "/y", "beta": True},
    ]
    assert _parse_suggestions(data) == ["appellant", "appellate", "appellate court"]


def test_dedupes_and_strips_whitespace():
    data = [{"word": " run "}, {"word": "run"}, {"word": "  runner"}]
    assert _parse_suggestions(data) == ["run", "runner"]


def test_respects_limit():
    data = [{"word": f"w{i}"} for i in range(20)]
    assert len(_parse_suggestions(data, limit=5)) == 5


def test_skips_empty_and_bad_items():
    data = [{"word": ""}, {"other": 1}, "not-a-dict", {"word": "ok"}]
    assert _parse_suggestions(data) == ["ok"]


def test_non_list_payload_returns_empty():
    assert _parse_suggestions(None) == []
    assert _parse_suggestions({"error": True}) == []
