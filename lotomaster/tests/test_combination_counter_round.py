import unittest

from fastapi.testclient import TestClient

from lotomaster.api import app
from lotomaster.combination_counter import count_lotofacil_combinations


class CombinationCounterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_reference_examples(self):
        cases = [
            (15, 10, 8, "21"),
            (15, 8, 7, "120"),
            (15, 0, 7, "816"),
            (15, 9, 6, "210"),
        ]
        for p, f, r, expected in cases:
            with self.subTest(p=p, f=f, r=r):
                self.assertEqual(
                    count_lotofacil_combinations(p, f, r)["combination_count"],
                    expected,
                )

    def test_boundaries(self):
        self.assertEqual(count_lotofacil_combinations(15, 15, 10)["combination_count"], "1")
        self.assertEqual(count_lotofacil_combinations(15, 0, 10)["combination_count"], "1")
        self.assertEqual(count_lotofacil_combinations(20, 0, 5)["combination_count"], "1")
        self.assertEqual(count_lotofacil_combinations(15, 0, 0)["combination_count"], "3268760")

    def test_invalid_values_are_rejected(self):
        invalid = [
            (14, 0, 0), (21, 0, 0),
            (15, -1, 0), (15, 0, -1),
            (15, 16, 0),
            (15, 10, 16),
            (20, 0, 6),
            (15.0, 0, 0), (15, True, 0), ("15", 0, 0),
        ]
        for args in invalid:
            with self.subTest(args=args), self.assertRaises(ValueError):
                count_lotofacil_combinations(*args)

    def test_get_route_contract_and_count_only_disclaimer(self):
        response = self.client.get(
            "/api/v1/lotofacil/combination-count",
            params={"pick_count": 15, "fixed_count": 10, "removed_count": 8},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["combination_count"], "21")
        self.assertEqual(body["formula"], "C(25 - 10 - 8, 15 - 10) = C(7, 5)")
        self.assertEqual(body["available_after_removals"], 17)
        self.assertEqual(body["free_to_choose"], 7)
        self.assertEqual(body["free_picks"], 5)
        self.assertIn("contagem combinatória", body["disclaimer"])
        self.assertIn("não representa chance de prêmio nem garantia", body["disclaimer"])
        self.assertIn("condição de que as dezenas fixas estejam corretas não está demonstrada", body["disclaimer"])
        self.assertNotIn("probability", body)

    def test_route_rejects_invalid_and_non_integer_inputs(self):
        invalid_queries = [
            "pick_count=14&fixed_count=0&removed_count=0",
            "pick_count=15&fixed_count=-1&removed_count=0",
            "pick_count=15&fixed_count=0&removed_count=11",
            "pick_count=15.5&fixed_count=0&removed_count=0",
        ]
        for query in invalid_queries:
            with self.subTest(query=query):
                response = self.client.get(f"/api/v1/lotofacil/combination-count?{query}")
                self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
