import json
from datetime import datetime, timezone
from pathlib import Path

from .cache import default_dir, slugify

WORDLIST_VERSION = 1


class Wordlist:
    def __init__(self, base_dir: Path | None = None):
        self.dir = Path(base_dir) if base_dir is not None else default_dir()
        self.path = self.dir / "wordlist.json"

    def _read(self) -> dict:
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("words"), list):
                return data
        except (OSError, ValueError):
            pass
        return {"version": WORDLIST_VERSION, "words": []}

    def _write(self, data: dict) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def entries(self) -> list[dict]:
        return self._read()["words"]

    def slugs(self) -> list[str]:
        return [slugify(e.get("word", "")) for e in self.entries()]

    def has(self, word: str) -> bool:
        return slugify(word) in self.slugs()

    def add(self, word: str) -> bool:
        slug = slugify(word)
        if not slug or slug in self.slugs():
            return False
        data = self._read()
        data["words"].append(
            {
                "word": word,
                "added_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        self._write(data)
        return True

    def remove(self, word: str) -> bool:
        slug = slugify(word)
        if slug not in self.slugs():
            return False
        data = self._read()
        data["words"] = [e for e in data["words"] if slugify(e.get("word", "")) != slug]
        self._write(data)
        return True
