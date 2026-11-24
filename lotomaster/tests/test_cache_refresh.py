import threading
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

    def test_failed_refresh_cannot_overwrite_a_concurrent_success(self):
        cached_db = {"contest": 100, "numbers": [1, 2, 3]}
        fresh = {"contest": 101, "numbers": [4, 5, 6]}
        sqlite_read_started = threading.Event()
        release_sqlite_read = threading.Event()
        stale_result = {}

        def fetch_draw(_game):
            if threading.current_thread().name == "stale-refresh":
                raise OSError("rede indisponível")
            return fresh

        def latest_draw(_game):
            sqlite_read_started.set()
            if not release_sqlite_read.wait(timeout=3):
                raise TimeoutError("SQLite test barrier timed out")
            return cached_db

        def run_stale_refresh():
            try:
                stale_result["result"] = engine.latest_result("megasena", refresh=True)
            except Exception as error:
                stale_result["error"] = error

        with (
            patch("lotomaster.engine.fetch_draw", side_effect=fetch_draw),
            patch("lotomaster.engine.storage.latest_draw", side_effect=latest_draw),
            patch("lotomaster.engine.storage.save_draw"),
        ):
            thread = threading.Thread(target=run_stale_refresh, name="stale-refresh")
            thread.start()
            try:
                self.assertTrue(sqlite_read_started.wait(timeout=2))
                fresh_result = engine.latest_result("megasena", refresh=True)
            finally:
                release_sqlite_read.set()
                thread.join(timeout=3)

        self.assertFalse(thread.is_alive())
        self.assertNotIn("error", stale_result)
        self.assertEqual(fresh_result["contest"], 101)
        self.assertEqual(stale_result["result"]["contest"], 101)
        self.assertEqual(stale_result["result"]["source"], "CAIXA via Cloudflare Worker")
        self.assertEqual(engine._latest_cache["megasena"][1]["contest"], 101)

    def _run_overlapping_successful_refreshes(self, delayed_draw, fast_draw):
        engine._latest_cache.clear()
        delayed_at_save = threading.Event()
        release_delayed_save = threading.Event()
        delayed_result = {}

        def fetch_draw(_game):
            if threading.current_thread().name == "delayed-refresh":
                return delayed_draw
            return fast_draw

        def save_draw(_draw):
            if threading.current_thread().name == "delayed-refresh":
                delayed_at_save.set()
                if not release_delayed_save.wait(timeout=3):
                    raise TimeoutError("save_draw test barrier timed out")

        def run_delayed_refresh():
            try:
                delayed_result["result"] = engine.latest_result("megasena", refresh=True)
            except Exception as error:
                delayed_result["error"] = error

        with (
            patch("lotomaster.engine.fetch_draw", side_effect=fetch_draw),
            patch("lotomaster.engine.storage.save_draw", side_effect=save_draw),
        ):
            thread = threading.Thread(target=run_delayed_refresh, name="delayed-refresh")
            thread.start()
            try:
                self.assertTrue(delayed_at_save.wait(timeout=2))
                fast_result = engine.latest_result("megasena", refresh=True)
            finally:
                release_delayed_save.set()
                thread.join(timeout=3)

        self.assertFalse(thread.is_alive())
        self.assertNotIn("error", delayed_result)
        return delayed_result["result"], fast_result

    def test_older_success_finishing_after_newer_keeps_newer(self):
        older = {"contest": 100, "numbers": [1, 2, 3]}
        newer = {"contest": 101, "numbers": [4, 5, 6]}
        delayed_result, fast_result = self._run_overlapping_successful_refreshes(older, newer)

        self.assertEqual(fast_result["contest"], 101)
        self.assertEqual(delayed_result["contest"], 101)
        self.assertEqual(engine._latest_cache["megasena"][1]["contest"], 101)

    def test_newer_success_finishing_after_older_replaces_older(self):
        older = {"contest": 100, "numbers": [1, 2, 3]}
        newer = {"contest": 101, "numbers": [4, 5, 6]}
        delayed_result, fast_result = self._run_overlapping_successful_refreshes(newer, older)

        self.assertEqual(fast_result["contest"], 100)
        self.assertEqual(delayed_result["contest"], 101)
        self.assertEqual(engine._latest_cache["megasena"][1]["contest"], 101)


if __name__ == "__main__":
    unittest.main()
