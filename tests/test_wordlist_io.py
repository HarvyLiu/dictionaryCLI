import pytest

from dictcli.wordlist import Wordlist


@pytest.fixture()
def wl(tmp_path):
    return Wordlist(base_dir=tmp_path)


class TestExportImport:
    def test_export_writes_one_word_per_line(self, tmp_path, monkeypatch):
        import dictcli.cli as cli

        monkeypatch.setattr("dictcli.wordlist.default_dir", lambda: tmp_path)
        wl = Wordlist(base_dir=tmp_path)
        wl.add("apple")
        wl.add("give up")

        out = tmp_path / "out.txt"
        assert cli._export_words(str(out)) == 0
        lines = out.read_text(encoding="utf-8").splitlines()
        assert lines == ["apple", "give up"]

    def test_export_empty_list_fails(self, tmp_path, monkeypatch):
        import dictcli.cli as cli

        monkeypatch.setattr("dictcli.wordlist.default_dir", lambda: tmp_path)
        assert cli._export_words(str(tmp_path / "o.txt")) == 1

    def test_import_parses_comments_and_blanks(self, tmp_path, monkeypatch):
        import dictcli.cli as cli

        monkeypatch.setattr("dictcli.cache.default_dir", lambda: tmp_path / "c")
        monkeypatch.setattr("dictcli.wordlist.default_dir", lambda: tmp_path)

        src = tmp_path / "words.txt"
        src.write_text(
            "# my vocab\n\napple\ngive up\n# comment\n  banana  \n",
            encoding="utf-8",
        )
        rc = cli._import_words(str(src), fetch=False)

        assert rc == 0
        wordlist = Wordlist(base_dir=tmp_path)
        assert wordlist.has("apple") is True
        assert wordlist.has("give up") is True
        assert wordlist.has("banana") is True
        assert len(wordlist.entries()) == 3

    def test_import_skips_duplicates(self, tmp_path, monkeypatch):
        import dictcli.cli as cli

        monkeypatch.setattr("dictcli.cache.default_dir", lambda: tmp_path / "c")
        monkeypatch.setattr("dictcli.wordlist.default_dir", lambda: tmp_path)

        wl = Wordlist(base_dir=tmp_path)
        wl.add("apple")

        src = tmp_path / "words.txt"
        src.write_text("apple\nAPPLE\npear\n", encoding="utf-8")
        cli._import_words(str(src), fetch=False)

        entries = Wordlist(base_dir=tmp_path).entries()
        assert [e["word"] for e in entries] == ["apple", "pear"]

    def test_import_missing_file_errors(self, tmp_path, monkeypatch):
        import dictcli.cli as cli

        monkeypatch.setattr("dictcli.wordlist.default_dir", lambda: tmp_path)
        assert cli._import_words(str(tmp_path / "nope.txt")) == 2

    def test_roundtrip_export_then_import(self, tmp_path, monkeypatch):
        import dictcli.cli as cli

        src_dir = tmp_path / "a"
        dst_dir = tmp_path / "b"
        Wordlist(base_dir=src_dir).add("apple")
        Wordlist(base_dir=src_dir).add("run away")

        out = tmp_path / "shared.txt"
        monkeypatch.setattr("dictcli.wordlist.default_dir", lambda: src_dir)
        assert cli._export_words(str(out)) == 0

        monkeypatch.setattr("dictcli.cache.default_dir", lambda: tmp_path / "c")
        monkeypatch.setattr("dictcli.wordlist.default_dir", lambda: dst_dir)
        assert cli._import_words(str(out), fetch=False) == 0

        imported = {e["word"] for e in Wordlist(base_dir=dst_dir).entries()}
        assert imported == {"apple", "run away"}
