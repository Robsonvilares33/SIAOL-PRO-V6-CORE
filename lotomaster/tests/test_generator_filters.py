import unittest
from unittest.mock import patch

from lotomaster.catalog import get_spec
from lotomaster.engine import _passes_filters, _validate_ticket, generate_tickets


class GeneratorFilterTests(unittest.TestCase):
    def test_prime_fibonacci_sequence_and_previous_filters_apply(self):
        nums = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
        previous = {1, 2, 3}
        self.assertTrue(_passes_filters(nums, {
            "min_prime": 6, "max_prime": 6,
            "min_fibonacci": 6, "max_fibonacci": 6,
            "min_sequence": 15, "max_sequence": 15,
            "min_even": 7, "max_even": 7,
            "min_repeated": 3, "max_repeated": 3,
            "min_sum": sum(nums), "max_sum": sum(nums),
        }, previous))
        self.assertFalse(_passes_filters(nums, {"max_prime": 5}, previous))
        self.assertFalse(_passes_filters(nums, {"max_fibonacci": 5}, previous))
        self.assertFalse(_passes_filters(nums, {"max_sequence": 14}, previous))

    def test_primes_and_fibonacci_extend_beyond_lotofacil_range(self):
        nums = [0, 29, 34, 55, 89, 97]
        self.assertTrue(_passes_filters(nums, {"min_prime": 3, "max_prime": 3,
                                             "min_fibonacci": 3, "max_fibonacci": 3}, set()))
        self.assertFalse(_passes_filters(nums, {"max_prime": 2}, set()))
        self.assertFalse(_passes_filters(nums, {"max_fibonacci": 2}, set()))

    def test_lotofacil_per_line_and_column_limits_are_applied(self):
        # Grade 5x5: três dezenas em cada uma das cinco linhas/colunas.
        nums = [1, 2, 3, 7, 8, 9, 13, 14, 15, 16, 19, 20, 21, 22, 25]
        with patch("lotomaster.engine.storage.latest_draw", return_value=None):
            ticket = generate_tickets("lotofacil", {
                "fixed": nums, "seed": 1,
                "filters": {"min_line": 3, "max_line": 3, "min_column": 3, "max_column": 3},
            })[0]
        self.assertEqual(ticket["numbers"], nums)
        self.assertFalse(_passes_filters(nums, {"min_line": 4}, set()))
        self.assertFalse(_passes_filters(nums, {"max_column": 2}, set()))

    def test_filter_bounds_invalid_types_and_unknown_names_rejected(self):
        bad_filters = [
            {"min_prime": -1}, {"max_fibonacci": 16}, {"min_sequence": 0},
            {"min_even": 1.5}, {"min_prime": True}, {"mystery": 1},
            {"min_sequence": 5, "max_sequence": 2},
        ]
        with patch("lotomaster.engine.storage.latest_draw", return_value=None):
            for filters in bad_filters:
                with self.subTest(filters=filters), self.assertRaises(ValueError):
                    generate_tickets("lotofacil", {"filters": filters})
            for filters in ({"min_line": 6}, {"min_column": -1}, {"min_line": 1}):
                with self.subTest(filters=filters), self.assertRaises(ValueError):
                    generate_tickets("mega-sena", {"filters": filters})

    def test_super_set_rejects_any_nonempty_filter_object(self):
        with patch("lotomaster.engine.storage.latest_draw", return_value=None):
            for filters in ({"min_even": 1}, {"unknown": 1}):
                with self.subTest(filters=filters), self.assertRaisesRegex(ValueError, "Super Sete"):
                    generate_tickets("supersete", {"filters": filters})
            self.assertEqual(len(generate_tickets("supersete", {"filters": {}})[0]["columns"]), 7)

    def test_super_set_accepts_official_simple_and_multiple_bet_sizes(self):
        valid_counts = [
            [1, 1, 1, 1, 1, 1, 1],
            [2, 1, 1, 1, 1, 1, 1],
            [2, 2, 2, 2, 2, 2, 2],
            [3, 2, 2, 2, 2, 2, 2],
            [3, 3, 3, 3, 3, 3, 3],
        ]
        with patch("lotomaster.engine.storage.latest_draw", return_value=None):
            for counts in valid_counts:
                columns = {str(index): {"pick_count": count} for index, count in enumerate(counts, 1)}
                ticket = generate_tickets("supersete", {"columns": columns})[0]
                with self.subTest(counts=counts):
                    self.assertEqual([len(column) for column in ticket["columns"]], counts)

        invalid_columns = [[0], [0, 1], [0, 1], [0, 1], [0, 1], [0, 1, 2], [0, 1, 2]]
        with self.assertRaisesRegex(ValueError, "aposta múltipla"):
            _validate_ticket(get_spec("supersete"), {"columns": invalid_columns})
        with patch("lotomaster.engine.storage.latest_draw", return_value=None), \
             self.assertRaisesRegex(ValueError, "aposta múltipla"):
            generate_tickets("supersete", {"columns": {
                str(index): {"pick_count": count}
                for index, count in enumerate([1, 2, 2, 2, 2, 3, 3], 1)
            }})

    def test_existing_sum_even_repeat_filters_remain_active(self):
        nums = [1, 2, 3, 4, 5, 6]
        self.assertTrue(_passes_filters(nums, {"min_sum": 21, "max_sum": 21, "min_even": 3, "max_even": 3, "min_repeated": 2, "max_repeated": 2}, {1, 2}))
        self.assertFalse(_passes_filters(nums, {"max_sum": 20}, {1, 2}))
        self.assertFalse(_passes_filters(nums, {"min_sum": 100}, {1, 2}))
        with patch("lotomaster.engine.storage.latest_draw", return_value=None):
            self.assertEqual(len(generate_tickets("megasena", {"filters": {"min_even": 6, "max_even": 6}, "fixed": [2, 4, 6, 8, 10, 12]})[0]["numbers"]), 6)

    def test_lotomania_quadrant_geometry_and_generation(self):
        nums = list(range(100))
        self.assertTrue(_passes_filters(nums, {f"min_q{i}": 25 for i in range(1, 5)}, set()))
        with patch("lotomaster.engine.storage.latest_draw", return_value=None):
            ticket = generate_tickets("lotomania", {"pick_count": 50, "seed": 12, "fixed": [0, 1], "excluded": [99], "filters": {"min_q1": 10, "max_q1": 10, "min_q2": 10, "max_q2": 10, "min_q3": 15, "max_q3": 15, "min_q4": 15, "max_q4": 15}})[0]
        self.assertEqual(ticket["quadrant_counts"], {"q1": 10, "q2": 10, "q3": 15, "q4": 15})
        self.assertIn(0, ticket["numbers"])
        self.assertNotIn(99, ticket["numbers"])

    def test_quadrant_bounds_infeasibility_and_wrong_game(self):
        with patch("lotomaster.engine.storage.latest_draw", return_value=None):
            for filters in ({"min_q1": 26}, {"min_q1": 20, "max_q1": 10}, {"min_q1": 25, "min_q2": 25, "min_q3": 1}):
                with self.subTest(filters=filters), self.assertRaises(ValueError):
                    generate_tickets("lotomania", {"filters": filters})
            with self.assertRaises(ValueError):
                generate_tickets("lotofacil", {"filters": {"min_q1": 1}})
            with self.assertRaises(ValueError):
                generate_tickets("lotomania", {"fixed": [0] + list(range(10, 50)), "filters": {"max_q1": 1}})


if __name__ == "__main__":
    unittest.main()
