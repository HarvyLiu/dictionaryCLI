import time

from dictcli.cache import Cache, Prefetcher


class TestPrefetcherNonBlocking:
    def test_enqueue_does_not_call_network(self, tmp_path, monkeypatch):
        import dictcli.scraper as scraper_mod

        calls = []

        def fake_suggest(*args, **kwargs):
            calls.append(1)
            return ["related"]

        monkeypatch.setattr(scraper_mod, "suggest_words", fake_suggest)

        cache = Cache(base_dir=tmp_path, enabled=True)
        prefetcher = Prefetcher(cache)
        prefetcher.enqueue_related("apple")

        assert calls == []  # no synchronous network call
        assert prefetcher.pending() == 1

    def test_enqueue_returns_fast_even_repeatedly(self, tmp_path):
        cache = Cache(base_dir=tmp_path, enabled=True)
        prefetcher = Prefetcher(cache)
        start = time.perf_counter()
        for _ in range(1000):
            prefetcher.enqueue_related("apple")
        elapsed = time.perf_counter() - start
        assert elapsed < 0.1
        assert prefetcher.pending() == 1  # deduped via _seen

    def test_disabled_cache_never_enqueues(self, tmp_path):
        cache = Cache(base_dir=tmp_path, enabled=False)
        prefetcher = Prefetcher(cache)
        prefetcher.enqueue_related("apple")
        assert prefetcher.pending() == 0
