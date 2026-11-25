from math import comb
import unittest

from lotomaster.catalog import get_spec
from lotomaster.engine import _validate_ticket, generate_tickets, simulate_tickets, simulate_ticket_history, ticket_probability


TIERS = (
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


def choose(n, k):
    return comb(n, k) if n >= 0 and 0 <= k <= n else 0


def reference_probability_counts(pick_count, trevo_count):
    """Independent small-state enumeration over exact intersection sizes."""
    tier_favorable = {tier: 0 for tier, *_ in TIERS}
    any_favorable = 0
    for main_hits in range(7):
        main_draws = comb(pick_count, main_hits) * comb(50 - pick_count, 6 - main_hits)
        if not main_draws:
            continue
        main_subbet_hits = {
            hits: (comb(main_hits, hits) * comb(pick_count - main_hits, 6 - hits)
                   if 0 <= hits <= main_hits and 0 <= 6 - hits <= pick_count - main_hits else 0)
            for hits in range(7)
        }
        for trevo_hits in range(3):
            trevo_draws = choose(trevo_count, trevo_hits) * choose(6 - trevo_count, 2 - trevo_hits)
            if not trevo_draws:
                continue
            trevo_subbet_hits = {
                hits: (comb(trevo_hits, hits) * comb(trevo_count - trevo_hits, 2 - hits)
                       if 0 <= hits <= trevo_hits and 0 <= 2 - hits <= trevo_count - trevo_hits else 0)
                for hits in range(3)
            }
            won = False
            for tier, main_target, trevo_targets, _label in TIERS:
                present = main_subbet_hits[main_target] > 0 and any(trevo_subbet_hits[hits] > 0 for hits in trevo_targets)
                if present:
                    tier_favorable[tier] += main_draws * trevo_draws
                    won = True
            if won:
                any_favorable += main_draws * trevo_draws
    return tier_favorable, any_favorable, comb(50, 6) * comb(6, 2)


class MaisMilionariaMultipleTests(unittest.TestCase):
    def test_catalog_exposes_official_multiple_pick_limits(self):
        spec = get_spec("maismilionaria")
        self.assertEqual((spec["min_pick"], spec["max_pick"]), (6, 12))
        self.assertEqual((spec["bonus"]["minimum"], spec["bonus"]["maximum"]), (2, 6))

    def test_generation_and_ticket_probability_include_all_subbets_at_boundaries(self):
        for pick_count, trevo_count in ((6, 2), (6, 6), (12, 2), (12, 6)):
            with self.subTest(pick_count=pick_count, trevo_count=trevo_count):
                ticket = generate_tickets("maismilionaria", {
                    "pick_count": pick_count,
                    "bonus": {"trevo_count": trevo_count},
                    "seed": 17,
                })[0]
                self.assertEqual(len(ticket["numbers"]), pick_count)
                self.assertEqual(len(ticket["bonus"]["trevos"]), trevo_count)
                self.assertEqual(ticket["probability"]["ticket_subbets"], comb(pick_count, 6) * comb(trevo_count, 2))
                self.assertEqual(ticket["probability"]["pick_count"], pick_count)
                self.assertEqual(ticket["probability"]["trevo_count"], trevo_count)

    def test_probability_per_tier_and_any_prize_matches_independent_exact_reference(self):
        for pick_count, trevo_count in ((6, 2), (6, 6), (12, 2), (12, 6)):
            with self.subTest(pick_count=pick_count, trevo_count=trevo_count):
                result = ticket_probability("maismilionaria", pick_count=pick_count, trevo_count=trevo_count)
                tier_counts, any_count, total = reference_probability_counts(pick_count, trevo_count)
                rows = {row["tier"]: row for row in result["prize_tiers"]}
                self.assertEqual(set(rows), set(range(1, 11)))
                self.assertEqual(result["ticket_subbets"], comb(pick_count, 6) * comb(trevo_count, 2))
                for tier, expected in tier_counts.items():
                    self.assertEqual(int(rows[tier]["favorable_outcomes"]), expected)
                    self.assertEqual(int(rows[tier]["total_outcomes"]), total)
                    self.assertAlmostEqual(rows[tier]["probability"], expected / total)
                self.assertEqual(int(result["any_prize"]["favorable_outcomes"]), any_count)
                self.assertEqual(int(result["any_prize"]["total_outcomes"]), total)
                self.assertAlmostEqual(result["any_prize"]["probability"], any_count / total)
                self.assertTrue(all(row["may_overlap"] for row in rows.values()))

    def test_invalid_number_and_trevo_counts_are_rejected(self):
        spec = get_spec("maismilionaria")
        for count in (5, 13):
            with self.subTest(number_count=count), self.assertRaises(ValueError):
                _validate_ticket(spec, {"numbers": list(range(1, count + 1)), "bonus": {"trevos": [1, 2]}})
            with self.subTest(probability_count=count), self.assertRaises(ValueError):
                ticket_probability("maismilionaria", pick_count=count)
        for trevos in ([1], [1, 2, 3, 4, 5, 6, 7], [1, 1]):
            with self.subTest(trevos=trevos), self.assertRaises(ValueError):
                _validate_ticket(spec, {"numbers": list(range(1, 7)), "bonus": {"trevos": trevos}})

    def test_multiple_ticket_conference_counts_awards_without_enumerating_subbet_list(self):
        ticket = {"numbers": list(range(1, 13)), "bonus": {"trevos": list(range(1, 7))}}
        draw = {"contest": 8, "numbers": [1, 2, 3, 4, 5, 6], "trevos": [1, 2]}
        result = simulate_tickets("maismilionaria", [ticket], draw)[0]
        self.assertEqual(result["main_hits"], 6)
        self.assertEqual(result["subbets_total"], comb(12, 6) * comb(6, 2))
        self.assertEqual(result["award"], "Faixa 1 · 6 acertos + 2 trevos")
        expected = {}
        for _tier, main_hits, trevo_hits, label in TIERS:
            count = sum(
                comb(6, main_hits) * comb(6, 6 - main_hits)
                * comb(2, matched_trevos) * comb(4, 2 - matched_trevos)
                for matched_trevos in trevo_hits
            )
            if count:
                expected[label] = count
        self.assertEqual(result["award_counts"], expected)
        self.assertEqual(result["winning_subbets"], sum(expected.values()))
        self.assertNotIn("subbet_awards", result)
        report = simulate_ticket_history("maismilionaria", [ticket], [draw])
        self.assertEqual(report["summary"], expected)


if __name__ == "__main__":
    unittest.main()
