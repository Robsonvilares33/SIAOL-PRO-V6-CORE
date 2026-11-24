import copy
import unittest

from lotomaster.analytics import analyze_draws

MONTH_NAMES = ("Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro")


class MonthRepeatRegressionTests(unittest.TestCase):
    @staticmethod
    def draw(contest, month):
        return {
            "contest": contest,
            "numbers": [1, 2, 3, 4, 5, 6, 7],
            "month": {"number": month, "name": MONTH_NAMES[month - 1]},
        }

    @staticmethod
    def data(draws):
        return analyze_draws("diadesorte", draws)["tables"]["months-repeat"]["data"]

    def test_ordering_and_repeat_only_for_consecutive_contests(self):
        draws = [self.draw(12, 3), self.draw(10, 3), self.draw(11, 3)]
        result = analyze_draws("diadesorte", draws)
        data = result["tables"]["months-repeat"]["data"]

        self.assertEqual(result["latest_contest"], 12)
        self.assertEqual(data["consecutive_repeats"], [
            {"month": 3, "name": "Março", "contests": [12, 11]},
            {"month": 3, "name": "Março", "contests": [11, 10]},
        ])
        self.assertEqual(data["cut_boundaries"], [])

    def test_gap_is_a_cut_not_a_proven_repeat(self):
        data = self.data([self.draw(20, 4), self.draw(18, 4)])
        self.assertEqual(data["consecutive_repeats"], [])
        self.assertEqual(data["cut_boundaries"], [{"newer_contest": 20, "older_contest": 18}])
        self.assertEqual(data["delays"][3]["draws_since_last_observed"], 0)

    def test_delays_count_records_from_latest_available_record(self):
        data = self.data([self.draw(5, 2), self.draw(4, 3), self.draw(3, 2)])
        self.assertEqual(data["delays"][2]["draws_since_last_observed"], 1)
        self.assertEqual(data["delays"][2]["last_observed_contest"], 4)
        self.assertEqual(data["delays"][1]["draws_since_last_observed"], 0)

    def test_empty_history_marks_all_months_never_observed(self):
        data = self.data([])
        self.assertEqual(data["consecutive_repeats"], [])
        self.assertEqual(data["cut_boundaries"], [])
        self.assertEqual(data["latest_contest"], None)
        self.assertEqual(data["never_observed_months"], list(range(1, 13)))
        self.assertTrue(all(row["draws_since_last_observed"] is None for row in data["delays"]))

    def test_month_never_seen_is_explicit(self):
        data = self.data([self.draw(2, 1), self.draw(1, 1)])
        self.assertIn(12, data["never_observed_months"])
        self.assertTrue(data["delays"][11]["never_observed"])
        self.assertIsNone(data["delays"][11]["last_observed_contest"])

    def test_input_is_not_mutated(self):
        draws = [self.draw(2, 5), self.draw(1, 5)]
        before = copy.deepcopy(draws)
        self.data(draws)
        self.assertEqual(draws, before)

    def test_frequency_months_keeps_previous_shape_and_values(self):
        result = analyze_draws("diadesorte", [self.draw(2, 5), self.draw(1, 5)])
        self.assertEqual(result["tables"]["months"]["data"], {
            "counts": [{"month": "Maio", "count": 2}], "distinct": 1
        })


if __name__ == "__main__":
    unittest.main()
