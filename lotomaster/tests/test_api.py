import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from lotomaster.api import app
from lotomaster.caixa import normalize_draw


class LotomasterApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_health_and_catalog(self):
        self.assertEqual(self.client.get("/api/v1/health").status_code, 200)
        response = self.client.get("/api/v1/lotteries")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 9)

    def test_generate_and_simulate(self):
        generated = self.client.post("/api/v1/lotofacil/generate", json={"count": 2, "seed": 20})
        self.assertEqual(generated.status_code, 200)
        self.assertEqual(generated.json()["count"], 2)
        draw = {"game": "megasena", "contest": 1, "draw_date": "01/01/2026", "numbers": [1, 2, 3, 4, 5, 6], "second_numbers": [], "trevos": [], "month": None, "team": None}
        with patch("lotomaster.api.latest_result", return_value=draw):
            response = self.client.post("/api/v1/megasena/simulate", json={"tickets": [{"numbers": [1, 2, 3, 4, 7, 8]}]})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["results"][0]["main_hits"], 4)
            invalid = self.client.post("/api/v1/megasena/simulate", json={"tickets": [{"numbers": [1, 2, 3, 4, 5]}]})
            self.assertEqual(invalid.status_code, 422)

    def test_day_of_fortune_generate_rejects_month_thirteen(self):
        response = self.client.post("/api/v1/diadesorte/generate", json={"bonus": {"month": 13}})
        self.assertEqual(response.status_code, 422)
        self.assertIn("Mês da Sorte", response.json()["detail"])

    def test_milionaria_simulate_requires_trevos(self):
        draw = {"game": "maismilionaria", "contest": 1, "draw_date": "01/01/2026", "numbers": [1, 2, 3, 4, 5, 6], "trevos": [1, 2]}
        with patch("lotomaster.api.latest_result", return_value=draw):
            missing_trevos = self.client.post("/api/v1/maismilionaria/simulate", json={"tickets": [{"numbers": [1, 2, 3, 4, 5, 6]}]})
            valid_ticket = self.client.post("/api/v1/maismilionaria/simulate", json={"tickets": [{"numbers": [1, 2, 3, 4, 5, 6], "bonus": {"trevos": [1, 2]}}]})
        self.assertEqual(missing_trevos.status_code, 422)
        self.assertIn("trevos", missing_trevos.json()["detail"])
        self.assertEqual(valid_ticket.status_code, 200)
        self.assertEqual(valid_ticket.json()["results"][0]["award"], "6 acertos + 2 trevos")

    def test_csv_and_txt_exports(self):
        sample = [{"contest": 50, "draw_date": "01/01/2026", "numbers": [1, 2, 3, 4, 5, 6], "second_numbers": [], "trevos": [], "month": None, "team": None, "accumulated": False, "estimated_prize": 1000}]
        with patch("lotomaster.api.list_results", return_value=sample):
            csv_response = self.client.get("/api/v1/megasena/export.csv?limit=1")
            txt_response = self.client.get("/api/v1/megasena/export.txt?limit=1")
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn("Concurso", csv_response.text)
        self.assertEqual(txt_response.status_code, 200)
        self.assertIn("Concurso 50", txt_response.text)

    def test_special_draw_flag_is_normalized(self):
        draw = normalize_draw("lotofacil", {"numero": 99, "listaDezenas": [str(i) for i in range(1, 16)], "indicadorConcursoEspecial": 1, "tipoJogo": "especial"})
        self.assertTrue(draw["special_draw"])
        self.assertEqual(draw["contest_type"], "especial")


if __name__ == "__main__":
    unittest.main()
