"""Regressões para probabilidades hipergeométricas da Lotomania."""
import math
import unittest
from math import comb

from fastapi.testclient import TestClient
from lotomaster.api import app
from lotomaster.engine import ticket_probability


def expected_probability(hits: int) -> float:
    return comb(50, hits) * comb(50, 20 - hits) / comb(100, 20)


class LotomaniaProbabilityTests(unittest.TestCase):
    def test_prize_tier_outcomes_are_symmetric_at_zero_and_twenty_hits(self):
        tiers = ticket_probability("lotomania")["prize_tiers"]
        probability_by_hits = {tier["hits"]: tier["probability"] for tier in tiers}
        self.assertEqual(probability_by_hits[0], probability_by_hits[20])

    def test_complete_hypergeometric_distribution_sums_to_one(self):
        probabilities = [expected_probability(hits) for hits in range(21)]
        self.assertTrue(math.isclose(sum(probabilities), 1.0, rel_tol=0.0, abs_tol=1e-14))

    def test_seven_prize_tiers_match_exact_hypergeometric_formula(self):
        tiers = ticket_probability("lotomania")["prize_tiers"]
        self.assertEqual([tier["hits"] for tier in tiers], [0, 15, 16, 17, 18, 19, 20])
        for tier in tiers:
            with self.subTest(hits=tier["hits"]):
                self.assertTrue(math.isclose(
                    tier["probability"], expected_probability(tier["hits"]),
                    rel_tol=1e-14, abs_tol=0.0,
                ))

    def test_legacy_twenty_hits_probability_fields_are_unchanged(self):
        result = ticket_probability("lotomania")
        legacy = {key: result[key] for key in ("event", "one_in", "percent", "method")}
        self.assertEqual(legacy, {
            "event": "20 acertos",
            "one_in": round(comb(100, 20) / comb(50, 20)),
            "percent": (comb(50, 20) / comb(100, 20)) * 100,
            "method": "Combinações equiprováveis conforme o universo numérico definido para a modalidade.",
        })

    def test_probability_api_exposes_legacy_and_additional_tier_fields(self):
        response = TestClient(app).get("/api/v1/lotomania/probability")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["event"], "20 acertos")
        self.assertEqual([tier["hits"] for tier in payload["prize_tiers"]], [0, 15, 16, 17, 18, 19, 20])


if __name__ == "__main__":
    unittest.main()
