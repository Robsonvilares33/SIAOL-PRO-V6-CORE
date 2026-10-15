import unittest
from unittest.mock import patch

from lotomaster.analytics import analyze_draws
from lotomaster.assistant import build_assistant_report
from lotomaster.caixa import normalize_draw
from lotomaster.catalog import LOTTERIES, get_spec
from lotomaster.engine import generate_tickets, simulate_tickets, ticket_probability


class CatalogTests(unittest.TestCase):
    def test_nine_lotteries_are_configured(self):
        self.assertEqual(len(LOTTERIES), 9)
        self.assertEqual(get_spec("mega-sena")["key"], "megasena")
        self.assertEqual(get_spec("+milionaria")["key"], "maismilionaria")

    def test_normalizes_special_caixa_fields(self):
        day = normalize_draw("diadesorte", {
            "numero": 22, "listaDezenas": ["02", "04", "09", "10", "23", "26", "28"],
            "nomeTimeCoracaoMesSorte": "Janeiro", "dataApuracao": "10/10/2026",
        })
        self.assertEqual(day["month"], {"name": "Janeiro", "number": 1})
        double = normalize_draw("duplasena", {
            "numero": 12, "listaDezenas": ["03", "11", "17", "22", "29", "39"],
            "listaDezenasSegundoSorteio": ["08", "16", "31", "35", "44", "47"],
        })
        self.assertEqual(double["second_numbers"], [8, 16, 31, 35, 44, 47])
        million = normalize_draw("maismilionaria", {
            "numero": 7, "listaDezenas": ["06", "15", "28", "30", "42", "50"],
            "trevosSorteados": ["3", "6"],
        })
        self.assertEqual(million["trevos"], [3, 6])
        team = normalize_draw("timemania", {
            "numero": 9, "listaDezenas": ["01", "02", "03", "04", "05", "06", "07"],
            "nomeTimeCoracaoMesSorte": "TIME/UF\x00\x00",
        })
        self.assertEqual(team["team"], "TIME/UF")


class GeneratorTests(unittest.TestCase):
    def test_fixed_excluded_and_size(self):
        with patch("lotomaster.engine.storage.latest_draw", return_value=None):
            ticket = generate_tickets("lotofacil", {
                "count": 1, "pick_count": 16, "fixed": [1, 2], "excluded": [3], "seed": 11,
            })[0]
        self.assertEqual(len(ticket["numbers"]), 16)
        self.assertTrue({1, 2}.issubset(ticket["numbers"]))
        self.assertNotIn(3, ticket["numbers"])
        self.assertEqual(ticket["numbers"], sorted(ticket["numbers"]))

    def test_lotomania_selects_zero_through_ninety_nine(self):
        with patch("lotomaster.engine.storage.latest_draw", return_value=None):
            ticket = generate_tickets("lotomania", {"seed": 8})[0]
        self.assertEqual(len(ticket["numbers"]), 50)
        self.assertEqual(len(set(ticket["numbers"])), 50)
        self.assertGreaterEqual(min(ticket["numbers"]), 0)
        self.assertLessEqual(max(ticket["numbers"]), 99)

    def test_super_sete_has_seven_columns(self):
        with patch("lotomaster.engine.storage.latest_draw", return_value=None):
            ticket = generate_tickets("supersete", {"seed": 2})[0]
        self.assertEqual(len(ticket["columns"]), 7)
        self.assertTrue(all(len(column) == 1 and 0 <= column[0] <= 9 for column in ticket["columns"]))

    def test_milionaria_generates_unique_trevos(self):
        with patch("lotomaster.engine.storage.latest_draw", return_value=None):
            ticket = generate_tickets("maismilionaria", {"bonus": {"trevo_count": 4}, "seed": 17})[0]
        self.assertEqual(len(ticket["bonus"]["trevos"]), 4)
        self.assertEqual(len(set(ticket["bonus"]["trevos"])), 4)

    def test_invalid_constraints_are_rejected(self):
        with patch("lotomaster.engine.storage.latest_draw", return_value=None):
            with self.assertRaises(ValueError):
                generate_tickets("mega-sena", {"fixed": [4], "excluded": [4]})
            with self.assertRaises(ValueError):
                generate_tickets("lotofacil", {"filters": {"min_sum": 9999}})


