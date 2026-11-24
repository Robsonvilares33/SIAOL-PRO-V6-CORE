import itertools
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from lotomaster import storage
from lotomaster.api import app
from lotomaster.repeated_closure import repeated_closure

PREVIOUS = [2, 3, 4, 5, 9, 10, 12, 13, 15, 16, 17, 18, 19, 21, 22]
REPEATED = [3, 4, 5, 9, 15, 16, 19, 21, 22]
ABSENT = [1, 6, 7, 8, 11, 14, 20, 23, 24, 25]


class RepeatedClosureUnitTests(unittest.TestCase):
    def test_observed_example_full_set_and_first_game(self):
        result = repeated_closure(PREVIOUS, REPEATED)
        expected = {
            tuple(sorted((*REPEATED, *choice)))
            for choice in itertools.combinations(ABSENT, 6)
        }
        actual = {tuple(game) for game in result["games"]}
        self.assertEqual(result["game_count"], 210)
        self.assertEqual(len(result["games"]), 210)
        self.assertEqual(len(actual), 210)
        self.assertEqual(actual, expected)
        self.assertEqual(result["games"][0], [1, 3, 4, 5, 6, 7, 8, 9, 11, 14, 15, 16, 19, 21, 22])
        self.assertTrue(all(len(game) == 15 and len(set(game)) == 15 for game in result["games"]))
        self.assertIn("não garante prêmio", result["disclaimer"])

    def test_validation(self):
        invalid = [
            ([True] + PREVIOUS[1:], REPEATED),
            ([1, 2], REPEATED),
            (PREVIOUS[:-1] + [25, 25], REPEATED),
            (PREVIOUS, REPEATED[:5]),
            (PREVIOUS, REPEATED + [3]),
            (PREVIOUS, REPEATED[:-1] + [1]),
            (PREVIOUS, REPEATED + [True]),
            (PREVIOUS, REPEATED + [26]),
        ]
        for draw, repeated in invalid:
            with self.subTest(draw=draw, repeated=repeated), self.assertRaises(ValueError):
                repeated_closure(draw, repeated)

    def test_pagination_matches_full_lexicographic_result(self):
        full = repeated_closure(PREVIOUS, REPEATED)
        first = repeated_closure(PREVIOUS, REPEATED, page_size=7)
        second = repeated_closure(PREVIOUS, REPEATED, offset=7, page_size=7)
        self.assertEqual(first["candidate_count"], 210)
        self.assertEqual(first["returned_count"], 7)
        self.assertEqual(first["next_offset"], 7)
        self.assertEqual(first["games"], full["games"][:7])
        self.assertEqual(second["games"], full["games"][7:14])
        self.assertEqual(second["offset"], 7)

    def test_reports_all_filter_failures_and_requires_reference_for_repeated_filter(self):
        filters = {"min_sum": 300, "min_even": 15, "min_prime": 15}
        item = repeated_closure(PREVIOUS, REPEATED, filters=filters, page_size=1)["items"][0]
        self.assertFalse(item["approved"])
        self.assertEqual(len(item["reasons"]), 3)
        with self.assertRaisesRegex(ValueError, "referência explícito"):
            repeated_closure(PREVIOUS, REPEATED, filters={"min_repeated": 3})
        checked = repeated_closure(
            PREVIOUS, REPEATED, filters={"min_repeated": 15},
            reference_draw=PREVIOUS, page_size=1,
        )
        self.assertIn("Repetidas", checked["items"][0]["reasons"][0])


class RepeatedClosureApiTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(storage, "DB_PATH", Path(self.tempdir.name) / "test.sqlite3")
        self.db_patch.start()
        self.initialized_patch = patch.object(storage, "_initialized", False)
        self.initialized_patch.start()
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        self.initialized_patch.stop()
        self.db_patch.stop()
        self.tempdir.cleanup()

    def test_endpoint_example_and_no_data_written(self):
        response = self.client.post("/api/v1/lotofacil/closures/repeated", json={
            "previous_draw": PREVIOUS,
            "repeated": REPEATED,
        })
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(result["game_count"], 210)
        self.assertEqual(len(set(map(tuple, result["games"]))), 210)
        self.assertEqual(result["games"][0], [1, 3, 4, 5, 6, 7, 8, 9, 11, 14, 15, 16, 19, 21, 22])
        self.assertEqual(storage.list_draws("lotofacil"), [])
        self.assertIn("não garante prêmio", result["disclaimer"])

    def test_endpoint_rejects_invalid_inputs_and_boolean(self):
        for payload in (
            {"previous_draw": PREVIOUS, "repeated": REPEATED + [True]},
            {"previous_draw": PREVIOUS[:-1], "repeated": REPEATED},
            {"previous_draw": PREVIOUS, "repeated": REPEATED[:5]},
            {"previous_draw": PREVIOUS, "repeated": REPEATED + [3]},
            {"previous_draw": [True] + PREVIOUS[1:], "repeated": REPEATED},
        ):
            with self.subTest(payload=payload):
                response = self.client.post("/api/v1/lotofacil/closures/repeated", json=payload)
                self.assertEqual(response.status_code, 422)

    def test_endpoint_pages_closure_and_fetches_reference_only_for_repeat_filter(self):
        payload = {"previous_draw": PREVIOUS, "repeated": REPEATED, "page_size": 10, "offset": 10}
        with patch("lotomaster.api._reference_draw", side_effect=AssertionError("filtro não requer referência")):
            response = self.client.post("/api/v1/lotofacil/closures/repeated", json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["offset"], 10)
        self.assertEqual(data["returned_count"], 10)
        self.assertEqual(data["next_offset"], 20)

        reference_draw = {"contest": 100, "numbers": PREVIOUS}
        with patch("lotomaster.api._reference_draw", return_value=reference_draw) as reference:
            filtered = self.client.post("/api/v1/lotofacil/closures/repeated", json={
                **payload, "offset": 0, "filters": {"min_repeated": 3}, "reference_contest": 100,
            })
        self.assertEqual(filtered.status_code, 200, filtered.text)
        self.assertEqual(filtered.json()["reference_contest"], 100)
        reference.assert_called_once_with("lotofacil", 100)

    def test_endpoint_rejects_repeat_filter_without_reference_without_fetch(self):
        with patch("lotomaster.api._reference_draw") as reference:
            response = self.client.post("/api/v1/lotofacil/closures/repeated", json={
                "previous_draw": PREVIOUS, "repeated": REPEATED,
                "filters": {"min_repeated": 3},
            })
        self.assertEqual(response.status_code, 422)
        self.assertIn("referência explícito", response.json()["detail"])
        reference.assert_not_called()


if __name__ == "__main__":
    unittest.main()
