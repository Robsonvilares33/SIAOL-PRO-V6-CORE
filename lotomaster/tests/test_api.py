import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from lotomaster.api import app
from lotomaster.caixa import BASE_URL, fetch_draw, normalize_draw


class LotomasterApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_health_and_catalog(self):
        health = self.client.get("/api/v1/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["official_results_source"], "API pública da CAIXA")
        self.assertEqual(health.json()["official_results_transport"], "Cloudflare Worker (proxy somente leitura)")
        self.assertEqual(health.json()["caixa_proxy_url"], BASE_URL)
        self.assertEqual(health.json()["frontend_auto_refresh_minutes"], 5)
        response = self.client.get("/api/v1/lotteries")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 9)

    def test_ai_configuration_asset_is_served_with_application(self):
        page = self.client.get("/")
        module = self.client.get("/assets/ai-assistant.js")
        self.assertEqual(page.status_code, 200)
        self.assertIn("ai-assistant.js", page.text)
        self.assertEqual(module.status_code, 200)
        self.assertIn("gpt-6-astra", module.text)

    def test_fetch_draw_uses_cloudflare_proxy_and_checks_requested_contest(self):
        response = Mock()
        response.json.return_value = {
            "numero": 3801,
            "dataApuracao": "09/10/2026",
            "listaDezenas": [str(number) for number in range(1, 16)],
        }
        with patch("lotomaster.caixa.requests.get", return_value=response) as get:
            draw = fetch_draw("lotofacil", 3801)
        self.assertEqual(get.call_args.args[0], f"{BASE_URL}/lotofacil/3801")
        self.assertNotIn("Origin", get.call_args.kwargs["headers"])
        self.assertEqual(get.call_args.kwargs["timeout"], 18)
        response.raise_for_status.assert_called_once()
        self.assertEqual(draw["contest"], 3801)

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

    def test_simulate_uses_official_draw_supplied_by_browser(self):
        draw = {"game": "megasena", "contest": 50, "draw_date": "01/01/2026", "numbers": [1, 2, 3, 4, 5, 6]}
        with patch("lotomaster.api.latest_result", side_effect=AssertionError("não deve consultar a Caixa")):
            response = self.client.post("/api/v1/megasena/simulate", json={"tickets": [{"numbers": [1, 2, 3, 4, 7, 8]}], "draw": draw})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["contest"], 50)
        self.assertEqual(response.json()["results"][0]["main_hits"], 4)

    def test_assistant_and_analysis_from_official_browser_history(self):
        draws = [
            {"game": "megasena", "contest": 50, "numbers": [1, 2, 3, 4, 5, 6]},
            {"game": "megasena", "contest": 49, "numbers": [1, 7, 8, 9, 10, 11]},
        ]
        with patch("lotomaster.api.list_results", return_value=draws):
            assistant = self.client.get("/api/v1/megasena/assistant?use_gemini=false")
        self.assertEqual(assistant.status_code, 200)
        self.assertEqual(assistant.json()["draws_analyzed"], 2)
        self.assertEqual(assistant.json()["selection_policy"], "uniform_random")
        computed = self.client.post("/api/v1/megasena/statistics/from-draws", json={"draws": draws})
        self.assertEqual(computed.status_code, 200)
        self.assertEqual(computed.json()["latest_contest"], 50)
        wrong_game = self.client.post("/api/v1/quina/statistics/from-draws", json={"draws": draws})
        self.assertEqual(wrong_game.status_code, 422)

    def test_history_cursor_endpoint_returns_caixa_page_metadata(self):
        page = {
            "items": [{"game": "lotomania", "contest": 100, "numbers": list(range(20))}],
            "from_contest": 100,
            "to_contest": 100,
            "expected_count": 1,
            "missing_contests": [],
            "next_before": 100,
        }
        with patch("lotomaster.api.list_history_page", return_value=page) as load:
            response = self.client.get("/api/v1/lotomania/history?limit=1&before=101")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["source"], "CAIXA via Cloudflare Worker")
        self.assertEqual(response.json()["next_before"], 100)
        load.assert_called_once_with("lotomania", limit=1, before=101)

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
