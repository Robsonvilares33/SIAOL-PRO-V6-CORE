import unittest

from lotomaster.analytics import analyze_draws
from lotomaster.catalog import LOTTERIES, get_stats, get_spec


class AllGameStatisticsTests(unittest.TestCase):
    def test_every_declared_statistic_has_a_result_for_each_game(self):
        for game, spec in LOTTERIES.items():
            with self.subTest(game=game):
                numbers = list(range(spec["minimum"], spec["minimum"] + spec["draw_size"]))
                draw = {
                    "game": game,
                    "contest": 100,
                    "numbers": numbers,
                    "ordered_numbers": numbers + ([1, 2] if game == "maismilionaria" else []),
                    "second_numbers": list(range(7, 13)) if game == "duplasena" else [],
                    "trevos": [1, 2] if game == "maismilionaria" else [],
                    "month": {"name": "Janeiro", "number": 1} if game == "diadesorte" else None,
                    "team": "Time Teste" if game == "timemania" else None,
                    "special_draw": True,
                }
                result = analyze_draws(game, [draw])
                expected = {item["id"] for item in get_stats(get_spec(game))}
                self.assertTrue(expected.issubset(result["tables"].keys()))
                for stat in spec.get("extra_stats", []):
                    self.assertIn("data", result["tables"][stat[0]])

    def test_lotomania_grid_and_neighbors_are_descriptive_counts(self):
        result = analyze_draws("lotomania", [
            {"game": "lotomania", "contest": 2, "numbers": [0, 1, 10, 99]},
            {"game": "lotomania", "contest": 1, "numbers": [0, 1, 11]},
        ])
        grid = result["layout"]["number_grid"]
        self.assertEqual(grid["grid"][0]["count"], 2)
        self.assertEqual(grid["grid"][1]["count"], 2)
        self.assertEqual(grid["grid"][10]["count"], 1)
        self.assertEqual(grid["quadrant_occurrences"]["Q1"], 6)
        self.assertIn({"numbers": [0, 1], "count": 2}, grid["neighbor_pairs"])
        self.assertIn("não indicam tendência", grid["interpretation"])


if __name__ == "__main__":
    unittest.main()