class SimulationTests(unittest.TestCase):
    def test_mega_sena_four_hits(self):
        draw = {"contest": 1, "numbers": [1, 2, 3, 4, 20, 21]}
        result = simulate_tickets("megasena", [{"numbers": [1, 2, 3, 4, 5, 6]}], draw)[0]
        self.assertEqual(result["main_hits"], 4)
        self.assertEqual(result["award"], "4 acertos")

    def test_dupla_sena_checks_both_draws(self):
        draw = {"contest": 8, "numbers": [1, 2, 3, 4, 5, 6], "second_numbers": [7, 8, 9, 10, 11, 12]}
        result = simulate_tickets("duplasena", [{"numbers": [1, 2, 3, 7, 8, 9]}], draw)[0]
        self.assertEqual(result["main_hits"], 3)
        self.assertEqual(result["second_hits"], 3)
        self.assertEqual(result["award"]["first"], "3 acertos")

    def test_special_month_and_team(self):
        day = simulate_tickets("diadesorte", [{"numbers": [1, 2, 3, 4, 5, 6, 7], "bonus": {"month": 1}}], {"contest": 3, "numbers": [1, 2, 3, 4, 5, 6, 7], "month": {"name": "Janeiro", "number": 1}})[0]
        self.assertTrue(day["month_hit"])
        team = simulate_tickets("timemania", [{"numbers": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], "bonus": {"team": "Time A"}}], {"contest": 4, "numbers": [1, 2, 3, 11, 12, 13, 14], "team": "Time A"})[0]
        self.assertTrue(team["team_hit"])

    def test_milionaria_requires_trevos_and_only_awards_defined_tiers(self):
        draw = {"contest": 9, "numbers": [1, 2, 3, 4, 5, 6], "trevos": [1, 2]}
        with self.assertRaisesRegex(ValueError, "trevos"):
            simulate_tickets("maismilionaria", [{"numbers": [1, 2, 3, 4, 5, 6]}], draw)
        result = simulate_tickets("maismilionaria", [{"numbers": [1, 2, 3, 20, 21, 22], "bonus": {"trevos": [3, 4]}}], draw)[0]
        self.assertEqual(result["trevo_hits"], 0)
        self.assertIsNone(result["award"])

    def test_super_sete_scores_columns(self):
        draw = {"contest": 15, "numbers": [1, 2, 3, 4, 5, 6, 7]}
        ticket = {"columns": [[1], [2], [3], [0], [5], [1], [7]]}
        result = simulate_tickets("supersete", [ticket], draw)[0]
        self.assertEqual(result["hits"], 5)
        self.assertEqual(result["award"], "5 acertos")

    def test_lotomania_zero_hits_is_a_tier(self):
        result = simulate_tickets("lotomania", [{"numbers": list(range(50))}], {"contest": 2, "numbers": list(range(50, 70))})[0]
        self.assertEqual(result["main_hits"], 0)
        self.assertEqual(result["award"], "0 acertos")


class AnalyticsTests(unittest.TestCase):
    def test_frequency_gaps_and_specials(self):
        draws = [
            {"contest": 3, "numbers": [1, 2, 3, 4, 5, 6], "ordered_numbers": [6, 5, 4, 3, 2, 1]},
            {"contest": 2, "numbers": [1, 2, 8, 9, 10, 11]},
            {"contest": 1, "numbers": [1, 7, 8, 9, 10, 11]},
        ]
        report = analyze_draws("megasena", draws)
        row_one = next(row for row in report["frequency"] if row["number"] == 1)
        self.assertEqual(row_one["count"], 3)
        self.assertEqual(row_one["gap"], 0)
        self.assertEqual(report["draws_analyzed"], 3)
        self.assertIn("duos", report["tables"])

    def test_probability_for_base_mega(self):
        result = ticket_probability("megasena", 6)
        self.assertEqual(result["one_in"], 50063860)

    def test_assistant_labels_history_as_descriptive_and_uses_random_selection(self):
        draws = [
            {"game": "megasena", "contest": 2, "numbers": [1, 2, 3, 4, 5, 6]},
            {"game": "megasena", "contest": 1, "numbers": [1, 7, 8, 9, 10, 11]},
        ]
        result = build_assistant_report("megasena", draws, use_gemini=False)
        self.assertEqual(result["draws_analyzed"], 2)
        self.assertEqual(result["selection_policy"], "uniform_random")
        self.assertFalse(result["probabilities_calibrated_out_of_sample"])
        self.assertIn("não", result["disclaimer"])
        self.assertEqual(result["ai"]["status"], "local_only")


if __name__ == "__main__":
    unittest.main()
