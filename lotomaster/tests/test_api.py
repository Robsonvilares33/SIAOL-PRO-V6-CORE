import unittest
from math import comb
from io import BytesIO
from unittest.mock import Mock, patch
from zipfile import ZipFile
import xml.etree.ElementTree as ET

from fastapi.testclient import TestClient

from lotomaster.api import app
from lotomaster.caixa import BASE_URL, UpstreamDrawError, fetch_draw, normalize_draw


class LotomasterApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_health_and_catalog(self):
        self.assertFalse(app.debug)
        health = self.client.get("/api/v1/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["official_results_source"], "API pública da CAIXA")
        self.assertEqual(health.json()["official_results_transport"], "Cloudflare Worker (proxy somente leitura)")
        self.assertEqual(health.json()["caixa_proxy_url"], BASE_URL)
        self.assertEqual(health.json()["frontend_auto_refresh_minutes"], 5)
        response = self.client.get("/api/v1/lotteries")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 9)

    def test_public_read_endpoints_hide_internal_exception_messages(self):
        sentinel = "/srv/private/config-and-provider-details"
        cases = [
            ("/api/v1/megasena/latest", "lotomaster.api.latest_result", "Não foi possível obter o resultado mais recente."),
            ("/api/v1/megasena/results", "lotomaster.api.list_results", "Não foi possível consultar os resultados."),
            ("/api/v1/megasena/history", "lotomaster.api.list_history_page", "Não foi possível consultar o histórico."),
            ("/api/v1/megasena/assistant", "lotomaster.api.list_results", "Não foi possível gerar o relatório do assistente."),
        ]
        for endpoint, dependency, expected_detail in cases:
            with self.subTest(endpoint=endpoint), patch(dependency, side_effect=RuntimeError(sentinel)):
                response = self.client.get(endpoint)
            self.assertEqual(response.status_code, 502, response.text)
            self.assertEqual(response.json()["detail"], expected_detail)
            self.assertNotIn(sentinel, response.text)

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

    def test_generate_rejects_malformed_supersete_columns_and_fractional_pick_count(self):
        malformed = self.client.post("/api/v1/supersete/generate", json={"columns": {"1": "not-an-object"}})
        fractional = self.client.post("/api/v1/supersete/generate", json={"columns": {"1": {"pick_count": 1.5}}})
        fractional_month = self.client.post("/api/v1/diadesorte/generate", json={"bonus": {"month": 2.5}})
        self.assertEqual(malformed.status_code, 422)
        self.assertEqual(fractional.status_code, 422)
        self.assertEqual(fractional_month.status_code, 422)

    def test_simulate_contest_keeps_valid_draw_when_storage_save_fails(self):
        draw = {"game": "megasena", "contest": 42, "draw_date": "01/01/2026", "numbers": [1, 2, 3, 4, 5, 6]}
        with patch("lotomaster.api.storage.get_draw", return_value=None), \
             patch("lotomaster.api.fetch_draw", return_value=draw), \
             patch("lotomaster.api.storage.save_draw", side_effect=OSError("disk")):
            response = self.client.post("/api/v1/megasena/simulate", json={"contest": 42, "tickets": [{"numbers": [1, 2, 3, 4, 7, 8]}]})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["contest"], 42)
        self.assertEqual(response.json()["results"][0]["main_hits"], 4)

    def test_upstream_draw_errors_are_502_and_do_not_expose_source_details(self):
        sentinel = "/srv/private/provider-payload"
        expected = "Não foi possível validar o resultado consultado na fonte."
        with patch("lotomaster.api.storage.get_draw", return_value=None), \
             patch("lotomaster.api.fetch_draw", side_effect=UpstreamDrawError(sentinel)):
            simulation = self.client.post("/api/v1/megasena/simulate", json={"contest": 123, "tickets": [{"numbers": [1, 2, 3, 4, 5, 6]}]})
        self.assertEqual(simulation.status_code, 502)
        self.assertEqual(simulation.json()["detail"], expected)
        self.assertNotIn(sentinel, simulation.text)

        closure_payload = {
            "pool": [1, 2, 3, 4, 5, 6], "pick_count": 6, "reference_contest": 123,
            "filters": {"min_repeated": 1},
        }
        with patch("lotomaster.api.storage.get_draw", return_value=None), \
             patch("lotomaster.api.fetch_draw", side_effect=UpstreamDrawError(sentinel)):
            closure = self.client.post("/api/v1/megasena/closures/exhaustive", json=closure_payload)
        self.assertEqual(closure.status_code, 502)
        self.assertEqual(closure.json()["detail"], expected)
        self.assertNotIn(sentinel, closure.text)

    def test_simulate_rejects_nonpositive_contest(self):
        response = self.client.post("/api/v1/megasena/simulate", json={"contest": 0, "tickets": [{"numbers": [1, 2, 3, 4, 5, 6]}]})
        self.assertEqual(response.status_code, 422)

    def test_exhaustive_closure_api_pages_and_reports_filter_reasons(self):
        payload = {
            "pool": list(range(1, 8)), "pick_count": 6, "page_size": 2, "offset": 0,
            "filters": {"min_sum": 30, "min_even": 4, "min_prime": 4},
        }
        with patch("lotomaster.api._reference_draw", side_effect=AssertionError("sem filtro de repetidas não busca concurso")):
            first = self.client.post("/api/v1/megasena/closures/exhaustive", json=payload)
            second = self.client.post("/api/v1/megasena/closures/exhaustive", json={**payload, "offset": 2})
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        data = first.json()
        self.assertEqual(data["candidate_count"], 7)
        self.assertEqual(data["returned_count"], 2)
        self.assertEqual(data["next_offset"], 2)
        self.assertFalse(data["items"][0]["approved"])
        self.assertEqual(len(data["items"][0]["reasons"]), 3)
        self.assertEqual(second.json()["offset"], 2)
        self.assertEqual(second.json()["items"][0]["numbers"], [1, 2, 3, 4, 6, 7])

    def test_closure_repeated_filter_requires_explicit_reference(self):
        payload = {"pool": list(range(1, 8)), "pick_count": 6, "filters": {"min_repeated": 3}}
        with patch("lotomaster.api._reference_draw") as reference:
            response = self.client.post("/api/v1/megasena/closures/exhaustive", json=payload)
        self.assertEqual(response.status_code, 422)
        self.assertIn("referência explícito", response.json()["detail"])
        reference.assert_not_called()

    def test_pareto_generation_uses_at_most_1000_cached_draws_and_reports_scope(self):
        draws = [{"contest": number, "numbers": list(range(1, 8))} for number in range(1, 11)]
        with patch("lotomaster.api.storage.list_draws", return_value=draws) as cache, \
             patch("lotomaster.api.storage.latest_draw", return_value=None):
            response = self.client.post("/api/v1/megasena/generate", json={"count": 2, "pareto": True, "seed": 9})
        self.assertEqual(response.status_code, 200, response.text)
        cache.assert_called_once_with("megasena", 1000)
        data = response.json()
        self.assertEqual(data["pareto"]["draws_analyzed"], 10)
        self.assertEqual(data["pareto"]["latest_contest"], 10)
        self.assertEqual(data["pareto"]["total_appearances"], 70)
        self.assertEqual(data["pareto"]["selected_numbers"], [1, 2, 3, 4, 5, 6])
        self.assertIn("80%", data["pareto"]["scope"])
        self.assertTrue(all(set(ticket["numbers"]).issubset(set(range(1, 7))) for ticket in data["items"]))

    def test_pareto_generation_requires_cached_history(self):
        with patch("lotomaster.api.storage.list_draws", return_value=[]) as cache, \
             patch("lotomaster.api.storage.latest_draw", return_value=None):
            response = self.client.post("/api/v1/megasena/generate", json={"count": 1, "pareto": True})
        self.assertEqual(response.status_code, 422)
        self.assertIn("histórico", response.json()["detail"])
        cache.assert_called_once_with("megasena", 1000)

    def test_api_schemas_bound_generation_and_simulation_payloads(self):
        excessive_generation = self.client.post("/api/v1/lotofacil/generate", json={"count": 101})
        excessive_numbers = self.client.post(
            "/api/v1/megasena/simulate",
            json={"tickets": [{"numbers": list(range(1, 52))}]},
        )
        excessive_columns = self.client.post(
            "/api/v1/supersete/simulate",
            json={"tickets": [{"numbers": [1] * 7, "columns": [[1] * 11 for _ in range(7)]}]},
        )
        excessive_ticket_count = self.client.post(
            "/api/v1/megasena/simulate",
            json={"tickets": [{"numbers": [1, 2, 3, 4, 5, 6]} for _ in range(501)]},
        )
        self.assertEqual(excessive_generation.status_code, 422)
        self.assertEqual(excessive_numbers.status_code, 422)
        self.assertEqual(excessive_columns.status_code, 422)
        self.assertEqual(excessive_ticket_count.status_code, 422)

    def test_simulate_uses_official_draw_supplied_by_browser(self):
        draw = {"game": "megasena", "contest": 50, "draw_date": "01/01/2026", "numbers": [1, 2, 3, 4, 5, 6]}
        with patch("lotomaster.api.latest_result", side_effect=AssertionError("não deve consultar a Caixa")):
            response = self.client.post("/api/v1/megasena/simulate", json={"tickets": [{"numbers": [1, 2, 3, 4, 7, 8]}], "draw": draw})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["contest"], 50)
        self.assertEqual(response.json()["results"][0]["main_hits"], 4)

    def test_simulate_fetches_selected_contest_without_using_latest(self):
        draw = {"game": "megasena", "contest": 42, "draw_date": "01/01/2026", "numbers": [1, 2, 3, 4, 5, 6]}
        with patch("lotomaster.api.storage.get_draw", return_value=None), \
             patch("lotomaster.api.fetch_draw", return_value=draw) as fetch, \
             patch("lotomaster.api.storage.save_draw"), \
             patch("lotomaster.api.latest_result", side_effect=AssertionError("não deve usar o último concurso")):
            response = self.client.post("/api/v1/megasena/simulate", json={"contest": 42, "tickets": [{"numbers": [1, 2, 3, 4, 7, 8]}]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["contest"], 42)
        self.assertEqual(response.json()["results"][0]["main_hits"], 4)
        fetch.assert_called_once_with("megasena", 42)

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

    def test_assistant_routes_do_not_forward_draws_to_gemini_by_default(self):
        draw = {"game": "megasena", "contest": 50, "numbers": [1, 2, 3, 4, 5, 6]}
        with patch.dict("os.environ", {"GEMINI_API_KEY": "test-only-not-a-real-key"}), \
             patch("lotomaster.assistant._gemini_commentary") as gemini, \
             patch("lotomaster.api.list_results", return_value=[draw]):
            get_response = self.client.get("/api/v1/megasena/assistant")
            post_response = self.client.post("/api/v1/megasena/assistant/from-draws", json={"draws": [draw]})
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(post_response.status_code, 200)
        self.assertEqual(get_response.json()["ai"]["status"], "local_only")
        self.assertEqual(post_response.json()["ai"]["status"], "local_only")
        gemini.assert_not_called()

    def test_assistant_routes_accept_explicit_gemini_opt_in(self):
        draw = {"game": "megasena", "contest": 50, "numbers": [1, 2, 3, 4, 5, 6]}
        token = "lotomaster-test-token-" + "x" * 32
        headers = {"Authorization": f"Bearer {token}"}
        with patch.dict("os.environ", {
                "GEMINI_API_KEY": "fake-provider-key",
                "LOTOMASTER_ENABLE_SERVER_GEMINI": "true",
                "LOTOMASTER_SERVER_GEMINI_TOKEN": token,
             }, clear=True), \
             patch("lotomaster.api.list_results", return_value=[draw]), \
             patch("lotomaster.api.build_assistant_report", return_value={"draws_analyzed": 1}) as build:
            get_response = self.client.get("/api/v1/megasena/assistant?use_gemini=true", headers=headers)
            post_response = self.client.post(
                "/api/v1/megasena/assistant/from-draws",
                json={"draws": [draw], "use_gemini": True},
                headers=headers,
            )
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(post_response.status_code, 200)
        build.assert_any_call("megasena", [draw], use_gemini=True)

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
        self.assertEqual(response.json()["source"], "CAIXA via Worker e cache do servidor")
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
        self.assertEqual(valid_ticket.json()["results"][0]["award"], "Faixa 1 · 6 acertos + 2 trevos")

    def test_milionaria_multiple_ticket_simulation_history_and_probability_api(self):
        draw = {"game": "maismilionaria", "contest": 8, "draw_date": "23/11/2026", "numbers": [1, 2, 3, 4, 5, 6], "trevos": [1, 2]}
        ticket = {"numbers": list(range(1, 13)), "bonus": {"trevos": list(range(1, 7))}}
        with patch("lotomaster.api.latest_result", return_value=draw):
            simulated = self.client.post("/api/v1/maismilionaria/simulate", json={"tickets": [ticket]})
        self.assertEqual(simulated.status_code, 200)
        result = simulated.json()["results"][0]
        self.assertEqual(result["subbets_total"], 13860)
        self.assertEqual(result["award"], "Faixa 1 · 6 acertos + 2 trevos")
        self.assertEqual(result["winning_subbets"], sum(result["award_counts"].values()))

        history = self.client.post("/api/v1/maismilionaria/simulate/history", json={"tickets": [ticket], "draws": [draw]})
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.json()["summary"], result["award_counts"])
        history_result = history.json()["draws"][0]["results"][0]
        self.assertEqual(history_result["subbets_total"], 13860)

        probability = self.client.get("/api/v1/maismilionaria/probability?pick_count=12&trevo_count=6")
        self.assertEqual(probability.status_code, 200)
        self.assertEqual(probability.json()["ticket_subbets"], 13860)
        self.assertEqual([row["tier"] for row in probability.json()["prize_tiers"]], list(range(1, 11)))
        self.assertEqual(probability.json()["any_prize"]["total_outcomes"], str(comb(50, 6) * 15))
        self.assertEqual(self.client.get("/api/v1/maismilionaria/probability?pick_count=13").status_code, 422)

    def test_csv_and_txt_exports(self):
        sample = [{"contest": 50, "draw_date": "01/01/2026", "numbers": [1, 2, 3, 4, 5, 6], "second_numbers": [], "trevos": [], "month": None, "team": None, "accumulated": False, "estimated_prize": 1000}]
        with patch("lotomaster.api.list_results", return_value=sample):
            csv_response = self.client.get("/api/v1/megasena/export.csv?limit=1")
            txt_response = self.client.get("/api/v1/megasena/export.txt?limit=1")
            xlsx_response = self.client.get("/api/v1/megasena/export.xlsx?limit=1")
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn("Concurso", csv_response.text)
        self.assertEqual(txt_response.status_code, 200)
        self.assertIn("Concurso 50", txt_response.text)
        self.assertEqual(xlsx_response.status_code, 200)
        self.assertEqual(xlsx_response.headers["content-type"], "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        with ZipFile(BytesIO(xlsx_response.content)) as archive:
            self.assertIn("xl/worksheets/sheet1.xml", archive.namelist())
            root = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        cells = root.findall(".//x:c", namespace)
        self.assertEqual(cells[0].attrib["r"], "A1")
        self.assertEqual(cells[0].findtext("x:is/x:t", namespaces=namespace), "Concurso")
        self.assertEqual(cells[7].attrib["r"], "A2")
        self.assertEqual(cells[7].findtext("x:v", namespaces=namespace), "50")

    def test_special_draw_flag_is_normalized(self):
        base = {"numero": 99, "listaDezenas": [str(i) for i in range(1, 16)], "tipoJogo": "LOTOFACIL"}
        regular = normalize_draw("lotofacil", {**base, "indicadorConcursoEspecial": 1})
        special = normalize_draw("lotofacil", {**base, "indicadorConcursoEspecial": 2})
        self.assertFalse(regular["special_draw"])
        self.assertTrue(special["special_draw"])
        self.assertEqual(special["contest_type"], "LOTOFACIL")


if __name__ == "__main__":
    unittest.main()
