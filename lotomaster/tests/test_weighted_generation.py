import unittest
from unittest.mock import patch

from lotomaster.engine import generate_tickets, simulate_tickets


class WeightedGenerationTests(unittest.TestCase):
    def test_validation_rejects_bad_weights_and_keys(self):
        bad_options = [
            {"weights": []},
            {"weights": {"01": 2}},
            {"weights": {"1": 0}},
            {"weights": {"1": -1}},
            {"weights": {"1": float("nan")}},
            {"weights": {"1": float("inf")}},
            {"weights": {"1": True}},
            {"weights": {True: 2}},
            {"weights": {"61": 2}},
            {"weights": {1: 2, "1": 3}},
            {"weights": {"1": 1_000_001}},
            {"weights": {"unknown": 2}},
        ]
        with patch("lotomaster.engine.storage.latest_draw", return_value=None):
            for options in bad_options:
                with self.subTest(options=options), self.assertRaises(ValueError):
                    generate_tickets("megasena", options)
            with self.assertRaisesRegex(ValueError, "Super Sete"):
                generate_tickets("supersete", {"weights": {"1": 2}})

    def test_seed_reproducibility_and_order_without_duplicates(self):
        options = {"weights": {"1": 5, "10": 2}, "seed": 9127, "count": 3}
        with patch("lotomaster.engine.storage.latest_draw", return_value=None):
            first = generate_tickets("megasena", options)
            second = generate_tickets("megasena", options)
        self.assertEqual([t["numbers"] for t in first], [t["numbers"] for t in second])
        for ticket in first:
            nums = ticket["numbers"]
            self.assertEqual(nums, sorted(nums))
            self.assertEqual(len(nums), len(set(nums)))

    def test_fixed_excluded_and_extreme_preference_are_respected(self):
        with patch("lotomaster.engine.storage.latest_draw", return_value=None):
            ticket = generate_tickets("megasena", {
                "pick_count": 6,
                "fixed": [2],
                "excluded": [3],
                "weights": {"1": 1_000_000},
                "seed": 3,
            })[0]
        nums = ticket["numbers"]
        self.assertIn(2, nums)
        self.assertIn(1, nums)
        self.assertNotIn(3, nums)
        self.assertEqual(len(nums), len(set(nums)))

    def test_no_weights_keeps_existing_rng_sample_path_and_empty_weights(self):
        with patch("lotomaster.engine.storage.latest_draw", return_value=None), \
             patch("lotomaster.engine._weighted_sample") as weighted_sample:
            legacy = generate_tickets("megasena", {"seed": 41})[0]["numbers"]
            empty = generate_tickets("megasena", {"seed": 41, "weights": {}})[0]["numbers"]
            weighted_sample.assert_not_called()
        self.assertEqual(legacy, empty)

    def test_repeat_filters_require_explicit_reference_for_generation(self):
        with patch("lotomaster.engine.storage.latest_draw", return_value=None):
            with self.assertRaisesRegex(ValueError, "concurso de referência explícito"):
                generate_tickets("megasena", {"filters": {"min_repeated": 0}})
            with self.assertRaisesRegex(ValueError, "concurso de referência explícito"):
                generate_tickets("megasena", {"filters": {"max_repeated": 6}})
            self.assertEqual(len(generate_tickets("megasena", {"filters": {}, "seed": 2})), 1)
            self.assertEqual(len(generate_tickets("supersete", {"filters": {}, "seed": 2})), 1)

    def test_simulation_ticket_parsing_rejects_fractional_and_unparseable_items(self):
        draw = {"contest": 99, "numbers": [1, 2, 3, 4, 5, 6]}
        for selected in ([1, 2, 3, 4, 5, 6.7], [1, 2, 3, 4, 5, "bad"]):
            with self.subTest(selected=selected), self.assertRaisesRegex(ValueError, "valores inteiros"):
                simulate_tickets("megasena", [{"numbers": selected}], draw)
        result = simulate_tickets("megasena", [{"numbers": "1, 2, 3, 4, 5, 6"}], draw)
        self.assertEqual(result[0]["hits"], 6)

    def test_weights_are_transient_and_do_not_persist(self):
        with patch("lotomaster.engine.storage.latest_draw", return_value=None), \
             patch("lotomaster.engine.storage.save_draw") as save_draw:
            result = generate_tickets("megasena", {"weights": {"1": 4}, "seed": 1})
        self.assertEqual(len(result), 1)
        save_draw.assert_not_called()


if __name__ == "__main__":
    unittest.main()
