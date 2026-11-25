import unittest
from math import comb

from lotomaster.closures import exhaustive_closure


class ExhaustiveClosureTests(unittest.TestCase):
    def test_small_exhaustive_result(self):
        result = exhaustive_closure("megasena", [1, 2, 3, 4, 5, 6, 7], 6)
        self.assertEqual(result["game_count"], 7)
        self.assertEqual(len(result["games"]), 7)
        self.assertEqual(len({tuple(game) for game in result["games"]}), 7)
        self.assertTrue(all(len(game) == 6 for game in result["games"]))
        self.assertEqual(result["games"][0], [1, 2, 3, 4, 5, 6])
        self.assertIn("todas as combinações", result["coverage"])
        self.assertIn("não garantem prêmio", result["coverage"])
        self.assertIsNone(result["next_offset"])

    def test_fixed_numbers_are_in_every_ticket(self):
        result = exhaustive_closure("megasena", [1, 2, 3, 4, 5, 6, 7], 6, fixed=[2, 4])
        self.assertEqual(result["game_count"], 5)
        self.assertTrue(all({2, 4}.issubset(game) for game in result["games"]))

    def test_pagination_is_lexicographic_and_keeps_exact_offsets(self):
        first = exhaustive_closure("megasena", range(1, 9), 6, page_size=3)
        second = exhaustive_closure("megasena", range(1, 9), 6, offset=3, page_size=3)
        self.assertEqual(first["candidate_count"], comb(8, 6))
        self.assertEqual(first["returned_count"], 3)
        self.assertEqual(first["next_offset"], 3)
        self.assertEqual(second["offset"], 3)
        self.assertEqual(second["items"][0]["numbers"], [1, 2, 3, 4, 6, 7])
        self.assertEqual(len({tuple(row["numbers"]) for row in first["items"] + second["items"]}), 6)

    def test_large_closure_returns_a_page_without_rejecting_total(self):
        pool = list(range(1, 19))
        first = exhaustive_closure("megasena", pool, 6, page_size=3)
        last_offset = first["candidate_count"] - 1
        last = exhaustive_closure("megasena", pool, 6, offset=last_offset, page_size=10)
        self.assertGreater(first["candidate_count"], 1000)
        self.assertEqual(first["returned_count"], 3)
        self.assertEqual(first["next_offset"], 3)
        self.assertEqual(last["offset"], last_offset)
        self.assertEqual(last["items"], [{"numbers": [13, 14, 15, 16, 17, 18], "approved": True, "reasons": []}])
        self.assertIsNone(last["next_offset"])

    def test_reports_all_local_filter_failures_per_ticket(self):
        result = exhaustive_closure(
            "megasena", range(1, 8), 6, page_size=1,
            filters={"min_sum": 30, "min_even": 4, "min_prime": 4},
        )
        item = result["items"][0]
        self.assertFalse(item["approved"])
        self.assertEqual(len(item["reasons"]), 3)
        self.assertTrue(any("Soma" in reason for reason in item["reasons"]))
        self.assertTrue(any("Pares" in reason for reason in item["reasons"]))
        self.assertTrue(any("Primos" in reason for reason in item["reasons"]))
        self.assertEqual(result["approved_count"], 0)

    def test_repeated_filter_requires_explicit_reference_and_uses_it(self):
        filters = {"min_repeated": 3}
        with self.assertRaisesRegex(ValueError, "referência explícito"):
            exhaustive_closure("megasena", range(1, 8), 6, filters=filters)
        result = exhaustive_closure(
            "megasena", range(1, 8), 6, filters=filters,
            reference_draw=[1, 2, 30, 31, 32, 33], page_size=1,
        )
        self.assertIn("Repetidas", result["items"][0]["reasons"][0])

    def test_repeated_filter_rejects_empty_or_partial_reference(self):
        for reference in ([], [1, 2, 3, 4, 5]):
            with self.subTest(reference=reference), self.assertRaisesRegex(ValueError, "reference_draw"):
                exhaustive_closure("megasena", range(1, 8), 6, filters={"min_repeated": 1}, reference_draw=reference)

    def test_out_of_range_offset_returns_empty_terminal_page(self):
        result = exhaustive_closure("megasena", range(1, 8), 6, offset=999, page_size=10)
        self.assertEqual(result["items"], [])
        self.assertEqual(result["returned_count"], 0)
        self.assertIsNone(result["next_offset"])

    def test_rejects_invalid_inputs_and_preserves_them(self):
        pool = [6, 1, 2, 3, 4, 5]
        fixed = [1, 2]
        original_pool, original_fixed = pool.copy(), fixed.copy()
        result = exhaustive_closure("megasena", pool, 6, fixed=fixed)
        self.assertEqual(pool, original_pool)
        self.assertEqual(fixed, original_fixed)
        self.assertEqual(result["pool"], [1, 2, 3, 4, 5, 6])
        cases = [
            ("megasena", [1, 1, 2, 3, 4, 5], 6, []),
            ("megasena", [0, 2, 3, 4, 5, 6], 6, []),
            ("megasena", [1, 2, 3, 4, 5, 6], 5, []),
            ("megasena", [1, 2, 3, 4, 5, 6], 6, [7]),
            ("megasena", [1, 2, 3, 4, 5, 6], 6, [1, 1]),
            ("megasena", [True, 2, 3, 4, 5, 6], 6, []),
            ("nao-existe", [1, 2, 3, 4, 5, 6], 6, []),
        ]
        for lottery, numbers, size, locked in cases:
            with self.subTest(lottery=lottery, numbers=numbers, fixed=locked):
                with self.assertRaises(ValueError):
                    exhaustive_closure(lottery, numbers, size, fixed=locked)

    def test_rejects_pool_over_100_and_unrepresentable_modalities(self):
        with self.assertRaisesRegex(ValueError, "pool excede"):
            exhaustive_closure("lotomania", list(range(6)), 50, max_pool=5)
        for lottery in ("diadesorte", "timemania", "supersete", "maismilionaria"):
            with self.subTest(lottery=lottery):
                with self.assertRaisesRegex(ValueError, "não suportada"):
                    exhaustive_closure(lottery, [1, 2, 3, 4, 5, 6, 7], 7)

    def test_fixed_count_cannot_exceed_ticket_size(self):
        with self.assertRaisesRegex(ValueError, "fixas"):
            exhaustive_closure("megasena", list(range(1, 10)), 6, fixed=[1, 2, 3, 4, 5, 6, 7])


if __name__ == "__main__":
    unittest.main()
