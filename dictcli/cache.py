import json
import re
import threading
from collections import deque
from datetime import datetime, timezone
from difflib import get_close_matches
from pathlib import Path

from .models import WordPage
from .scraper import fetch_word

CACHE_VERSION = 1


def default_dir() -> Path:
    try:
        from platformdirs import user_data_dir

        return Path(user_data_dir("dictcli", appauthor=False))
    except ImportError:
        return Path.home() / ".dictcli"


def slugify(text: str) -> str:
    s = re.sub(r"[^\w\s-]", "", text.lower().strip(), flags=re.UNICODE)
    s = re.sub(r"[\s_]+", "-", s).strip("-")
    return s or "_"


def cache_key(word: str, pair: str = "en") -> str:
    slug = slugify(word)
    if pair == "en":
        return slug
    return f"{slug}.{pair}"


def get_setting(key: str, default=None):
    try:
        from platformdirs import user_data_dir

        base = Path(user_data_dir("dictcli", appauthor=False))
    except ImportError:
        base = Path.home() / ".dictcli"
    try:
        with open(base / "config.json", encoding="utf-8") as f:
            return json.load(f).get(key, default)
    except (OSError, ValueError):
        return default


def set_setting(key: str, value) -> None:
    try:
        from platformdirs import user_data_dir

        base = Path(user_data_dir("dictcli", appauthor=False))
    except ImportError:
        base = Path.home() / ".dictcli"
    base.mkdir(parents=True, exist_ok=True)
    config = {}
    try:
        with open(base / "config.json", encoding="utf-8") as f:
            config = json.load(f)
    except (OSError, ValueError):
        pass
    config[key] = value
    with open(base / "config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


class Cache:
    def __init__(self, base_dir: Path | None = None, enabled: bool | None = None):
        self.dir = Path(base_dir) if base_dir is not None else default_dir()
        if enabled is not None:
            self.enabled = enabled
        else:
            self.enabled = self._read_config().get("cache_enabled", False)

    @property
    def words_dir(self) -> Path:
        return self.dir / "words"

    @property
    def config_path(self) -> Path:
        return self.dir / "config.json"

    def _read_config(self) -> dict:
        try:
            with open(self.config_path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def _write_config(self, config: dict) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)

    def set_enabled(self, value: bool) -> None:
        config = self._read_config()
        config["cache_enabled"] = value
        self._write_config(config)
        self.enabled = value

    def path_for(self, word: str, pair: str = "en") -> Path:
        return self.words_dir / f"{cache_key(word, pair)}.json"

    def save_page(self, page: WordPage, force: bool = False, pair: str = "en") -> bool:
        if not force and not self.enabled:
            return False
        key = cache_key(page.word, pair)
        if not page.found or not key.strip("."):
            return False
        payload = {
            "cache_version": CACHE_VERSION,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "page": _page_to_dict(page),
        }
        try:
            self.words_dir.mkdir(parents=True, exist_ok=True)
            with open(self.words_dir / f"{key}.json", "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except OSError:
            return False
        return True

    def load_word(self, word: str, pair: str = "en") -> WordPage | None:
        return self.load_slug(cache_key(word, pair))

    def load_slug(self, slug: str) -> WordPage | None:
        try:
            with open(self.words_dir / f"{slug}.json", encoding="utf-8") as f:
                payload = json.load(f)
        except (OSError, ValueError):
            return None
        if not isinstance(payload, dict) or "page" not in payload:
            return None
        return _page_from_dict(payload["page"])

    def has(self, word_or_slug: str, pair: str = "en") -> bool:
        name = cache_key(word_or_slug, pair)
        return (self.words_dir / f"{name}.json").exists()

    def cached_words(self) -> list[str]:
        if not self.words_dir.exists():
            return []
        words = []
        for p in sorted(self.words_dir.glob("*.json")):
            page = self.load_slug(p.stem)
            words.append(page.word if page and page.word else p.stem.replace("-", " "))
        return words

    def nearest(self, word: str, n: int = 5) -> list[str]:
        return get_close_matches(word.lower(), [w.lower() for w in self.cached_words()], n=n)

    def stats(self) -> dict:
        files = list(self.words_dir.glob("*.json")) if self.words_dir.exists() else []
        size = sum(f.stat().st_size for f in files)
        return {"count": len(files), "size_bytes": size}

    def clear(self) -> int:
        removed = 0
        if self.words_dir.exists():
            for f in self.words_dir.glob("*.json"):
                try:
                    f.unlink()
                    removed += 1
                except OSError:
                    pass
        return removed


def _page_to_dict(page: WordPage) -> dict:
    entries = []
    for e in page.entries:
        entries.append(
            {
                "pos": e.pos,
                "grammar": e.grammar,
                "ipa_uk": e.ipa_uk,
                "ipa_us": e.ipa_us,
                "audio_uk": e.audio_uk,
                "audio_us": e.audio_us,
                "synonyms": e.synonyms,
                "sense_groups": [
                    {
                        "guideword": g.guideword,
                        "definitions": [
                            {
                                "text": d.text,
                                "cefr": d.cefr,
                                "labels": d.labels,
                                "examples": d.examples,
                                "translations": d.translations,
                            }
                            for d in g.definitions
                        ],
                    }
                    for g in e.sense_groups
                ],
            }
        )
    return {"word": page.word, "source_url": page.source_url, "entries": entries}


def _page_from_dict(d: dict) -> WordPage:
    page = WordPage(
        word=d.get("word", ""),
        source_url=d.get("source_url"),
    )
    for e in d.get("entries", []):
        entry = _entry_from_dict(e)
        page.entries.append(entry)
    return page


def _entry_from_dict(e: dict):
    from .models import Definition, Entry, SenseGroup

    groups = []
    for g in e.get("sense_groups", []):
        defs = [
            Definition(
                text=d.get("text", ""),
                cefr=d.get("cefr"),
                labels=list(d.get("labels", [])),
                examples=list(d.get("examples", [])),
                translations=list(d.get("translations", [])),
            )
            for d in g.get("definitions", [])
        ]
        groups.append(SenseGroup(guideword=g.get("guideword"), definitions=defs))
    return Entry(
        pos=e.get("pos"),
        grammar=e.get("grammar"),
        ipa_uk=e.get("ipa_uk"),
        ipa_us=e.get("ipa_us"),
        audio_uk=e.get("audio_uk"),
        audio_us=e.get("audio_us"),
        synonyms=list(e.get("synonyms", [])),
        sense_groups=groups,
    )


class Prefetcher:
    """Background worker that slowly downloads related words while the REPL runs.

    Only active when the cache is explicitly enabled by the user.
    """

    def __init__(self, cache: Cache, interval: float = 1.5, max_queue: int = 100):
        self.cache = cache
        self.interval = interval
        self.max_queue = max_queue
        self._queue: deque[str] = deque(maxlen=max_queue)
        self._seen: set[str] = set()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if not self.cache.enabled or (self._thread and self._thread.is_alive()):
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def enqueue_related(self, word: str) -> None:
        if not self.cache.enabled:
            return
        from .scraper import NetworkError, suggest_words

        try:
            related = suggest_words(word, limit=5)
        except NetworkError:
            return
        for w in related:
            slug = slugify(w)
            if slug not in self._seen:
                self._seen.add(slug)
                self._queue.append(w)

    def pending(self) -> int:
        return len(self._queue)

    def _run(self) -> None:
        from .scraper import LookupError

        while not self._stop_event.is_set():
            try:
                word = self._queue.popleft()
            except IndexError:
                if self._stop_event.wait(1.0):
                    break
                continue
            if self.cache.has(word):
                continue
            try:
                page = fetch_word(word)
                if page.found:
                    self.cache.save_page(page)
            except LookupError:
                pass
            if self._stop_event.wait(self.interval):
                break
