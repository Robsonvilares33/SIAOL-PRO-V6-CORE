import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from lotomaster.api import app


class LotofacilHistoryNumberSearchTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.draws = [
            {"contest": 3835, "numbers": list(range(1, 16))},
            {"contest": 1352, "numbers": [1, 2, *range(3, 16)]},
            {"contest": 7, "numbers": list(range(2, 17))},
        ]

    def test_returns_draws_containing_every_selected_number(self):
        response = self.client.post(
            "/api/v1/lotofacil/history-number-search",
            json={"numbers": [1, 2], "draws": self.draws},
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["numbers"], [1, 2])
        self.assertEqual([draw["contest"] for draw in body["matching_draws"]], [3835, 1352])
        self.assertEqual(body["match_count"], 2)
        self.assertEqual(body["examined_count"], 3)
        self.assertIn("amostra pode ser parcial", body["disclaimer"])
        self.assertIn("não são verificadas", body["disclaimer"])

    def test_exact_combination_matches_the_same_set_independent_of_order(self):
        response = self.client.post(
            "/api/v1/lotofacil/history-number-search",
            json={"numbers": list(reversed(range(1, 16))), "draws": self.draws, "match_mode": "exact"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["match_mode"], "exact")
        self.assertEqual(body["match_count"], 2)
        self.assertEqual([draw["contest"] for draw in body["matching_draws"]], [3835, 1352])

    def test_excludes_all_returns_only_draws_without_any_selected_number(self):
        draws = [*self.draws, {"contest": 4, "numbers": list(range(3, 18))}]
        response = self.client.post(
            "/api/v1/lotofacil/history-number-search",
            json={"numbers": [1, 2], "draws": draws, "match_mode": "excludes_all"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["match_mode"], "excludes_all")
        self.assertEqual([draw["contest"] for draw in body["matching_draws"]], [4])

    def test_exact_combination_requires_fifteen_selected_numbers(self):
        response = self.client.post(
            "/api/v1/lotofacil/history-number-search",
            json={"numbers": [1, 2], "draws": self.draws, "match_mode": "exact"},
        )
        self.assertEqual(response.status_code, 422)

    def test_unknown_match_mode_is_rejected(self):
        response = self.client.post(
            "/api/v1/lotofacil/history-number-search",
            json={"numbers": [1, 2], "draws": self.draws, "match_mode": "fuzzy"},
        )
        self.assertEqual(response.status_code, 422)

    def test_client_history_is_not_loaded_or_persisted(self):
        with patch("lotomaster.api.storage.save_draw", side_effect=AssertionError("não deve persistir")), \
             patch("lotomaster.api.storage.get_draw", side_effect=AssertionError("não deve ler banco")), \
             patch("lotomaster.api.fetch_draw", side_effect=AssertionError("não deve consultar rede")):
            response = self.client.post(
                "/api/v1/lotofacil/history-number-search",
                json={"numbers": [1], "draws": [self.draws[0]]},
            )
        self.assertEqual(response.status_code, 200, response.text)

    def test_rejects_invalid_number_sets(self):
        for numbers in ([], [1] * 16, [1, 1], [0], [26], [True], [1.5]):
            with self.subTest(numbers=numbers):
                response = self.client.post(
                    "/api/v1/lotofacil/history-number-search",
                    json={"numbers": numbers, "draws": [self.draws[0]]},
                )
                self.assertEqual(response.status_code, 422, response.text)

    def test_rejects_invalid_or_duplicate_draws(self):
        invalid_draws = [
            [],
            [{"contest": 1, "numbers": list(range(1, 15))}],
            [{"contest": True, "numbers": list(range(1, 16))}],
            [{"contest": 1, "numbers": [*range(1, 15), 14]}],
            [self.draws[0], self.draws[0]],
        ]
        for draws in invalid_draws:
            with self.subTest(draws=draws):
                response = self.client.post(
                    "/api/v1/lotofacil/history-number-search",
                    json={"numbers": [1, 2], "draws": draws},
                )
                self.assertEqual(response.status_code, 422, response.text)

    def test_rejects_missing_fields_and_more_than_5000_draws(self):
        missing = self.client.post("/api/v1/lotofacil/history-number-search", json={"numbers": [1]})
        self.assertEqual(missing.status_code, 422)
        over_limit = [{"contest": i, "numbers": list(range(1, 16))} for i in range(1, 5002)]
        response = self.client.post(
            "/api/v1/lotofacil/history-number-search",
            json={"numbers": [1], "draws": over_limit},
        )
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
