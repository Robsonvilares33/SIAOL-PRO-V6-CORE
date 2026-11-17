"""Integration of validation, provenance and the real ASGI API, offline."""
import json
from fastapi.testclient import TestClient
from lotomaster.api import app
from lotomaster.request_limits import MAX_HISTORY_BODY


def draws(n):
    return [{'game': 'quina', 'contest': i + 1, 'numbers': [1, 2, 3, 4, 5],
             'source': 'CAIXA', 'verified': True} for i in range(n)]


def test_statistics_boundary_and_provenance():
    client = TestClient(app)
    route = '/api/v1/quina/statistics/from-draws'
    ok = client.post(route, json={'draws': draws(500)})
    assert ok.status_code == 200
    assert ok.json()['draws_analyzed'] == 500
    assert ok.json()['provenance']['kind'] == 'client_supplied'
    assert ok.json()['provenance']['verified'] is False
    assert client.post(route, json={'draws': draws(501)}).status_code == 422


def test_assistant_boundary_and_provenance():
    client = TestClient(app)
    route = '/api/v1/quina/assistant/from-draws'
    ok = client.post(route, json={'draws': draws(300)})
    assert ok.status_code == 200
    assert ok.json()['ai']['status'] == 'local_only'
    assert ok.json()['provenance']['verified'] is False
    assert client.post(route, json={'draws': draws(301)}).status_code == 422


def test_bounded_malicious_inputs_rejected():
    client = TestClient(app)
    for route in ('statistics', 'assistant'):
        url = f'/api/v1/quina/{route}/from-draws'
        bad = draws(1); bad[0]['numbers'] = list(range(10000))
        assert client.post(url, json={'draws': bad}).status_code == 422
        assert client.post(url, content=b' ' * (MAX_HISTORY_BODY + 1)).status_code == 413


def test_recent_window_excludes_old_cache_instead_of_hiding_gap():
    from unittest.mock import patch
    from lotomaster import engine
    rows = [{'game':'quina','contest': n,'numbers':[1,2,3,4,5]} for n in [100,98,97]]
    with patch('lotomaster.engine.latest_result', return_value=rows[0]), \
         patch('lotomaster.engine.storage.list_draws_range', side_effect=lambda game, low, high: [r for r in rows if low <= r['contest'] <= high]), \
         patch('lotomaster.engine.fetch_draw', side_effect=OSError('offline')):
        result = engine.list_results('quina', limit=3)
    assert [row['contest'] for row in result] == [100, 98]
    with patch('lotomaster.api.list_results', return_value=result):
        data = TestClient(app).get('/api/v1/quina/results?limit=3').json()
    assert data['partial'] is True and data['expected_count'] == 3 and data['count'] == 2
