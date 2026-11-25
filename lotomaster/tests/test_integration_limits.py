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


def _padded_json(payload, limit):
    body = json.dumps(payload, separators=(',', ':')).encode()
    assert len(body) < limit
    return body + b' ' * (limit - len(body))


def test_large_simulation_and_history_search_bodies_are_bounded_and_maximum_batches_work():
    client = TestClient(app)
    from lotomaster.request_limits import MAX_SIMULATION_BODY

    quina_draw = {'game': 'quina', 'contest': 1, 'numbers': [1, 2, 3, 4, 5]}
    lotofacil_draws = [
        {'contest': contest, 'numbers': list(range(1, 16))}
        for contest in range(1, 5001)
    ]
    cases = [
        (
            '/api/v1/lotofacil/history-number-search',
            {'numbers': list(range(1, 16)), 'draws': lotofacil_draws},
        ),
        (
            '/api/v1/quina/simulate/history',
            {'tickets': [{'numbers': [1, 2, 3, 4, 5]}], 'draws': draws(5000)},
        ),
        (
            '/api/v1/quina/simulate',
            {'tickets': [{'numbers': [1, 2, 3, 4, 5]} for _ in range(500)], 'draw': quina_draw},
        ),
    ]

    for route, payload in cases:
        with __import__('unittest').TestCase().subTest(route=route):
            accepted = client.post(route, content=_padded_json(payload, MAX_SIMULATION_BODY),
                                   headers={'content-type': 'application/json'})
            assert accepted.status_code == 200, accepted.text
            rejected = client.post(route, content=b' ' * (MAX_SIMULATION_BODY + 1),
                                   headers={'content-type': 'application/json'})
            assert rejected.status_code == 413, rejected.text

    chunked = client.post(
        '/api/v1/lotofacil/history-number-search',
        content=iter([b' ' * MAX_SIMULATION_BODY, b' ']),
        headers={'content-type': 'application/json'},
    )
    multipart = client.post(
        '/api/v1/quina/simulate/history',
        content=b'--boundary\r\n' + b'x' * (MAX_SIMULATION_BODY + 1),
        headers={'content-type': 'multipart/form-data; boundary=boundary'},
    )
    assert chunked.status_code == 413, chunked.text
    assert multipart.status_code == 413, multipart.text


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
