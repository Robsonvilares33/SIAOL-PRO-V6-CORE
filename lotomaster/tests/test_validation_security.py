import asyncio
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from lotomaster.analytics import analyze_draws
from lotomaster.api import app
from lotomaster.caixa import normalize_draw
from lotomaster.catalog import LOTTERIES
from lotomaster.request_limits import DrawBodyLimit, MAX_HISTORY_BODY
from lotomaster.validation import MAX_DRAWS


def draw(game='megasena', contest=1):
    spec = LOTTERIES[game]
    numbers = list(range(spec['minimum'], spec['minimum'] + spec['draw_size']))
    return {'game': game, 'contest': contest, 'numbers': numbers}


@pytest.mark.parametrize('game', list(LOTTERIES))
def test_all_modalities_valid_main_results(game):
    result = analyze_draws(game, [draw(game)])
    assert result['draws_analyzed'] == 1
    assert all(0 <= row['percent'] <= 100 for row in result['frequency'])


@pytest.mark.parametrize('bad', [
    [1, 2, 3, 4, 5], [1, 2, 3, 4, 5, 5], [1, 2, 3, 4, 5, 61],
    [0, 2, 3, 4, 5, 6], [True, 2, 3, 4, 5, 6],
    ['1', 2, 3, 4, 5, 6], [1.0, 2, 3, 4, 5, 6],
    list(range(10000)), None, '1,2,3,4,5,6',
])
def test_bad_main_numbers_rejected(bad):
    data = draw()
    data['numbers'] = bad
    with pytest.raises(ValueError):
        analyze_draws('megasena', [data])


@pytest.mark.parametrize('contest', [0, -1, True, 1.0, '1', 10**20, None])
def test_bad_contests_rejected(contest):
    with pytest.raises(ValueError):
        analyze_draws('megasena', [draw(contest=contest)])


def test_duplicate_contests_and_direct_limit():
    with pytest.raises(ValueError, match='duplicado'):
        analyze_draws('megasena', [draw(), draw()])
    with pytest.raises(ValueError):
        analyze_draws('megasena', [draw(contest=i + 1) for i in range(MAX_DRAWS + 1)])


def test_supersete_repeated_digits_are_legal_and_frequency_bounded():
    d = draw('supersete')
    d['numbers'] = [1, 1, 1, 1, 1, 1, 1]
    report = analyze_draws('supersete', [d])
    row = next(x for x in report['frequency'] if x['number'] == 1)
    assert row['count'] == 1 and row['percent'] == 100
    assert all(column['digits'][1]['count'] == 1 for column in report['special']['columns'])


@pytest.mark.parametrize('key,value', [
    ('ordered_numbers', [1, 2, 3, 4, 5, 7]),
    ('ordered_numbers', [1] * 100),
    ('second_numbers', [1, 2, 3, 4, 5, 6]),
    ('trevos', [1, 2]), ('month', {'name': 'Janeiro', 'number': 1}),
    ('team', 'time'), ('special_draw', 'true'),
])
def test_untrusted_secondary_fields_rejected(key, value):
    d = draw(); d[key] = value
    with pytest.raises(ValueError):
        analyze_draws('megasena', [d])


def test_extra_fields_and_order_must_match():
    d = draw('duplasena'); d['second_numbers'] = [1, 2, 3, 4, 5, 5]
    with pytest.raises(ValueError): analyze_draws('duplasena', [d])
    d['second_numbers'] = [1, 2, 3, 4, 5, 6]
    d['ordered_numbers'] = d['numbers'] + [1, 2, 3, 4, 5, 7]
    with pytest.raises(ValueError): analyze_draws('duplasena', [d])
    d = draw('maismilionaria'); d['trevos'] = [1, 1]
    with pytest.raises(ValueError): analyze_draws('maismilionaria', [d])
    d['trevos'] = [1, 7]
    with pytest.raises(ValueError): analyze_draws('maismilionaria', [d])
    d = draw('diadesorte'); d['month'] = {'name': 'Janeiro', 'number': 12}
    with pytest.raises(ValueError): analyze_draws('diadesorte', [d])


@pytest.mark.parametrize('numbers', [['01', '02', '03', '04', '05', '05'], ['01', '02', '03', '04', '05', '61'], ['01', '02', '03', '04', '05', 'bad'], ['01'] * 100])
def test_caixa_invalid_numbers_never_silently_dropped(numbers):
    with pytest.raises(ValueError): normalize_draw('megasena', {'numero': 1, 'listaDezenas': numbers})


def test_caixa_two_draws_and_trevos_required_with_order_fallback():
    with pytest.raises(ValueError): normalize_draw('duplasena', {'numero': 1, 'listaDezenas': ['01', '02', '03', '04', '05', '06']})
    with pytest.raises(ValueError): normalize_draw('maismilionaria', {'numero': 1, 'listaDezenas': ['01', '02', '03', '04', '05', '06']})
    ordered = ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12']
    assert normalize_draw('duplasena', {'numero': 1, 'dezenasSorteadasOrdemSorteio': ordered})['second_numbers'] == list(range(7, 13))
    assert normalize_draw('maismilionaria', {'numero': 1, 'dezenasSorteadasOrdemSorteio': ordered[:6] + ['02', '03']})['trevos'] == [2, 3]


def test_empty_pareto_has_no_phantom_hit():
    assert analyze_draws('megasena', [])['tables']['pareto']['data']['total_appearances'] == 0


def test_public_assistant_is_local_by_default_and_explicit_gemini_request_fails_closed():
    client = TestClient(app)
    draws = [draw()]
    with patch.dict('os.environ', {'GEMINI_API_KEY': 'fake-test-key'}, clear=True), patch('lotomaster.assistant.requests.post', side_effect=AssertionError('Gemini called')) as post, patch('lotomaster.api.list_results', return_value=draws):
        r = client.get('/api/v1/megasena/assistant')
        assert r.status_code == 200 and r.json()['ai']['status'] == 'local_only'
        explicit = client.get('/api/v1/megasena/assistant?use_gemini=true')
        assert explicit.status_code == 503
        r = client.post('/api/v1/megasena/assistant/from-draws', json={'draws': draws})
        assert r.status_code == 200 and r.json()['ai']['status'] == 'local_only'
        post.assert_not_called()


@pytest.mark.parametrize('endpoint', ['statistics', 'assistant'])
def test_http_validation_and_body_limit(endpoint):
    client = TestClient(app)
    url = f'/api/v1/megasena/{endpoint}/from-draws'
    assert client.post(url, json={'draws': [draw(), draw()]}).status_code == 422
    assert client.post(url, json={'draws': [{**draw(), 'numbers': [1] * 6}]}).status_code == 422
    assert client.post(url, json={'draws': [draw(contest=i + 1) for i in range(501)]}).status_code == 422
    assert client.post(url, content=b' ' * (MAX_HISTORY_BODY + 1), headers={'content-type': 'application/json'}).status_code == 413


def test_limit_applies_to_chunked_body_without_content_length():
    async def run():
        invoked = []
        async def app(scope, receive, send): invoked.append(True)
        chunks = iter([{'type': 'http.request', 'body': b'a' * 600000, 'more_body': True}, {'type': 'http.request', 'body': b'b' * 400001, 'more_body': False}])
        sent = []
        async def receive(): return next(chunks)
        async def send(message): sent.append(message)
        await DrawBodyLimit(app)({'type': 'http', 'method': 'POST', 'path': '/api/v1/megasena/statistics/from-draws', 'headers': []}, receive, send)
        assert not invoked and sent[0]['status'] == 413
    asyncio.run(run())
