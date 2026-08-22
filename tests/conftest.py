from pathlib import Path

import pytest

from dictcli.scraper import parse_html

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def apple_page():
    html = (FIXTURES / "apple.html").read_text(encoding="utf-8")
    return parse_html(html, word="apple")
