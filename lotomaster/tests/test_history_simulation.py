import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from lotomaster.api import app
from lotomaster.engine import simulate_ticket_history


class HistorySimulationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_api_lotofacil_multiple_tickets_and_11_to_15_summary(self):
        draw = {"game": "lotofacil", "contest": 123, "draw_date": "01/01/2026", "numbers": list(range(1, 16))}
        tickets = [
            {"numbers": list(range(1, 16))},
            {"numbers": list(range(1, 12)) + [16, 17, 18, 19]},
            {"numbers": list(range(11, 26))},
        ]
        with patch("lotomaster.api.fetch_draw", side_effect=AssertionError("não deve buscar histórico")), patch("lotomaster.api.storage.save_draw", side_effect=AssertionError("não deve persistir")):
            response = self.client.post("/api/v1/lotofacil/simulate/history", json={"tickets": tickets, "draws": [draw]})
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["evaluated_contests"], 1)
        self.assertEqual(data["evaluated_tickets"], 3)
        self.assertEqual(data["draws"][0]["contest"], 123)
        self.assertEqual(data["summary"], {"15 acertos": 1, "11 acertos": 1})
        self.assertEqual(data["draws"][0]["results"][2]["award"], None)

    def test_dupla_sena_contests_include_independent_first_and_second_awards(self):
        draw = {"game": "duplasena", "contest": 8, "numbers": [1, 2, 3, 4, 5, 6], "second_numbers": [7, 8, 9, 10, 11, 12]}
        ticket = {"numbers": [1, 2, 3, 7, 8, 9]}
        report = simulate_ticket_history("duplasena", [ticket], [draw])
        self.assertEqual(report["draws"][0]["results"][0]["award"], {"first": "3 acertos", "second": "3 acertos"})
        self.assertEqual(report["summary"], {"1º sorteio: 3 acertos": 1, "2º sorteio: 3 acertos": 1})

    def test_month_team_and_trevos_are_separate_from_main_hit_tier(self):
        day = simulate_ticket_history("diadesorte", [{"numbers": [1, 2, 3, 4, 5, 6, 7], "bonus": {"month": 1}}], [
            {"contest": 1, "numbers": [1, 2, 3, 4, 5, 6, 7], "month": {"name": "Janeiro", "number": 1}}
        ])
        self.assertEqual(day["summary"], {"7 acertos": 1, "Mês da Sorte": 1})
        month_only = simulate_ticket_history("diadesorte", [{"numbers": [8, 9, 10, 11, 12, 13, 14], "bonus": {"month": 1}}], [
            {"contest": 4, "numbers": [1, 2, 3, 4, 5, 6, 7], "month": {"name": "Janeiro", "number": 1}}
        ])
        self.assertEqual(month_only["summary"], {"Mês da Sorte": 1})
        team = simulate_ticket_history("timemania", [{"numbers": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], "bonus": {"team": "Time A"}}], [
            {"contest": 2, "numbers": [1, 2, 3, 11, 12, 13, 14], "team": "Time A"}
        ])
        self.assertEqual(team["summary"], {"3 acertos": 1, "Time do Coração": 1})
        million = simulate_ticket_history("maismilionaria", [{"numbers": [1, 2, 3, 4, 5, 6], "bonus": {"trevos": [1, 2]}}], [
            {"contest": 3, "numbers": [1, 2, 3, 4, 5, 6], "trevos": [1, 2]}
        ])
        self.assertEqual(million["summary"], {"Faixa 1 · 6 acertos + 2 trevos": 1})
        self.assertNotIn("2 trevos", million["summary"])

    def test_validates_duplicates_game_second_draw_and_trevos(self):
        with self.assertRaisesRegex(ValueError, "duplicado"):
            simulate_ticket_history("megasena", [{"numbers": [1, 2, 3, 4, 5, 6]}], [
                {"contest": 1, "numbers": [1, 2, 3, 4, 5, 6]}, {"contest": 1, "numbers": [1, 2, 3, 4, 5, 6]}
            ])
        bad_double = {"contest": 1, "numbers": [1, 2, 3, 4, 5, 6], "second_numbers": [1, 2]}
        with self.assertRaisesRegex(ValueError, "second_numbers"):
            simulate_ticket_history("duplasena", [{"numbers": [1, 2, 3, 4, 5, 6]}], [bad_double])
        bad_million = {"contest": 1, "numbers": [1, 2, 3, 4, 5, 6], "trevos": [2, 2]}
        with self.assertRaisesRegex(ValueError, "trevos"):
            simulate_ticket_history("maismilionaria", [{"numbers": [1, 2, 3, 4, 5, 6], "bonus": {"trevos": [1, 2]}}], [bad_million])
        wrong_game = {"game": "quina", "contest": 1, "numbers": [1, 2, 3, 4, 5, 6]}
        with self.assertRaisesRegex(ValueError, "modalidade"):
            simulate_ticket_history("megasena", [{"numbers": [1, 2, 3, 4, 5, 6]}], [wrong_game])

    def test_history_rejects_non_python_ints_in_each_draw_list(self):
        valid_numbers = [1, 2, 3, 4, 5, 6]
        cases = (
            ("megasena", "numbers", valid_numbers, [1, 2, 3, 4, 5, "6"]),
            ("megasena", "numbers", valid_numbers, [1, 2, 3, 4, 5, 6.0]),
            ("megasena", "numbers", valid_numbers, [1, 2, 3, 4, 5, True]),
            ("duplasena", "second_numbers", [7, 8, 9, 10, 11, 12], [7, 8, 9, 10, 11, "12"]),
            ("duplasena", "second_numbers", [7, 8, 9, 10, 11, 12], [7, 8, 9, 10, 11, 12.0]),
            ("duplasena", "second_numbers", [7, 8, 9, 10, 11, 12], [7, 8, 9, 10, 11, False]),
            ("maismilionaria", "trevos", [1, 2], [1, "2"]),
            ("maismilionaria", "trevos", [1, 2], [1, 2.0]),
            ("maismilionaria", "trevos", [1, 2], [1, True]),
        )
        for game, field, valid, invalid in cases:
            with self.subTest(game=game, field=field, invalid=invalid):
                draw = {"contest": 1, "numbers": valid_numbers.copy()}
                if game == "duplasena":
                    draw["second_numbers"] = valid.copy()
                elif game == "maismilionaria":
                    draw["trevos"] = valid.copy()
                else:
                    draw[field] = invalid
                if game != "megasena":
                    draw[field] = invalid
                with self.assertRaises(ValueError):
                    simulate_ticket_history(game, [{"numbers": valid_numbers}], [draw])

    def test_history_simulation_does_not_mutate_input_draw_lists(self):
        draw = {"contest": 1, "numbers": [1, 2, 3, 4, 5, 6]}
        original = {key: value.copy() if isinstance(value, list) else value for key, value in draw.items()}
        report = simulate_ticket_history("megasena", [{"numbers": [1, 2, 3, 4, 5, 6]}], [draw])
        self.assertEqual(report["draws"][0]["results"][0]["main_hits"], 6)
        self.assertEqual(draw, original)

        dupla = {"contest": 2, "numbers": [1, 2, 3, 4, 5, 6], "second_numbers": [7, 8, 9, 10, 11, 12]}
        dupla_original = {key: value.copy() if isinstance(value, list) else value for key, value in dupla.items()}
        simulate_ticket_history("duplasena", [{"numbers": [1, 2, 3, 7, 8, 9]}], [dupla])
        self.assertEqual(dupla, dupla_original)

        million = {"contest": 3, "numbers": [1, 2, 3, 4, 5, 6], "trevos": [1, 2]}
        million_original = {key: value.copy() if isinstance(value, list) else value for key, value in million.items()}
        simulate_ticket_history("maismilionaria", [{"numbers": [1, 2, 3, 4, 5, 6], "bonus": {"trevos": [1, 2]}}], [million])
        self.assertEqual(million, million_original)

    def test_supersete_history_accepts_repeated_digits_across_columns(self):
        draw = {"game": "supersete", "contest": 11, "numbers": [4, 4, 0, 4, 9, 0, 4]}
        ticket = {"numbers": [4, 4, 0, 4, 9, 0, 4]}
        report = simulate_ticket_history("supersete", [ticket], [draw])
        self.assertEqual(report["draws"][0]["results"][0]["hits"], 7)
        self.assertEqual(report["summary"], {"7 acertos": 1})

    def test_supersete_history_rejects_bad_digits_and_wrong_count(self):
        ticket = {"numbers": [0, 1, 2, 3, 4, 5, 6]}
        for numbers in ([0, 1, 2, 3, 4, 5, 10], [0, 1, 2, 3, 4, 5], [0, 1, 2, 3, 4, 5, 6, 7], [0, 1, 2, 3, 4, 5, "x"], [0, 1, 2, 3, 4, 5, 6.5]):
            with self.subTest(numbers=numbers), self.assertRaises(ValueError):
                simulate_ticket_history("supersete", [ticket], [{"contest": 12, "numbers": numbers}])

    def test_caps_work_and_api_reports_validation_as_422(self):
        draw = {"contest": 1, "numbers": [1, 2, 3, 4, 5, 6]}
        with self.assertRaisesRegex(ValueError, "100.000"):
            simulate_ticket_history("megasena", [{"numbers": [1, 2, 3, 4, 5, 6]}] * 21, [dict(draw, contest=i + 1) for i in range(5000)])
        response = self.client.post("/api/v1/megasena/simulate/history", json={"tickets": [{"numbers": [1, 2, 3, 4, 5, 6]}], "draws": [draw, draw]})
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
