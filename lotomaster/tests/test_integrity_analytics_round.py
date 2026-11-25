import unittest

from lotomaster.analytics import analyze_draws


class RoundIntegrityAnalyticsTests(unittest.TestCase):
    def test_repeats_only_compare_numerically_consecutive_contests(self):
        result = analyze_draws("megasena", [
            {"contest": 20, "numbers": [1, 2, 3, 4, 5, 6]},
            {"contest": 19, "numbers": [1, 7, 8, 9, 10, 11]},
            {"contest": 16, "numbers": [1, 2, 12, 13, 14, 15]},
        ])

        repeats = result["tables"]["repeats"]["data"]
        self.assertEqual(result["repeated_from_previous"], 1)
        self.assertTrue(repeats["latest_comparison_available"])
        self.assertEqual(repeats["history"], [1])
        self.assertEqual(repeats["consecutive_contest_pairs"], [[20, 19]])
        self.assertEqual(repeats["skipped_pair_boundaries"], [{
            "newer_contest": 19,
            "older_contest": 16,
        }])

    def test_latest_repeats_are_not_claimed_when_latest_records_have_a_gap(self):
        result = analyze_draws("megasena", [
            {"contest": 30, "numbers": [1, 2, 3, 4, 5, 6]},
            {"contest": 28, "numbers": [1, 7, 8, 9, 10, 11]},
        ])

        repeats = result["tables"]["repeats"]["data"]
        self.assertEqual(result["repeated_from_previous"], 0)
        self.assertEqual(repeats["latest_repeats"], 0)
        self.assertFalse(repeats["latest_comparison_available"])
        self.assertEqual(repeats["history"], [])
        self.assertEqual(repeats["consecutive_contest_pairs"], [])
        self.assertEqual(repeats["skipped_pair_boundaries"], [{
            "newer_contest": 30,
            "older_contest": 28,
        }])

    def test_missing_contest_identifier_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Número de concurso inválido"):
            analyze_draws("megasena", [
                {"contest": 2, "numbers": [1, 2, 3, 4, 5, 6]},
                {"numbers": [1, 7, 8, 9, 10, 11]},
            ])


if __name__ == "__main__":
    unittest.main()
