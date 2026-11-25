"""Regressões de probabilidades exatas e amostragem combinatória."""
from math import comb
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from lotomaster.api import app
from lotomaster.engine import _hypergeometric_counts, _quadrant_allocation_weights, ticket_probability, generate_tickets


class ProbabilityDistributionTests(unittest.TestCase):
    def test_primary_events_expose_exact_integer_counts_for_all_modalities(self):
        for game in ("megasena", "lotofacil", "lotomania", "quina", "diadesorte", "duplasena", "timemania", "supersete", "maismilionaria"):
            with self.subTest(game=game):
                result = ticket_probability(game)
                favorable = int(result["favorable_outcomes"])
                total = int(result["total_outcomes"])
                self.assertGreater(favorable, 0)
                self.assertGreater(total, favorable)
                self.assertAlmostEqual(result["percent"], favorable / total * 100, places=12)

    def test_dupla_sena_hit_distribution_is_the_best_of_two_independent_draws(self):
        result = ticket_probability("duplasena")
        single, denominator = _hypergeometric_counts(50, 6, 6)
        cumulative = 0
        previous_max_favorable = 0
        rows = {row["hits"]: row for row in result["hit_distribution"]}
        self.assertEqual(result["hit_unit"], "acertos no melhor dos dois sorteios")
        for hits, outcomes in sorted(single.items()):
            cumulative += outcomes
            expected = cumulative ** 2 - previous_max_favorable
            row = rows[hits]
            self.assertEqual(row["favorable_outcomes"], str(expected))
            self.assertEqual(row["total_outcomes"], str(denominator ** 2))
            previous_max_favorable = cumulative ** 2
        self.assertEqual(sum(int(row["favorable_outcomes"]) for row in rows.values()), denominator ** 2)

    def test_probability_inputs_are_rejected_instead_of_coerced_or_clamped(self):
        for value in (0, True, 6.5, "6"):
            with self.subTest(pick_count=value), self.assertRaises(ValueError):
                ticket_probability("megasena", pick_count=value)
        for value in (1, 7, True, 2.5, "3"):
            with self.subTest(trevo_count=value), self.assertRaises(ValueError):
                ticket_probability("maismilionaria", trevo_count=value)

    def test_every_lottery_exact_hit_distribution_sums_to_one(self):
        for game in ("megasena", "lotofacil", "lotomania", "quina", "diadesorte", "duplasena", "timemania", "supersete", "maismilionaria"):
            with self.subTest(game=game):
                result = ticket_probability(game)
                self.assertTrue(
                    abs(sum(row["probability"] for row in result["hit_distribution"]) - 1) < 1e-12
                )
                self.assertTrue(result["prize_tiers"])
                self.assertGreaterEqual(result["any_prize"]["probability"], 0)
                self.assertLessEqual(result["any_prize"]["probability"], 1)
                self.assertEqual(result["any_prize"]["total_outcomes"], str(
                    int(result["any_prize"]["total_outcomes"])
                ))

    def test_standard_hypergeometric_rows_expose_exact_integer_outcome_counts(self):
        result = ticket_probability("lotofacil", pick_count=16)
        denominator = comb(25, 15)
        self.assertEqual(result["hit_unit"], "acertos")
        rows = {row["hits"]: row for row in result["hit_distribution"]}
        for hits in range(6, 16):
            expected = comb(16, hits) * comb(9, 15 - hits)
            self.assertEqual(rows[hits]["favorable_outcomes"], str(expected))
            self.assertEqual(rows[hits]["total_outcomes"], str(denominator))
            self.assertAlmostEqual(rows[hits]["probability"], expected / denominator)

    def test_lotomania_prize_tiers_preserve_legacy_event_and_include_exact_odds(self):
        result = ticket_probability("lotomania")
        self.assertEqual(result["event"], "20 acertos")
        self.assertEqual([row["hits"] for row in result["prize_tiers"]], [0, 15, 16, 17, 18, 19, 20])
        self.assertTrue(all(row["favorable_outcomes"] and row["total_outcomes"] for row in result["prize_tiers"]))

    def test_dia_de_sorte_any_prize_uses_independent_month_event_without_double_counting(self):
        result = ticket_probability("diadesorte", pick_count=7)
        main_denominator = comb(31, 7)
        main_wins = sum(comb(7, hits) * comb(24, 7 - hits) for hits in (4, 5, 6, 7))
        expected = (main_wins / main_denominator) + (1 - main_wins / main_denominator) / 12
        self.assertAlmostEqual(result["any_prize"]["probability"], expected, places=14)
        month_row = next(row for row in result["prize_tiers"] if row["label"] == "Mês da Sorte")
        self.assertEqual(month_row["favorable_outcomes"], "1")
        self.assertEqual(month_row["total_outcomes"], "12")
        self.assertTrue(month_row["overlaps_main_prizes"])

    def test_timemania_includes_official_one_in_eighty_team_event(self):
        result = ticket_probability("timemania")
        team_row = next(row for row in result["prize_tiers"] if row["label"] == "Time do Coração")
        self.assertEqual(team_row["one_in"], 80)
        main_denominator = comb(80, 7)
        main_wins = sum(comb(10, hits) * comb(70, 7 - hits) for hits in (3, 4, 5, 6, 7))
        expected = main_wins / main_denominator + (1 - main_wins / main_denominator) / 80
        self.assertAlmostEqual(result["any_prize"]["probability"], expected, places=14)

    def test_dupla_sena_any_prize_counts_two_independent_draws(self):
        result = ticket_probability("duplasena")
        denominator = comb(50, 6)
        one_draw_win = sum(comb(6, hits) * comb(44, 6 - hits) for hits in (3, 4, 5, 6))
        expected = 1 - (1 - one_draw_win / denominator) ** 2
        self.assertAlmostEqual(result["any_prize"]["probability"], expected, places=14)
        self.assertTrue(all(row["may_overlap"] for row in result["prize_tiers"]))

    def test_plus_milionaria_exact_bonus_probability(self):
        result = ticket_probability("maismilionaria", trevo_count=3)
        jackpot = next(row for row in result["prize_tiers"] if row["hits"] == 6 and row["trevo_hits"] == 2)
        expected = (1 / comb(50, 6)) * (comb(3, 2) / comb(6, 2))
        self.assertAlmostEqual(jackpot["probability"], expected, places=20)
        self.assertEqual(result["event"], "Faixa 1 · ao menos uma subaposta")

    def test_plus_milionaria_matches_all_ten_official_tiers_including_tier_ten(self):
        result = ticket_probability("maismilionaria", trevo_count=2)
        self.assertEqual([row["tier"] for row in result["prize_tiers"]], list(range(1, 11)))
        tier_ten = result["prize_tiers"][-1]
        expected_favorable = comb(6, 2) * comb(44, 4) * comb(2, 1) * comb(4, 1)
        expected_total = comb(50, 6) * comb(6, 2)
        self.assertEqual(tier_ten["label"], "Faixa 10 · 2 acertos + 1 trevo")
        self.assertEqual(tier_ten["favorable_outcomes"], str(expected_favorable))
        self.assertEqual(tier_ten["total_outcomes"], str(expected_total))
        self.assertAlmostEqual(tier_ten["probability"], expected_favorable / expected_total)
        self.assertEqual(
            sum(int(row["favorable_outcomes"]) for row in result["prize_tiers"]),
            int(result["any_prize"]["favorable_outcomes"]),
        )

    def test_super_sete_column_choices_have_exact_poisson_binomial_counts(self):
        result = ticket_probability("supersete", column_pick_counts=[2, 1, 1, 1, 1, 1, 1])
        self.assertEqual(result["hit_unit"], "colunas acertadas")
        self.assertEqual(result["column_pick_counts"], [2, 1, 1, 1, 1, 1, 1])
        self.assertEqual(result["hit_distribution"][0]["total_outcomes"], "10000000")
        self.assertEqual(result["prize_tiers"][-1]["favorable_outcomes"], "2")
        self.assertEqual(result["one_in"], 5_000_000)

    def test_super_sete_rejects_malformed_column_choices(self):
        for values in ([1] * 6, [1] * 6 + [11], [1] * 6 + [True]):
            with self.subTest(values=values), self.assertRaises(ValueError):
                ticket_probability("supersete", column_pick_counts=values)

    def test_probability_api_accepts_repeated_column_pick_parameters(self):
        response = TestClient(app).get(
            "/api/v1/supersete/probability?" + "&".join("column_picks=1" for _ in range(7))
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["column_pick_counts"], [1] * 7)
        invalid = TestClient(app).get("/api/v1/supersete/probability?column_picks=1")
        self.assertEqual(invalid.status_code, 422)

    def test_quadrant_allocation_weights_equal_number_of_concrete_subsets(self):
        pools = [list(range(2)) for _ in range(4)]
        allocations = [(a, b, c, d) for a in range(3) for b in range(3)
                       for c in range(3) for d in range(3) if a + b + c + d == 2]
        weights = _quadrant_allocation_weights(pools, allocations, [0, 0, 0, 0])
        self.assertEqual(sum(weights), comb(8, 2))

    def test_quadrant_generation_chooses_allocations_with_combinatorial_weights(self):
        class FixedRng:
            def __init__(self):
                self.weights = None

            def choices(self, population, weights, k):
                self.weights = list(weights)
                return [population[0]]

            def sample(self, population, count):
                return list(population[:count])

        rng = FixedRng()
        filters = {f"{bound}_q{index}": value for index in range(1, 5)
                   for bound, value in (("min", 0), ("max", 25))}
        with patch("lotomaster.engine.storage.latest_draw", return_value=None), \
             patch("lotomaster.engine.random.Random", return_value=rng):
            tickets = generate_tickets("lotomania", {"pick_count": 50, "filters": filters, "seed": 3})
        self.assertEqual(len(tickets[0]["numbers"]), 50)
        self.assertIsNotNone(rng.weights)
        self.assertEqual(sum(rng.weights), comb(100, 50))


if __name__ == "__main__":
    unittest.main()
