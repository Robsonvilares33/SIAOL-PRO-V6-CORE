import unittest

from lotomaster.analytics import analyze_draws


class AnalyticsRegressionTests(unittest.TestCase):
    def test_empty_history_has_no_fabricated_pareto_appearances(self):
        result = analyze_draws("megasena", [])

        pareto = result["tables"]["pareto"]["data"]
        self.assertEqual(pareto["total_appearances"], 0)
        self.assertEqual(pareto["top_numbers_for_80_percent_of_hits"], [])
        self.assertEqual(result["draws_analyzed"], 0)
        self.assertEqual(result["sum"]["count"], 0)

    def test_pareto_contains_only_numbers_needed_to_reach_eighty_percent(self):
        result = analyze_draws("supersete", [
            {"contest": 2, "numbers": [1, 1, 1, 1, 1, 1, 1]},
            {"contest": 1, "numbers": [2, 2, 2, 2, 2, 2, 2]},
        ])

        pareto = result["tables"]["pareto"]["data"]
        # Repeated digits within one Super Sete draw count once for the
        # cross-draw appearance/Pareto summary; column detail remains separate.
        self.assertEqual(pareto["total_appearances"], 2)
        self.assertEqual(pareto["top_numbers_for_80_percent_of_hits"], [1, 2])

    def test_pareto_stops_at_the_minimum_prefix_reaching_eighty_percent(self):
        result = analyze_draws("megasena", [
            {"contest": contest, "numbers": [1, 2, 3, 4, 5, 6]}
            for contest in range(5, 0, -1)
        ])

        pareto = result["tables"]["pareto"]["data"]
        self.assertEqual(pareto["total_appearances"], 30)
        self.assertEqual(pareto["top_numbers_for_80_percent_of_hits"], [1, 2, 3, 4, 5])
        self.assertEqual(pareto["selected_appearances"], 25)
        self.assertLess(20, pareto["target_percent"] / 100 * pareto["total_appearances"])
        self.assertGreaterEqual(pareto["selected_appearances"], pareto["target_percent"] / 100 * pareto["total_appearances"])

    def test_superset_counts_and_gaps_are_independent_by_column(self):
        result = analyze_draws("supersete", [
            {"contest": 2, "numbers": [1, 2, 3, 4, 5, 6, 7]},
            {"contest": 1, "numbers": [1, 8, 3, 9, 5, 0, 7]},
        ])

        columns = result["special"]["columns"]
        self.assertEqual(len(columns), 7)
        self.assertEqual(columns[0]["digits"][1], {
            "digit": 1, "count": 2, "draws_since_hit": 0
        })
        self.assertEqual(columns[1]["digits"][2]["count"], 1)
        self.assertEqual(columns[1]["digits"][8]["draws_since_hit"], 1)
        self.assertEqual(result["layout"]["by_column"], columns)

    def test_timemania_team_identity_ignores_case_and_repeated_whitespace(self):
        result = analyze_draws("timemania", [
            {"contest": 3, "numbers": [1, 2, 3, 4, 5, 6, 7], "team": "  Sao   Paulo  "},
            {"contest": 2, "numbers": [8, 9, 10, 11, 12, 13, 14], "team": "sao paulo"},
            {"contest": 1, "numbers": [15, 16, 17, 18, 19, 20, 21], "team": "Vasco"},
        ])

        teams = result["special"]["teams"]
        gaps = {row["team"].casefold(): row["draws_since_hit"] for row in result["special"]["team_gaps"]["items"]}
        self.assertEqual(teams["distinct"], 2)
        self.assertEqual(teams["counts"][0], {"team": "Sao Paulo", "count": 2})
        self.assertEqual(gaps["sao paulo"], 0)
        self.assertEqual(gaps["vasco"], 2)


if __name__ == "__main__":
    unittest.main()
