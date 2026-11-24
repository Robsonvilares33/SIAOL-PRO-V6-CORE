import time
import unittest
from unittest.mock import patch

from lotomaster import engine


class LatestResultCacheTests(unittest.TestCase):
    def setUp(self):
        self.original_cache = engine._latest_cache.copy()
        engine._latest_cache.clear()
        self.addCleanup(self._restore_cache)

    def _restore_cache(self):
        engine._latest_cache.clear()
        engine._latest_cache.update(self.original_cache)

    def test_refresh_true_fetches_caixa_even_with_recent_memory_cache(self):
        cached = {"contest": 100, "numbers": [1, 2, 3]}
        fresh = {"contest": 101, "numbers": [4, 5, 6]}
        engine._latest_cache["megasena"] = (time.monotonic(), cached)

        with (
            patch("lotomaster.engine.storage.latest_draw", return_value=cached),
            patch("lotomaster.engine.fetch_draw", return_value=fresh) as fetch,
            patch("lotomaster.engine.storage.save_draw") as save,
        ):
            result = engine.latest_result("megasena", refresh=True)

        fetch.assert_called_once_with("megasena")
        save.assert_called_once_with(fresh)
        self.assertEqual(result["contest"], 101)
        self.assertEqual(result["source"], "CAIXA via Cloudflare Worker")

    def test_refresh_false_returns_recent_memory_cache_without_fetching(self):
        cached = {"contest": 100, "numbers": [1, 2, 3]}
        engine._latest_cache["megasena"] = (time.monotonic(), cached)

        with (
            patch("lotomaster.engine.storage.latest_draw") as latest_draw,
            patch("lotomaster.engine.fetch_draw") as fetch,
        ):
            result = engine.latest_result("megasena", refresh=False)

        latest_draw.assert_not_called()
        fetch.assert_not_called()
        self.assertEqual(result["contest"], 100)
        self.assertEqual(result["source"], "cache")

    def test_refresh_failure_falls_back_to_sqlite_with_warning(self):
        cached_db = {"contest": 100, "numbers": [1, 2, 3]}
        engine._latest_cache["megasena"] = (time.monotonic(), {"contest": 99, "numbers": [7, 8, 9]})

        with (
            patch("lotomaster.engine.storage.latest_draw", return_value=cached_db),
            patch("lotomaster.engine.fetch_draw", side_effect=OSError("rede indisponível")) as fetch,
        ):
            result = engine.latest_result("megasena", refresh=True)

        fetch.assert_called_once_with("megasena")
        self.assertEqual(result["contest"], 100)
        self.assertEqual(result["source"], "cache")
        self.assertEqual(
            result["warning"],
            "A CAIXA está temporariamente indisponível; o resultado em cache pode estar desatualizado.",
        )
        self.assertNotIn("rede indisponível", result["warning"])


if __name__ == "__main__":
    unittest.main()
