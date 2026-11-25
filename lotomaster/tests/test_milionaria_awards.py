"""Regressão das faixas simples da +Milionária (regras públicas da CAIXA)."""
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from lotomaster.api import app
from lotomaster.engine import simulate_tickets


DRAW = {"game": "maismilionaria", "contest": 407,
        "numbers": [9, 22, 25, 26, 28, 50], "trevos": [2, 3]}


class MillionAwardTests(unittest.TestCase):
    def test_all_simple_hit_combinations(self):
        # Uma aposta simples tem seis dezenas e dois trevos; o sorteio também.
        # Para 4–6 dezenas, 0 e 1 trevo integram a mesma faixa oficial.
        awards = {
            (6, 2): "Faixa 1 · 6 acertos + 2 trevos", (6, 1): "Faixa 2 · 6 acertos + 1 ou nenhum trevo", (6, 0): "Faixa 2 · 6 acertos + 1 ou nenhum trevo",
            (5, 2): "Faixa 3 · 5 acertos + 2 trevos", (5, 1): "Faixa 4 · 5 acertos + 1 ou nenhum trevo", (5, 0): "Faixa 4 · 5 acertos + 1 ou nenhum trevo",
            (4, 2): "Faixa 5 · 4 acertos + 2 trevos", (4, 1): "Faixa 6 · 4 acertos + 1 ou nenhum trevo", (4, 0): "Faixa 6 · 4 acertos + 1 ou nenhum trevo",
            (3, 2): "Faixa 7 · 3 acertos + 2 trevos", (3, 1): "Faixa 8 · 3 acertos + 1 trevo",
            (2, 2): "Faixa 9 · 2 acertos + 2 trevos", (2, 1): "Faixa 10 · 2 acertos + 1 trevo",
        }
        trevos_by_hits = {0: [1, 4], 1: [2, 4], 2: [2, 3]}
        not_drawn = [1, 2, 3, 4, 5, 6]
        for hits in range(7):
            numbers = DRAW["numbers"][:hits] + not_drawn[:6 - hits]
            for trevo_hits, trevos in trevos_by_hits.items():
                with self.subTest(hits=hits, trevo_hits=trevo_hits):
                    ticket = {"numbers": numbers, "bonus": {"trevos": trevos}}
                    result = simulate_tickets("maismilionaria", [ticket], DRAW)[0]
                    self.assertEqual(result["main_hits"], hits)
                    self.assertEqual(result["trevo_hits"], trevo_hits)
                    self.assertEqual(result["award"], awards.get((hits, trevo_hits)))

    def test_reproduced_case_through_api(self):
        ticket = {"numbers": [9, 22, 1, 2, 3, 4], "bonus": {"trevos": [2, 4]}}
        with TestClient(app) as client, patch("lotomaster.api.latest_result", return_value=DRAW):
            response = client.post("/api/v1/maismilionaria/simulate", json={"tickets": [ticket]})
        self.assertEqual(response.status_code, 200)
        result = response.json()["results"][0]
        self.assertEqual((result["main_hits"], result["trevo_hits"], result["award"]),
                         (2, 1, "Faixa 10 · 2 acertos + 1 trevo"))

    def test_multiple_trevos_are_conferenced_as_subbets(self):
        ticket = {"numbers": [9, 22, 1, 2, 3, 4], "bonus": {"trevos": [2, 3, 4]}}
        result = simulate_tickets("maismilionaria", [ticket], DRAW)[0]
        self.assertEqual(result["subbets_total"], 3)
        self.assertEqual(result["award_counts"], {
            "Faixa 9 · 2 acertos + 2 trevos": 1,
            "Faixa 10 · 2 acertos + 1 trevo": 2,
        })
        with TestClient(app) as client, patch("lotomaster.api.latest_result", return_value=DRAW):
            response = client.post("/api/v1/maismilionaria/simulate", json={"tickets": [ticket]})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["results"][0]["subbets_total"], 3)

    def test_number_count_above_official_multiple_limit_is_rejected(self):
        ticket = {"numbers": list(range(1, 14)), "bonus": {"trevos": [2, 3]}}
        with self.assertRaises(ValueError):
            simulate_tickets("maismilionaria", [ticket], DRAW)


if __name__ == "__main__":
    unittest.main()
