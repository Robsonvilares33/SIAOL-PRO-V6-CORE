"""Regressions for the five independent-review follow-ups, all offline."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from lotomaster import engine, storage
from lotomaster.api import app
from lotomaster.caixa import normalize_draw

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


def test_pages_same_fetch_timestamp_and_expired_offline_warning(db):
    for n in range(1, 121): storage.save_draw(draw(n))
    # Patch the engine's clock reference, not the shared time module used by asyncio.
    clock = iter([100, 110, 191])
    with patch.object(engine, 'time', SimpleNamespace(monotonic=lambda: next(clock))), patch('lotomaster.engine.fetch_draw', side_effect=[draw(120), OSError('offline')]) as fetch:
        first = client.get('/api/v1/megasena/history?limit=100').json()
        second = client.get('/api/v1/megasena/history?limit=100&before=21').json()
        third = client.get('/api/v1/megasena/history?limit=100&before=21').json()
    assert fetch.call_count == 2
    assert [first['provenance']['latest_lookup'], second['provenance']['latest_lookup']] == ['server_fetch','server_cache']
    assert first['provenance']['recently_checked'] and second['provenance']['recently_checked']
    assert first['provenance']['last_successful_lookup_at'] == second['provenance']['last_successful_lookup_at']
    assert 'warning' not in first and 'warning' not in second
    assert second['items'][-1]['contest'] == 1 and not second['missing_contests']
    assert not third['provenance']['recently_checked'] and 'offline' in third['warning']
    assert 'last_successful_lookup_at' not in third['provenance']


def test_offline_fallback_with_no_success_never_claims_freshness(db):
    storage.save_draw(draw(3))
    with patch('lotomaster.engine.fetch_draw', side_effect=OSError('offline')):
        one = client.get('/api/v1/megasena/history?limit=1').json()
        two = client.get('/api/v1/megasena/history?limit=1&before=3').json()
    assert not one['provenance']['recently_checked'] and not two['provenance']['recently_checked']
    assert 'warning' in one and 'warning' in two


def test_raw_timemania_team_separators_are_spaces_and_match():
    raw = {'numero': 1, 'listaDezenas':[1,2,3,4,5,6,7], 'nomeTimeCoracaoMesSorte':' SÃO\t\nPAULO  FC '}
    normalized = normalize_draw('timemania', raw)
    assert normalized['team'] == 'SÃO PAULO FC'
    ticket = {'numbers':[1,2,3,4,5,6,7,8,9,10], 'bonus':{'team':'são paulo fc'}}
    result = client.post('/api/v1/timemania/simulate',json={'draw': normalized, 'tickets':[ticket]})
    assert result.status_code == 200 and result.json()['results'][0]['team_hit'] is True


def test_invalid_legacy_cache_skipped_and_missing_offline(db):
    storage.save_draw(draw(4)); storage.save_draw(draw(1))
    insert(3, json.dumps({**draw(3), 'numbers':[1,1,2,3,4,99]}))
    insert(2, '{invalid json')
    assert storage.get_draw('megasena',3) is None
    assert [x['contest'] for x in storage.list_draws_range('megasena',1,4)] == [4,1]
    with patch('lotomaster.engine.fetch_draw', side_effect=OSError('offline')):
        history=client.get('/api/v1/megasena/history?limit=4').json()
        results=client.get('/api/v1/megasena/results?limit=4').json()
    assert [x['contest'] for x in history['items']] == [4,1]
    assert history['missing_contests'] == [3,2] and 'warning' in history
    assert [x['contest'] for x in results['items']] == [4,1]
    assert results['partial'] is True and results['expected_count']==4 and 'warning' in results


def test_invalid_newest_cache_does_not_invent_offline_contest(db):
    storage.save_draw(draw(4)); storage.save_draw(draw(3)); storage.save_draw(draw(2))
    insert(5, json.dumps(draw(4)))  # key/payload mismatch is not evidence contest 5 exists
    assert storage.get_draw('megasena',5) is None
    assert storage.latest_draw('megasena')['contest'] == 4
    with patch('lotomaster.engine.fetch_draw', side_effect=OSError('offline')):
        latest=client.get('/api/v1/megasena/latest').json()
        history=client.get('/api/v1/megasena/history?limit=3').json()
        results=client.get('/api/v1/megasena/results?limit=3').json()
    assert latest['contest']==4 and 'warning' in latest
    assert history['missing_contests']==[] and [x['contest'] for x in history['items']]==[4,3,2]
    assert results['expected_count']==3 and results['partial'] is False and 'warning' in results


@pytest.mark.parametrize('limit', [1, 3])
def test_online_latest_repairs_invalid_key(db, limit):
    storage.save_draw(draw(4)); storage.save_draw(draw(3))
    insert(5, json.dumps(draw(4)))
    with patch('lotomaster.engine.fetch_draw', side_effect=lambda game, contest=None: draw(5 if contest is None else contest)):
        response = client.get(f'/api/v1/megasena/results?limit={limit}')
    assert response.status_code == 200
    result = response.json()
    assert result['items'][0]['contest'] == 5
    assert result['partial'] is False
    assert storage.get_draw('megasena', 5)['contest'] == 5


def test_invalid_cache_refetched_then_validated(db):
    storage.save_draw(draw(3)); insert(2,json.dumps({**draw(2),'numbers':[1,1,2,3,4,5]})); storage.save_draw(draw(1))
    with patch('lotomaster.engine.fetch_draw', side_effect=lambda game, contest=None: draw(3 if contest is None else contest)):
        page=client.get('/api/v1/megasena/history?limit=3').json()
    assert not page['missing_contests'] and storage.get_draw('megasena',2)['numbers']==[1,2,3,4,5,6]


def test_empty_history_contract_with_and_without_lookup(db):
    empty=client.get('/api/v1/megasena/history?before=1').json()
    assert empty['items']==[] and empty['expected_count']==0 and empty['missing_contests']==[] and empty['next_before'] is None
    assert empty['provenance']=={'latest_lookup':'unknown','recently_checked':False,'verified':False} and 'warning' in empty
    with patch('lotomaster.engine.latest_result', return_value={**draw(1), 'source':'cache','warning':'offline'}), patch('lotomaster.engine.storage.list_draws_range',return_value=[]):
        # Defensive branch when a latest contest is invalid/out of bounds (not reachable through normal validation).
        with patch('lotomaster.engine.int', side_effect=lambda x: 0 if x==1 else int(x), create=True):
            page=engine.list_history_page('megasena',limit=1)
    assert page['items']==[] and page['provenance']['latest_lookup']=='server_cache' and page['warning']=='offline'


@pytest.mark.parametrize('bridge,payload', [
    ('api_bridge.py', {'draws':[draw(1)]}),
    ('simulate_bridge.py', {'draw': {'game':'maismilionaria','contest':1,'numbers':[1,2,3,4,5,6],'trevos':[1,2]}, 'tickets':[]}),
    ('review_bridge.py', {'action':'validate','game':'megasena','draw':draw(1)}),
    ('review_bridge.py', {'action':'generate','payload':{'count':1,'bonus':{'team':'Teste'}}}),
])
def test_bridges_set_database_before_import(tmp_path, bridge, payload):
    path=Path(__file__).with_name(bridge)
    sentinel=tmp_path/'do-not-open.db'
    # run_path retains the imported module so its actual DB_PATH can be checked after bridge execution.
    script="import runpy,sys; runpy.run_path(sys.argv[1],run_name='__main__'); from lotomaster import storage; print('DB_PATH='+str(storage.DB_PATH),file=sys.stderr)"
    env={**os.environ,'LOTOMASTER_DB_PATH':str(sentinel)}
    proc=subprocess.run([sys.executable,'-c',script,str(path)],input=json.dumps(payload),text=True,capture_output=True,env=env)
    assert proc.returncode==0, proc.stderr
    dbpath=proc.stderr.split('DB_PATH=')[-1].strip()
    assert dbpath != str(sentinel) and ('lotomaster-' in dbpath) and not sentinel.exists()
    json.loads(proc.stdout)
