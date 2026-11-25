"""Regressões offline das falhas encontradas na revisão independente."""
from copy import deepcopy
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from lotomaster.api import app
from lotomaster.caixa import normalize_draw
from lotomaster.catalog import LOTTERIES

CLIENT = TestClient(app)


def fixture(game):
    spec = LOTTERIES[game]
    numbers = [0] * 7 if game == 'supersete' else list(range(spec['minimum'], spec['minimum'] + spec['draw_size']))
    draw = {'game': game, 'contest': 50, 'numbers': numbers}
    ticket = {'numbers': ([0] * 7 if game == 'supersete' else list(range(spec['minimum'], spec['minimum'] + spec['pick_size'])))}
    if game == 'duplasena': draw['second_numbers'] = [1, 2, 3, 4, 5, 6]
    if game == 'maismilionaria':
        draw['trevos'] = [1, 2]
        ticket['bonus'] = {'trevos': [1, 2]}
    if game == 'diadesorte':
        draw['month'] = {'name': 'Janeiro', 'number': 1}; ticket['bonus'] = {'month': 1}
    if game == 'timemania':
        draw['team'] = 'Teste FC'; ticket['bonus'] = {'team': 'Teste FC'}
    return draw, ticket


def post(game, draw, ticket):
    return CLIENT.post(f'/api/v1/{game}/simulate', json={'draw': draw, 'tickets': [ticket]})


@pytest.mark.parametrize('game', LOTTERIES)
def test_all_modalities_complete_and_cardinality_range_duplicates(game):
    draw, ticket = fixture(game)
    assert post(game, draw, ticket).status_code == 200
    for numbers in (draw['numbers'][:-1], draw['numbers'] + [draw['numbers'][0]],
                    [LOTTERIES[game]['maximum'] + 1] + draw['numbers'][1:]):
        assert post(game, {**draw, 'numbers': numbers}, ticket).status_code == 422
    if game != 'supersete':
        numbers = draw['numbers'].copy(); numbers[1] = numbers[0]
        assert post(game, {**draw, 'numbers': numbers}, ticket).status_code == 422
    else:
        assert post(game, draw, ticket).status_code == 200  # repeated digits across columns are valid


@pytest.mark.parametrize('game,field,invalid', [
    ('duplasena', 'second_numbers', None), ('duplasena', 'second_numbers', [1]*6),
    ('duplasena', 'second_numbers', [1,2,3,4,5,51]), ('duplasena', 'second_numbers', [1,2]),
    ('maismilionaria', 'trevos', None), ('maismilionaria', 'trevos', [1,1]),
    ('maismilionaria', 'trevos', [1,7]), ('maismilionaria', 'trevos', [1]),
    ('diadesorte', 'month', None), ('diadesorte', 'month', {'name':'Janeiro','number':2}),
    ('timemania', 'team', None), ('timemania', 'team', '  '),
])
def test_incomplete_or_invalid_special_draws_are_rejected(game, field, invalid):
    draw, ticket = fixture(game); draw[field] = invalid
    assert post(game, draw, ticket).status_code == 422


@pytest.mark.parametrize('source', ['latest', 'cache', 'fetch'])
def test_server_sources_are_validated_before_comparison(source):
    draw, ticket = fixture('maismilionaria'); draw['trevos'] = []
    with patch('lotomaster.api.latest_result', return_value=draw), patch('lotomaster.api.storage.get_draw', return_value=draw if source == 'cache' else None), patch('lotomaster.api.fetch_draw', return_value=draw), patch('lotomaster.api.storage.save_draw'):
        payload = {'tickets':[ticket]}
        if source != 'latest': payload['contest'] = 50
        assert CLIENT.post('/api/v1/maismilionaria/simulate', json=payload).status_code == 422


@pytest.mark.parametrize('game,bonus', [
    ('diadesorte', {}), ('diadesorte', {'month':13}), ('diadesorte', {'month':1.5}),
    ('timemania', {}), ('timemania', {'team':'  '}),
    ('maismilionaria', {}), ('maismilionaria', {'trevos':[1,2,'bad']}),
    ('maismilionaria', {'trevos':[1,2.8]}), ('megasena', {'month':1}),
    ('supersete', {'team':'X'}),
])
def test_incomplete_or_invalid_ticket_specials(game, bonus):
    draw, ticket = fixture(game); ticket['bonus'] = bonus
    assert post(game, draw, ticket).status_code == 422


