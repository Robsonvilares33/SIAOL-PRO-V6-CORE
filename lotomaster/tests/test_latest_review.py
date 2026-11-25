"""Offline regressions for latest independent review."""
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from lotomaster import engine
from lotomaster.api import app
from lotomaster.caixa import normalize_draw

client = TestClient(app)


def test_history_ttl_cache_provenance_and_warning():
    engine._latest_cache.clear()
    one = {'game':'megasena','contest':1,'numbers':[1,2,3,4,5,6]}
    with patch('lotomaster.engine.storage.latest_draw', return_value=one), \
         patch('lotomaster.engine.storage.list_draws_range', return_value=[one]), \
         patch('lotomaster.engine.storage.save_draw'), \
         patch('lotomaster.engine.fetch_draw', return_value=one) as fetch:
        first = client.get('/api/v1/megasena/history?limit=100').json()
        second = client.get('/api/v1/megasena/history?limit=100').json()
    assert fetch.call_count == 1
    assert first['provenance']['latest_lookup'] == 'server_fetch'
    assert first['provenance']['recently_checked'] is True
    assert second['provenance']['latest_lookup'] == 'server_cache'
    assert second['provenance']['recently_checked'] is True
    assert first['provenance']['last_successful_lookup_at'] == second['provenance']['last_successful_lookup_at']
    assert first['provenance']['verified'] is second['provenance']['verified'] is False
    assert 'warning' not in first and 'warning' not in second
    assert second['missing_contests'] == [] and second['next_before'] is None
    engine._latest_cache.clear()


def test_team_whitespace_normalized_on_actual_api():
    draw = {'game':'timemania','contest':1,'numbers':[1,2,3,4,5,6,7], 'team':'  SÃO\t PAULO FC  '}
    ticket = {'numbers':[1,2,3,4,5,6,7,8,9,10], 'bonus':{'team':' são  paulo fc '}}
    res = client.post('/api/v1/timemania/simulate', json={'draw':draw,'tickets':[ticket]})
    assert res.status_code == 200
    assert res.json()['results'][0]['team_hit'] is True
    ticket['bonus']['team']='outro fc'
    assert client.post('/api/v1/timemania/simulate',json={'draw':draw,'tickets':[ticket]}).json()['results'][0]['team_hit'] is False


@pytest.mark.parametrize('extra', [
    {'trevosSorteados':['4','5']},
    {'dezenasSorteadasOrdemSorteio':['1','2','3','4','5','6','4','5']},
    {'dezenasSorteadasOrdemSorteio':['1','2','3','4','5','6','1','2'], 'trevosSorteados':['4','5']},
])
def test_milionaria_rejects_conflicting_raw_fields(extra):
    raw = {'numero':1,'listaDezenas':['1','2','3','4','5','6','1','2'],**extra}
    with pytest.raises(ValueError,match='contraditórios'):
        normalize_draw('maismilionaria',raw)


def test_milionaria_agreeing_unordered_trevos_are_accepted():
    draw=normalize_draw('maismilionaria',{'numero':1,'listaDezenas':['1','2','3','4','5','6','1','2'],'trevosSorteados':['2','1']})
    assert draw['trevos']==[2,1]
