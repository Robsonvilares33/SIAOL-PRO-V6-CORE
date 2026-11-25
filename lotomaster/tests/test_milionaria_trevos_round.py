from itertools import combinations
from math import comb
import unittest
from lotomaster.engine import simulate_tickets, simulate_ticket_history, ticket_probability


class MilionariaTrevosRoundTests(unittest.TestCase):
    def test_each_pair_is_checked_and_awarded_independently(self):
        ticket = {"numbers": [1, 2, 3, 4, 5, 6], "bonus": {"trevos": [1, 2, 3]}}
        draw = {"contest": 8, "numbers": [1, 2, 3, 4, 5, 6], "trevos": [1, 2]}
        result = simulate_tickets("maismilionaria", [ticket], draw)[0]
        self.assertEqual(result["award"], "Faixa 1 · 6 acertos + 2 trevos")
        self.assertEqual(result["award_counts"], {
            "Faixa 1 · 6 acertos + 2 trevos": 1,
            "Faixa 2 · 6 acertos + 1 ou nenhum trevo": 2,
        })
        self.assertTrue(result["award_tiers_overlap"])
        self.assertEqual(result["subbets_total"], 3)
        self.assertEqual(result["winning_subbets"], 3)
        self.assertEqual(len(result["subbet_awards"]), 3)

    def test_history_summary_counts_subbet_awards_and_simple_contract(self):
        draw = {"contest": 9, "numbers": [1, 2, 3, 4, 5, 6], "trevos": [1, 2]}
        multi = {"numbers": [1, 2, 3, 4, 5, 6], "bonus": {"trevos": [1, 2, 3]}}
        report = simulate_ticket_history("maismilionaria", [multi], [draw])
        self.assertEqual(report["summary"], {
            "Faixa 1 · 6 acertos + 2 trevos": 1,
            "Faixa 2 · 6 acertos + 1 ou nenhum trevo": 2,
        })
        simple = dict(multi, bonus={"trevos": [1, 2]})
        result = simulate_tickets("maismilionaria", [simple], draw)[0]
        self.assertEqual(result["award"], "Faixa 1 · 6 acertos + 2 trevos")

    def test_exhaustive_probability_presence_union_and_overlap_for_two_to_six(self):
        tier_defs = (
            (1, 6, (2,), "Faixa 1 · 6 acertos + 2 trevos"),
            (2, 6, (0, 1), "Faixa 2 · 6 acertos + 1 ou nenhum trevo"),
            (3, 5, (2,), "Faixa 3 · 5 acertos + 2 trevos"),
            (4, 5, (0, 1), "Faixa 4 · 5 acertos + 1 ou nenhum trevo"),
            (5, 4, (2,), "Faixa 5 · 4 acertos + 2 trevos"),
            (6, 4, (0, 1), "Faixa 6 · 4 acertos + 1 ou nenhum trevo"),
            (7, 3, (2,), "Faixa 7 · 3 acertos + 2 trevos"),
            (8, 3, (1,), "Faixa 8 · 3 acertos + 1 trevo"),
            (9, 2, (2,), "Faixa 9 · 2 acertos + 2 trevos"),
            (10, 2, (1,), "Faixa 10 · 2 acertos + 1 trevo"),
        )
        for k in range(2, 7):
            result = ticket_probability("maismilionaria", trevo_count=k)
            selected_sets = [tuple(range(1, k + 1))]
            draws = list(combinations(range(1, 7), 2))
            rows = {row["tier"]: row for row in result["prize_tiers"]}
            self.assertTrue(all(row["may_overlap"] for row in rows.values()))
            for tier, main_hits, matching_hits, _label in tier_defs:
                occurrences = 0
                for selected in selected_sets:
                    for drawn in draws:
                        if any(len(set(pair) & set(drawn)) in matching_hits
                               for pair in combinations(selected, 2)):
                            occurrences += 1
                main_outcomes = comb(6, main_hits) * comb(44, 6 - main_hits)
                denominator = comb(50, 6) * len(draws)
                expected_favorable = occurrences * main_outcomes
                self.assertEqual(int(rows[tier]["favorable_outcomes"]), expected_favorable)
                self.assertEqual(int(rows[tier]["total_outcomes"]), denominator)
                self.assertAlmostEqual(rows[tier]["probability"], expected_favorable / denominator)
            # Any prize is exact union over distinct main-hit and trevo outcomes.
            favorable = 0
            for main_hits, count in ((6, 1), (5, 6*44), (4, 15*comb(44, 2)),
                                     (3, 20*comb(44, 3)), (2, 15*comb(44, 4))):
                relevant = [d for d in tier_defs if d[1] == main_hits]
                trevo_wins = sum(any(any(len(set(pair) & set(drawn)) in d[2]
                    for pair in combinations(selected, 2)) for d in relevant)
                    for selected in selected_sets for drawn in draws)
                favorable += count * trevo_wins
            total = comb(50, 6) * len(selected_sets) * len(draws)
            self.assertEqual(int(result["any_prize"]["favorable_outcomes"]), favorable)
            self.assertEqual(int(result["any_prize"]["total_outcomes"]), total)
            self.assertTrue(any(row["may_overlap"] for row in result["prize_tiers"]))


if __name__ == "__main__":
    unittest.main()