def test_timemania_generator_requires_team():
    with patch('lotomaster.engine.storage.latest_draw', return_value=None):
        assert CLIENT.post('/api/v1/timemania/generate', json={}).status_code == 422
        response = CLIENT.post('/api/v1/timemania/generate', json={'bonus':{'team':'Teste FC'}})
    assert response.status_code == 200
    draw, _ = fixture('timemania')
    assert post('timemania', draw, response.json()['items'][0]).status_code == 200


def test_invalid_order_and_game_are_rejected():
    draw, ticket = fixture('maismilionaria')
    for change in ({'game':'quina'}, {'contest':0}, {'ordered_numbers':[1,2,3,4,5,6,1,3]}, {'month':{'name':'Janeiro','number':1}}):
        assert post('maismilionaria', {**draw, **change}, ticket).status_code == 422


def test_generator_and_simulator_agree_on_multiple_trevo_counts():
    with patch('lotomaster.engine.storage.latest_draw', return_value=None):
        for count in (1, 2.5, True, '2', 7):
            resp = CLIENT.post('/api/v1/maismilionaria/generate', json={'bonus':{'trevo_count':count}, 'seed':1})
            assert resp.status_code == 422
        draw, _ = fixture('maismilionaria')
        for trevo_count in range(2, 7):
            generated = CLIENT.post('/api/v1/maismilionaria/generate', json={
                'count':10, 'bonus':{'trevo_count':trevo_count}, 'seed':1,
            })
            assert generated.status_code == 200
            for ticket in generated.json()['items']:
                assert len(ticket['bonus']['trevos']) == trevo_count
                assert post('maismilionaria', draw, ticket).status_code == 200


@pytest.mark.parametrize('raw', [
    {'dezenasSorteadasOrdemSorteio':['9','22','25','26','28','50','2','3']},
    {'listaDezenas':['9','22','25','26','28','50','2','3']},
    {'listaDezenas':['9','22','25','26','28','50'], 'trevosSorteados':['2','3']},
])
def test_python_normalizes_million_eight_numbers(raw):
    result = normalize_draw('maismilionaria', {'numero':407, **raw})
    assert result['numbers'] == [9,22,25,26,28,50]
    assert result['trevos'] == [2,3]
    assert post('maismilionaria', result, {'numbers':[9,22,1,2,3,4], 'bonus':{'trevos':[2,4]}}).json()['results'][0]['award'] == 'Faixa 10 · 2 acertos + 1 trevo'


@pytest.mark.parametrize('draws,partial,source,warning', [
    ([{'game':'megasena','contest':10,'numbers':[1,2,3,4,5,6],'source':'cache','warning':'cache antigo'},{'game':'megasena','contest':8,'numbers':[1,2,3,4,5,6]}], True, 'cache', 'cache antigo'),
    ([{'game':'megasena','contest':2,'numbers':[1,2,3,4,5,6],'source':'cache'},{'game':'megasena','contest':1,'numbers':[1,2,3,4,5,6]}], False, 'cache', 'cache do servidor'),
    ([{'game':'megasena','contest':2,'numbers':[1,2,3,4,5,6],'source':'CAIXA via Cloudflare Worker'},{'game':'megasena','contest':1,'numbers':[1,2,3,4,5,6]}], False, 'CAIXA via Cloudflare Worker', None),
    ([], True, 'origem não informada', None),
])
def test_assistant_propagates_cache_and_partial(draws, partial, source, warning):
    with patch('lotomaster.api.list_results', return_value=draws):
        resp = CLIENT.get('/api/v1/megasena/assistant?limit=3')
    assert resp.status_code == 200
    body=resp.json(); assert body['partial'] is partial and body['source'] == source
    if warning: assert warning in body['warning']
    else: assert 'warning' not in body
    assert body['expected_count'] == min(3, max((d['contest'] for d in draws), default=0))


def test_client_analytics_never_assert_official_history():
    for game in ('duplasena','maismilionaria','megasena'):
        draw, _ = fixture(game); draw['special_draw'] = True
        for route in ('statistics', 'assistant'):
            response = CLIENT.post(f'/api/v1/{game}/{route}/from-draws', json={'draws':[draw]})
            assert response.status_code == 200
            body = response.json()
            assert body['provenance']['verified'] is False
            text = response.text.lower()
            assert 'segundo sorteio oficial' not in text and 'sequência oficial' not in text
            assert 'officially_marked_special_draws' not in text
            assert 'retornado pela caixa' not in text
    draw, _ = fixture('duplasena')
    body=CLIENT.post('/api/v1/duplasena/statistics/from-draws',json={'draws':[draw]}).json()
    assert 'não é verificada' in body['tables']['second-draw']['data']['note']
