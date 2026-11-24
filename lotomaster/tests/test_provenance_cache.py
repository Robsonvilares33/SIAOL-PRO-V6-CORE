import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from lotomaster import engine
from lotomaster.api import app

DRAW = {"game": "megasena", "contest": 50, "numbers": [1, 2, 3, 4, 5, 6]}
TICKETS = [{"numbers": [1, 2, 3, 4, 7, 8]}]


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        engine._latest_cache.clear()

    def test_client_can_spoof_source_but_not_server_provenance(self):
        draw = {**DRAW, "source": "CAIXA oficial", "verified": True, "warning": "aviso antigo"}
        with patch("lotomaster.api.fetch_draw", side_effect=AssertionError("network")), patch("lotomaster.api.latest_result", side_effect=AssertionError("network")):
            body = self.client.post('/api/v1/megasena/simulate', json={"draw": draw, "tickets": TICKETS}).json()
        self.assertEqual(body['provenance']['kind'], 'client_supplied')
        self.assertFalse(body['provenance']['verified'])
        self.assertEqual(body['draw']['warning'], 'aviso antigo')
        self.assertEqual(body['results'][0]['main_hits'], 4)

    def test_server_fetch_and_cache_are_distinct(self):
        with patch('lotomaster.api.storage.get_draw', return_value=DRAW):
            body = self.client.post('/api/v1/megasena/simulate', json={"contest": 50, "tickets": TICKETS}).json()
        self.assertEqual(body['provenance']['kind'], 'server_cache')
        with patch('lotomaster.api.storage.get_draw', return_value=None), patch('lotomaster.api.fetch_draw', return_value=DRAW), patch('lotomaster.api.storage.save_draw'):
            body = self.client.post('/api/v1/megasena/simulate', json={"contest": 50, "tickets": TICKETS}).json()
        self.assertEqual(body['provenance']['kind'], 'server_fetch')
        self.assertFalse(body['provenance']['verified'])

    def test_from_draws_is_not_claimed_official(self):
        payload = {"draws": [{**DRAW, "source": "CAIXA", "verified": True}]}
        with patch('lotomaster.api.build_assistant_report', return_value={"ok": True}):
            for route in ['statistics', 'assistant']:
                result = self.client.post(f'/api/v1/megasena/{route}/from-draws', json=payload)
                self.assertEqual(result.status_code, 200)
                self.assertEqual(result.json()['provenance']['kind'], 'client_supplied')
                self.assertFalse(result.json()['provenance']['verified'])

    def test_warning_survives_memory_ttl_and_results(self):
        with patch("lotomaster.engine.storage.latest_draw", return_value=DRAW), patch("lotomaster.engine.storage.list_draws_range", return_value=[DRAW]), patch("lotomaster.engine.fetch_draw", side_effect=OSError("offline")) as fetch:
            first = engine.latest_result('megasena', refresh=True)
            second = engine.latest_result('megasena', refresh=False)
            third = engine.list_results('megasena', limit=1, refresh_latest=False)[0]
        self.assertEqual(fetch.call_count, 1)
        for row in (first, second, third):
            self.assertIn('offline', row['warning'])
            self.assertEqual(row['source'], 'cache')
        with patch('lotomaster.api.list_results', return_value=[third]):
            result = self.client.get('/api/v1/megasena/results?limit=1').json()
        self.assertIn('offline', result['warning'])

    def test_success_after_expiry_clears_warning(self):
        with patch('lotomaster.engine.storage.latest_draw', return_value=DRAW), patch('lotomaster.engine.storage.save_draw'), patch('lotomaster.engine.fetch_draw', side_effect=[OSError('offline'), {**DRAW, 'contest': 51}]), patch('lotomaster.engine.time.monotonic', side_effect=[100, 191]):
            self.assertIn('warning', engine.latest_result('megasena'))
            fresh = engine.latest_result('megasena')
        self.assertNotIn('warning', fresh)
        self.assertEqual(fresh['contest'], 51)

    def test_history_page_warns_when_latest_unknown(self):
        stale = {**DRAW, 'warning': 'offline', 'source': 'cache'}
        with patch('lotomaster.engine.latest_result', return_value=stale), patch('lotomaster.engine.storage.list_draws_range', return_value=[DRAW]):
            page = engine.list_history_page('megasena', limit=1)
        self.assertEqual(page['warning'], 'offline')
