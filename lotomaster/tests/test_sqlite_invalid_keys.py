"""Offline regressions for poisoned SQLite keys and bounded cache reads."""
import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from lotomaster import engine, storage
from lotomaster.api import app

client = TestClient(app)


def draw(n):
    return {'game': 'megasena', 'contest': n, 'numbers': [1, 2, 3, 4, 5, 6]}


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'DB_PATH', tmp_path / 'test.db')
    monkeypatch.setattr(storage, '_initialized', False)
    engine._latest_cache.clear()
    yield
    engine._latest_cache.clear()
    storage._initialized = False


def insert(key, payload):
    storage.initialize()
    with storage._connect() as conn:
        conn.execute('INSERT OR REPLACE INTO lottery_draws(game,contest,payload) VALUES(?,?,?)', ('megasena', key, payload))


@pytest.mark.parametrize('bad_key', [10000, 1000000001])
@pytest.mark.parametrize('online', [False, True])
def test_extreme_invalid_key_does_not_hide_recent_rows(db, bad_key, online):
    for n in range(1, 5):
        storage.save_draw(draw(n))
    insert(bad_key, json.dumps(draw(4)))
    assert storage.latest_known_contest('megasena') == 4
    assert [r['contest'] for r in storage.list_draws('megasena', 3)] == [4, 3, 2]
    calls = []
    def remote(game, contest=None):
        calls.append(contest)
        if not online:
            raise OSError('offline')
        return draw(4 if contest is None else contest)
    with patch('lotomaster.engine.fetch_draw', side_effect=remote):
        history = client.get('/api/v1/megasena/history?limit=3')
        results = client.get('/api/v1/megasena/results?limit=3')
    assert history.status_code == results.status_code == 200
    h, r = history.json(), results.json()
    assert (h['from_contest'], h['to_contest']) == (2, 4)
    assert [x['contest'] for x in h['items']] == [4, 3, 2]
    assert h['missing_contests'] == [] and h['expected_count'] == 3
    assert [x['contest'] for x in r['items']] == [4, 3, 2]
    assert r['expected_count'] == 3 and r['partial'] is False
    assert ('warning' in h) == (not online)
    assert ('warning' in r) == (not online)
    assert h['provenance']['recently_checked'] == online
    assert all(n is None or 2 <= n <= 4 for n in calls)
    assert storage.get_draw('megasena', bad_key) is None


@pytest.mark.parametrize('online', [False, True])
@pytest.mark.parametrize('repair', [False, True])
def test_multiple_invalid_keys_real_gaps_and_repair(db, online, repair):
    storage.save_draw(draw(4)); storage.save_draw(draw(1))
    insert(3, '{broken')
    insert(2, json.dumps(draw(1)))
    for key in [5, 10000, 999999999, 1000000001]:
        insert(key, json.dumps(draw(4)))
    assert storage.latest_known_contest('megasena') == 4
    assert [r['contest'] for r in storage.list_draws('megasena', 2)] == [4, 1]
    calls = []
    def remote(game, contest=None):
        calls.append(contest)
        if contest is None:
            if not online:
                raise OSError('latest offline')
            return draw(4)
        if not repair:
            raise OSError('contest offline')
        return draw(contest)
    with patch('lotomaster.engine.fetch_draw', side_effect=remote):
        h = client.get('/api/v1/megasena/history?limit=4')
        r = client.get('/api/v1/megasena/results?limit=4')
    assert h.status_code == r.status_code == 200
    history, results = h.json(), r.json()
    assert history['missing_contests'] == ([] if repair else [3, 2])
    expected = [4, 3, 2, 1] if repair else [4, 1]
    assert [x['contest'] for x in history['items']] == expected
    assert [x['contest'] for x in results['items']] == expected
    assert results['partial'] is (not repair) and results['expected_count'] == 4
    assert ('warning' in history) == (not online)
    assert all(n is None or 1 <= n <= 4 for n in calls)


def test_fresh_remote_window_ignores_invalid_huge_keys_and_reports_gaps(db):
    for n in [1, 2, 3, 4]: storage.save_draw(draw(n))
    for key in [10000, 10001, 1000000001]: insert(key, json.dumps(draw(4)))
    def remote(game, contest=None):
        if contest is None: return draw(6)
        raise OSError('missing')
    with patch('lotomaster.engine.fetch_draw', side_effect=remote):
        h = client.get('/api/v1/megasena/history?limit=4').json()
        r = client.get('/api/v1/megasena/results?limit=4').json()
    assert [x['contest'] for x in h['items']] == [6, 4, 3]
    assert h['missing_contests'] == [5] and h['expected_count'] == 4
    assert [x['contest'] for x in r['items']] == [6, 4, 3]
    assert r['partial'] and r['expected_count'] == 4


def test_budget_exhaustion_is_explicit_and_online_fetch_still_works(db, monkeypatch):
    monkeypatch.setattr(storage, 'MAX_SCAN_ROWS', 3)
    storage.save_draw(draw(1))
    for n in range(10, 14): insert(n, '{bad')
    with pytest.raises(RuntimeError, match='Limite de leitura'):
        storage.latest_draw('megasena')
    with pytest.raises(RuntimeError, match='Limite de leitura'):
        storage.list_draws('megasena', 2)
    with patch('lotomaster.engine.fetch_draw', side_effect=OSError('offline')):
        r = client.get('/api/v1/megasena/results?limit=1')
    assert r.status_code == 502 and 'Limite de leitura' in r.json()['detail']
    engine._latest_cache.clear()
    with patch('lotomaster.engine.fetch_draw', return_value=draw(1)):
        r = client.get('/api/v1/megasena/results?limit=1')
    assert r.status_code == 200 and r.json()['items'][0]['contest'] == 1


def test_bounded_window_and_oversized_or_fractional_keys(db, monkeypatch):
    monkeypatch.setattr(storage, 'MAX_PAYLOAD_BYTES', 100)
    storage.save_draw(draw(1))
    insert(2, 'x' * 101)
    insert(1.5, json.dumps(draw(1)))
    assert storage.get_draw('megasena', 2) is None
    assert [x['contest'] for x in storage.list_draws_range('megasena', 1, 2)] == [1]
    with pytest.raises(ValueError, match='excessiva'):
        storage.list_draws_range('megasena', 1, 501)
