import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from lotomaster.api import app


class ClientDrawValidationTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.draw = {"game": "megasena", "contest": 9, "numbers": [1, 2, 3, 4, 5, 6]}
        self.ticket = {"numbers": [1, 2, 3, 4, 5, 6]}

    def test_supplied_draw_is_labelled_unverified_and_not_persisted(self):
        with patch("lotomaster.api.storage.save_draw", side_effect=AssertionError("não pode salvar")):
            r = self.client.post("/api/v1/megasena/simulate", json={"tickets": [self.ticket], "draw": self.draw})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["provenance"]["kind"], "client_supplied")
        self.assertFalse(r.json()["provenance"]["verified"])

    def test_server_draw_is_labelled_separately(self):
        with patch("lotomaster.api.latest_result", return_value={**self.draw, "source": "cache"}):
            r = self.client.post("/api/v1/megasena/simulate", json={"tickets": [self.ticket]})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["provenance"]["kind"], "server_cache")
        self.assertFalse(r.json()["provenance"]["verified"])

    def test_rejects_wrong_or_malformed_draws_for_each_client_path(self):
        cases = [
            dict(self.draw, game="quina"), dict(self.draw, contest=True),
            dict(self.draw, contest=-1), dict(self.draw, numbers=[1, 2, 3, 4, 5, 5]),
            dict(self.draw, numbers=[1, 2, 3, 4, 5, 61]),
            dict(self.draw, numbers=[1, 2, 3, 4, 5, True]),
        ]
        for draw in cases:
            with self.subTest(draw=draw):
                a = self.client.post("/api/v1/megasena/simulate", json={"tickets": [self.ticket], "draw": draw})
                b = self.client.post("/api/v1/megasena/statistics/from-draws", json={"draws": [draw]})
                self.assertEqual(a.status_code, 422, a.text)
                self.assertEqual(b.status_code, 422, b.text)

    def test_rejects_duplicate_contests_and_invalid_special_results(self):
        r = self.client.post("/api/v1/megasena/statistics/from-draws", json={"draws": [self.draw, self.draw]})
        self.assertEqual(r.status_code, 422)
        month = {"game": "diadesorte", "contest": 1, "numbers": [1, 2, 3, 4, 5, 6, 7], "month": {"number": 13}}
        r = self.client.post("/api/v1/diadesorte/simulate", json={"tickets": [{"numbers": [1, 2, 3, 4, 5, 6, 7]}], "draw": month})
        self.assertEqual(r.status_code, 422)
        double = {"game": "duplasena", "contest": 1, "numbers": [1, 2, 3, 4, 5, 6]}
        r = self.client.post("/api/v1/duplasena/simulate", json={"tickets": [self.ticket], "draw": double})
        self.assertEqual(r.status_code, 422)

    def test_conference_requires_drawn_month_and_team(self):
        for game, numbers in (("diadesorte", [1, 2, 3, 4, 5, 6, 7]),
                              ("timemania", [1, 2, 3, 4, 5, 6, 7])):
            draw = {"game": game, "contest": 1, "numbers": numbers}
            ticket = {"numbers": numbers if game == "diadesorte" else list(range(1, 11))}
            with self.subTest(game=game):
                r = self.client.post(f"/api/v1/{game}/simulate", json={"tickets": [ticket], "draw": draw})
                self.assertEqual(r.status_code, 422, r.text)
                r = self.client.post(f"/api/v1/{game}/simulate/history", json={"tickets": [ticket], "draws": [draw]})
                self.assertEqual(r.status_code, 422, r.text)

    def test_statistics_and_history_mark_client_origin(self):
        stat = self.client.post("/api/v1/megasena/statistics/from-draws", json={"draws": [self.draw]})
        history = self.client.post("/api/v1/megasena/simulate/history", json={"tickets": [self.ticket], "draws": [self.draw]})
        for r in (stat, history):
            self.assertEqual(r.status_code, 200, r.text)
            self.assertEqual(r.json()["provenance"]["kind"], "client_supplied")
            self.assertFalse(r.json()["provenance"]["verified"])

    def test_single_simulation_limits_ticket_count(self):
        r = self.client.post("/api/v1/megasena/simulate", json={"tickets": [self.ticket] * 501, "draw": self.draw})
        self.assertEqual(r.status_code, 422)


if __name__ == "__main__":
    unittest.main()
