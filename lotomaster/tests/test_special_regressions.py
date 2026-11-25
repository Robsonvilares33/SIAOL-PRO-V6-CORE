import unittest

from lotomaster.engine import simulate_ticket_history


class SpecialHistoryRegressionTests(unittest.TestCase):
    def test_day_of_fortune_history_requires_valid_drawn_month(self):
        ticket = {"numbers": [1, 2, 3, 4, 5, 6, 7], "bonus": {"month": 1}}
        malformed_draws = [
            {"contest": 101, "numbers": [1, 2, 3, 4, 5, 6, 7]},
            {"contest": 102, "numbers": [1, 2, 3, 4, 5, 6, 7], "month": {"number": 13}},
            {"contest": 103, "numbers": [1, 2, 3, 4, 5, 6, 7], "month": {"number": True}},
        ]
        for draw in malformed_draws:
            with self.subTest(draw=draw), self.assertRaises(ValueError):
                simulate_ticket_history("diadesorte", [ticket], [draw])

    def test_timemania_history_requires_nonempty_drawn_team(self):
        ticket = {"numbers": list(range(1, 11)), "bonus": {"team": "Time Fictício"}}
        malformed_draws = [
            {"contest": 201, "numbers": [1, 2, 3, 4, 5, 6, 7]},
            {"contest": 202, "numbers": [1, 2, 3, 4, 5, 6, 7], "team": "  "},
            {"contest": 203, "numbers": [1, 2, 3, 4, 5, 6, 7], "team": 42},
        ]
        for draw in malformed_draws:
            with self.subTest(draw=draw), self.assertRaises(ValueError):
                simulate_ticket_history("timemania", [ticket], [draw])

    def test_valid_synthetic_special_results_still_score_awards(self):
        day = simulate_ticket_history(
            "diadesorte",
            [{"numbers": [1, 2, 3, 4, 5, 6, 7], "bonus": {"month": 1}}],
            [{"contest": 301, "numbers": [1, 2, 3, 4, 5, 6, 7], "month": {"number": 1}}],
        )
        team = simulate_ticket_history(
            "timemania",
            [{"numbers": list(range(1, 11)), "bonus": {"team": "Time Fictício"}}],
            [{"contest": 302, "numbers": [1, 2, 3, 4, 5, 6, 7], "team": "time fictício"}],
        )
        self.assertEqual(day["summary"], {"7 acertos": 1, "Mês da Sorte": 1})
        self.assertEqual(team["summary"], {"7 acertos": 1, "Time do Coração": 1})


if __name__ == "__main__":
    unittest.main()
