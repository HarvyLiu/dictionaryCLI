import re
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup

from .models import Definition, Entry, SenseGroup, WordPage

BASE_URL = "https://dictionary.cambridge.org/dictionary/english/{word}"
SITE_URL = "https://dictionary.cambridge.org"
AUTOCOMPLETE_URL = "https://dictionary.cambridge.org/autocomplete/amp?dataset=english&q={query}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

TIMEOUT = 15


class LookupError(Exception):
    pass


class WordNotFoundError(LookupError):
    def __init__(self, word: str, suggestions: list[str] | None = None):
        self.word = word
        self.suggestions = suggestions or []
        super().__init__(f"'{word}' not found in Cambridge Dictionary")


class NetworkError(LookupError):
    pass


def _clean(text: str | None) -> str:
    if text is None:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def _fetch_html(word: str) -> tuple[str, str]:
    url = BASE_URL.format(word=quote(word.lower()))
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise NetworkError(f"Network request failed: {exc}") from exc
    if resp.status_code == 404:
        raise WordNotFoundError(word)
    if resp.status_code != 200:
        raise NetworkError(f"Unexpected status {resp.status_code} from Cambridge")
    return resp.text, url


def fetch_word(word: str) -> WordPage:
    html, url = _fetch_html(word)
    return parse_html(html, word=word, url=url)


def suggest_words(query: str, limit: int = 5) -> list[str]:
    url = AUTOCOMPLETE_URL.format(query=quote(query.lower()))
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise NetworkError(f"Network request failed: {exc}") from exc
    try:
        data = resp.json()
    except ValueError:
        return []
    return _parse_suggestions(data, limit=limit)


def _parse_suggestions(data, limit: int = 5) -> list[str]:
    words: list[str] = []
    if not isinstance(data, list):
        return words
    for item in data:
        if not isinstance(item, dict):
            continue
        w = _clean(item.get("word", ""))
        if w and w not in words:
            words.append(w)
    return words[:limit]


def parse_html(html: str, word: str | None = None, url: str | None = None) -> WordPage:
    soup = BeautifulSoup(html, "html.parser")
    panel = soup.select_one('div.pr.dictionary[data-id="cald4"]')
    if panel is None:
        panel = soup.select_one("div.pr.dictionary")

    page = WordPage(word=word or "", source_url=url)

    if panel is not None:
        title_el = panel.select_one(".di-title .hw.dhw")
        if title_el is not None:
            page.word = _clean(title_el.get_text()) or page.word
        page.entries = [e for el in panel.select("div.pr.entry-body__el") if (e := _parse_entry(el))]

    if not page.entries:
        page.suggestions = []
    return page


def _parse_entry(el) -> Entry:
    entry = Entry()

    pos_el = el.select_one(".posgram .pos.dpos")
    entry.pos = _clean(pos_el.get_text()) if pos_el else None

    gram_el = el.select_one(".posgram .gram.dgram")
    entry.grammar = _clean(gram_el.get_text()) if gram_el else None

    uk = el.select_one("span.uk.dpron-i span.pron.dpron")
    us = el.select_one("span.us.dpron-i span.pron.dpron")
    entry.ipa_uk = _clean(uk.get_text()) if uk else None
    entry.ipa_us = _clean(us.get_text()) if us else None

    entry.audio_uk = _audio_url(el, "span.uk.dpron-i")
    entry.audio_us = _audio_url(el, "span.us.dpron-i")
    entry.synonyms = _parse_synonyms(el)

    for ds in el.select(".pr.dsense"):
        gw_el = ds.select_one(".guideword.dsense_hw") or ds.select_one(".guideword")
        guideword = _clean(gw_el.get_text().strip("≡ ")) if gw_el else None
        group = SenseGroup(guideword=guideword or None)
        for db in ds.select(".def-block.ddef_block"):
            group.definitions.append(_parse_def_block(db))
        if group.definitions:
            entry.sense_groups.append(group)

    if not entry.sense_groups:
        group = SenseGroup()
        for db in el.select(".def-block.ddef_block"):
            group.definitions.append(_parse_def_block(db))
        if group.definitions:
            entry.sense_groups.append(group)

    return entry


def _parse_synonyms(el) -> list[str]:
    synonyms: list[str] = []
    seen: set[str] = set()
    for a in el.select(".daccord_lb li a"):
        href = a.get("href", "")
        if not href.startswith("/thesaurus/") or "/thesaurus/articles/" in href:
            continue
        text = _clean(a.get_text())
        if text and text.lower() not in seen:
            seen.add(text.lower())
            synonyms.append(text)
    return synonyms[:8]


def _audio_url(el, container_sel: str) -> str | None:
    container = el.select_one(container_sel)
    if container is None:
        return None
    src = container.select_one(".daud source[type='audio/mpeg']")
    if src is None or not src.get("src"):
        return None
    return urljoin(SITE_URL, src["src"])


def _parse_def_block(db) -> Definition:
    definition = Definition(text="")

    def_el = db.select_one(".def.ddef_d") or db.select_one(".ddef_d")
    definition.text = _clean(def_el.get_text()).rstrip(":").strip() if def_el else ""

    xref = db.select_one(".def-info .epp-xref.dxref")
    definition.cefr = _clean(xref.get_text()) if xref else None

    labels: list[str] = []
    for sel in (".usage.dusage", ".region.dregion"):
        for lab in db.select(sel):
            t = _clean(lab.get_text())
            if t:
                labels.append(t)
    definition.labels = labels

    body = db.select_one(".def-body.ddef_b")
    examples: list[str] = []
    if body is not None:
        for ex in body.select(".examp.dexamp"):
            eg = ex.select_one(".eg.deg")
            t = _clean((eg or ex).get_text())
            if t:
                examples.append(t)
    definition.examples = examples

    return definition
