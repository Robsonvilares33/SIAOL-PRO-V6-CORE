import unittest
from unittest.mock import patch

from lotomaster.engine import _passes_filters, generate_tickets


class JumpsFilterTests(unittest.TestCase):
    def test_adjacent_gaps_counted_once_regardless_of_gap_size(self):
        numbers = [1, 2, 7, 20, 21, 30]
        # Três pares adjacentes ordenados têm distância > 1.
        self.assertTrue(_passes_filters(numbers, {"min_jumps": 3, "max_jumps": 3}, set()))
        self.assertFalse(_passes_filters(numbers, {"max_jumps": 2}, set()))
        self.assertFalse(_passes_filters(numbers, {"min_jumps": 4}, set()))

    def test_zero_jumps_for_consecutive_selection_and_empty_or_singleton(self):
        self.assertTrue(_passes_filters([3, 4, 5], {"min_jumps": 0, "max_jumps": 0}, set()))
        self.assertTrue(_passes_filters([1], {"min_jumps": 0, "max_jumps": 0}, set()))
        self.assertTrue(_passes_filters([], {"min_jumps": 0, "max_jumps": 0}, set()))

    def test_integer_bounds_and_coherent_order_are_validated(self):
        invalid = [
            {"min_jumps": -1}, {"max_jumps": 6}, {"min_jumps": 1.5},
            {"min_jumps": True}, {"min_jumps": "1.0"},
            {"min_jumps": 3, "max_jumps": 2},
        ]
        with patch("lotomaster.engine.storage.latest_draw", return_value=None):
            for filters in invalid:
                with self.subTest(filters=filters), self.assertRaises(ValueError):
                    generate_tickets("megasena", {"filters": filters})
            # O limite depende de pick_count (cinco gaps possíveis neste caso).
            with self.assertRaises(ValueError):
                generate_tickets("megasena", {"pick_count": 6, "filters": {"max_jumps": 6}})

    def test_generate_tickets_honors_jumps_with_fixed_and_excluded_numbers(self):
        # Fixos e removidos deixam apenas uma combinação: [1, 2, 10, 11, 20, 30].
        fixed = [1, 2, 10]
        excluded = [n for n in range(1, 61) if n not in {*fixed, 11, 20, 30}]
        with patch("lotomaster.engine.storage.latest_draw", return_value=None):
            ticket = generate_tickets("megasena", {
                "pick_count": 6,
                "fixed": fixed,
                "excluded": excluded,
                "filters": {"min_jumps": 3, "max_jumps": 3},
                "seed": 7,
            })[0]
        self.assertEqual(ticket["numbers"], [1, 2, 10, 11, 20, 30])

    def test_generate_tickets_fails_when_fixed_numbers_cannot_meet_jump_filter(self):
        with patch("lotomaster.engine.storage.latest_draw", return_value=None):
            with self.assertRaisesRegex(ValueError, "Nenhum jogo"):
                generate_tickets("megasena", {
                    "pick_count": 6,
                    "fixed": [1, 2, 3, 4, 5, 6],
                    "filters": {"min_jumps": 1},
                })


if __name__ == "__main__":
    unittest.main()
