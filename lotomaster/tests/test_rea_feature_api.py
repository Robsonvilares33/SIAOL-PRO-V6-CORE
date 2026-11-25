import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from lotomaster.api import app
from lotomaster.engine import _weighted_sample


class ReaFeatureApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.latest = patch('lotomaster.engine.storage.latest_draw', return_value=None)
        self.latest.start()
        self.addCleanup(self.latest.stop)

    def test_closure_endpoint_exhaustive_and_stateless(self):
        with patch('lotomaster.storage.save_draw') as save:
            response = self.client.post('/api/v1/megasena/closures/exhaustive', json={
                'pool': [1, 2, 3, 4, 5, 6, 7], 'fixed': [1], 'pick_count': 6,
            })
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result['game_count'], 6)
        self.assertEqual(len({tuple(x) for x in result['games']}), 6)
        self.assertTrue(all(1 in game for game in result['games']))
        self.assertIn('não garantem prêmio', result['coverage'])
        save.assert_not_called()

    def test_closure_input_and_large_total_is_paged(self):
        large = self.client.post('/api/v1/megasena/closures/exhaustive', json={
            'pool': list(range(1, 19)), 'pick_count': 6, 'page_size': 12,
        })
        self.assertEqual(large.status_code, 200, large.text)
        self.assertEqual(large.json()['game_count'], 18564)
        self.assertEqual(large.json()['returned_count'], 12)
        self.assertEqual(large.json()['next_offset'], 12)

        for payload in (
            {'pool': [1, 2, 3, 4, 5, 5], 'pick_count': 6},
            {'pool': [True, 2, 3, 4, 5, 6], 'pick_count': 6},
            {'pool': [1, 2, 3, 4, 5, 6], 'pick_count': 6.5},
        ):
            with self.subTest(payload=payload):
                self.assertEqual(self.client.post('/api/v1/megasena/closures/exhaustive', json=payload).status_code, 422)
        self.assertEqual(self.client.post('/api/v1/supersete/closures/exhaustive', json={'pool': list(range(7)), 'pick_count': 7}).status_code, 422)
        self.assertEqual(self.client.post('/api/v1/naoexiste/closures/exhaustive', json={'pool': [], 'pick_count': 6}).status_code, 404)

    def test_generate_weighted_and_jumps(self):
        response = self.client.post('/api/v1/megasena/generate', json={
            'fixed': [1, 2, 7, 20, 21, 30], 'seed': 42,
            'weights': {'1': 2}, 'filters': {'min_jumps': 3, 'max_jumps': 3},
        })
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['items'][0]['numbers'], [1, 2, 7, 20, 21, 30])
        data = response.json()
        self.assertTrue(data['weighting_fallback'])
        self.assertTrue(data['items'][0]['weighting_fallback'])
        self.assertIn('pesos manuais não aplicados', data['method'])
        weighted = self.client.post('/api/v1/megasena/generate', json={'weights': {'1': 2}, 'seed': 42})
        self.assertEqual(weighted.status_code, 200, weighted.text)
        self.assertFalse(weighted.json()['weighting_fallback'])
        self.assertIn('ponderada', weighted.json()['method'])
        invalid = self.client.post('/api/v1/megasena/generate', json={'weights': {'1': 0}})
        self.assertEqual(invalid.status_code, 422)

    def test_super_sete_still_generates_without_weights_and_rejects_weights(self):
        response = self.client.post('/api/v1/supersete/generate', json={'seed': 1})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(response.json()['items'][0]['columns']), 7)
        response = self.client.post('/api/v1/supersete/generate', json={'weights': {'1': 2}})
        self.assertEqual(response.status_code, 422)

    def test_rounding_upper_endpoint_still_produces_complete_sample(self):
        class EdgeRng:
            def random(self):
                return 1.0  # Simulate an upper-endpoint rounded result.
        self.assertEqual(_weighted_sample(EdgeRng(), [1, 2], 2, {1: 1., 2: 1.}), [2, 1])

    def test_tool_catalog_only_advertises_supported_closures(self):
        for game, expected in [('lotofacil', True), ('megasena', True), ('diadesorte', False), ('supersete', False)]:
            with self.subTest(game=game):
                tools = self.client.get(f'/api/v1/{game}/tools').json()['tools']
                self.assertEqual(next(t['available'] for t in tools if t['id'] == 'closures'), expected)

    def test_tool_catalog_marks_quadrant_generator_available(self):
        lotomania = self.client.get('/api/v1/lotomania/tools').json()['tools']
        quadrants = next(t for t in lotomania if t['id'] == 'quadrants')
        self.assertTrue(quadrants['available'])
        self.assertIn('5×5', quadrants['note'])
        lotofacil = self.client.get('/api/v1/lotofacil/tools').json()['tools']
        repeated = next(t for t in lotofacil if t['id'] == 'repeated_closure')
        self.assertTrue(repeated['available'])

    def test_lotomania_generate_api_and_other_games_reject_quadrants(self):
        response = self.client.post('/api/v1/lotomania/generate', json={'pick_count': 50, 'seed': 7, 'filters': {'min_q1': 25, 'max_q1': 25, 'min_q2': 25, 'max_q2': 25, 'min_q3': 0, 'max_q3': 0, 'min_q4': 0, 'max_q4': 0}})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['items'][0]['quadrant_counts'], {'q1': 25, 'q2': 25, 'q3': 0, 'q4': 0})
        self.assertIn('não previsões', response.json()['disclaimer'])
        self.assertEqual(self.client.post('/api/v1/megasena/generate', json={'filters': {'max_q1': 2}}).status_code, 422)

    def test_lotofacil_23_numbers_current_and_history_simulation_api(self):
        ticket = {'numbers': list(range(1, 24))}
        draw = {'game': 'lotofacil', 'contest': 1, 'numbers': list(range(1, 16))}
        current = self.client.post('/api/v1/lotofacil/simulate', json={'tickets': [ticket], 'draw': draw})
        self.assertEqual(current.status_code, 200, current.text)
        self.assertEqual(current.json()['results'][0]['hits'], 15)
        history = self.client.post('/api/v1/lotofacil/simulate/history', json={'tickets': [ticket], 'draws': [draw]})
        self.assertEqual(history.status_code, 200, history.text)
        self.assertEqual(history.json()['draws'][0]['results'][0]['hits'], 15)
        self.assertEqual(self.client.post('/api/v1/lotofacil/simulate', json={'tickets': [{'numbers': list(range(1, 25))}], 'draw': draw}).status_code, 422)
        self.assertEqual(self.client.post('/api/v1/lotofacil/simulate', json={'tickets': [{'numbers': list(range(1, 15))}], 'draw': draw}).status_code, 422)


if __name__ == '__main__':
    unittest.main()
