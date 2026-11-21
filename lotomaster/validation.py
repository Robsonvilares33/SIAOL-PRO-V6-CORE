"""Validação estrita de resultados normalizados usados em estatísticas."""
from .catalog import get_spec

MAX_DRAWS = 500
MAX_CONTEST = 1_000_000_000
MONTHS = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "março": 3, "abril": 4,
    "maio": 5, "junho": 6, "julho": 7, "agosto": 8, "setembro": 9,
    "outubro": 10, "novembro": 11, "dezembro": 12,
}


def _sequence(value, size, low, high, name, *, unique=True):
    if not isinstance(value, list) or len(value) != size:
        raise ValueError(f"{name} deve conter exatamente {size} valores.")
    if any(type(n) is not int or not low <= n <= high for n in value):
        raise ValueError(f"{name} contém valores inválidos.")
    if unique and len(set(value)) != size:
        raise ValueError(f"{name} contém valores duplicados.")
    return value[:]


def validate_draw(game, draw, *, require_game=False, require_special=False):
    spec = get_spec(game)
    key = spec['key']
    if not isinstance(draw, dict):
        raise ValueError('Cada concurso deve ser um objeto.')
    if (require_game or 'game' in draw) and draw.get('game') != key:
        raise ValueError('Todos os concursos precisam ser da mesma modalidade.')
    contest = draw.get('contest')
    if type(contest) is not int or not 1 <= contest <= MAX_CONTEST:
        raise ValueError('Número de concurso inválido.')
    nums = _sequence(draw.get('numbers'), spec['draw_size'], spec['minimum'], spec['maximum'], 'numbers', unique=key != 'supersete')
    result = {'game': key, 'contest': contest, 'numbers': nums}
    second = draw.get('second_numbers')
    if second not in (None, []):
        if key != 'duplasena':
            raise ValueError('Segundo sorteio incompatível com a modalidade.')
        result['second_numbers'] = _sequence(second, 6, 1, 50, 'second_numbers')
    elif require_special and key == 'duplasena':
        raise ValueError('Segundo sorteio ausente.')
    else:
        result['second_numbers'] = []
    trevos = draw.get('trevos')
    if trevos not in (None, []):
        if key != 'maismilionaria':
            raise ValueError('Trevos incompatíveis com a modalidade.')
        result['trevos'] = _sequence(trevos, 2, 1, 6, 'trevos')
    elif require_special and key == 'maismilionaria':
        raise ValueError('Trevos ausentes.')
    else:
        result['trevos'] = []
    ordered = draw.get('ordered_numbers')
    if ordered is not None and ordered != []:
        if not isinstance(ordered, list):
            raise ValueError('Ordem de sorteio inválida.')
        n = spec['draw_size']
        valid_sizes = {n}
        if key == 'duplasena' and result['second_numbers']:
            valid_sizes.add(n + 6)
        if key == 'maismilionaria' and result['trevos']:
            valid_sizes.add(n + 2)
        if len(ordered) not in valid_sizes:
            raise ValueError('Tamanho da ordem de sorteio inválido.')
        first = _sequence(ordered[:n], n, spec['minimum'], spec['maximum'], 'ordered_numbers', unique=key != 'supersete')
        if (first != nums if key == 'supersete' else sorted(first) != sorted(nums)):
            raise ValueError('Ordem de sorteio não corresponde às dezenas.')
        if len(ordered) > n:
            extras = result['second_numbers'] if key == 'duplasena' else result['trevos']
            checked = _sequence(ordered[n:], len(extras), 1, 50 if key == 'duplasena' else 6, 'ordered_numbers extras')
            if sorted(checked) != sorted(extras):
                raise ValueError('Ordem de sorteio não corresponde aos valores extras.')
        result['ordered_numbers'] = ordered[:]
    else:
        result['ordered_numbers'] = nums[:]
    month = draw.get('month')
    if month is not None:
        if key != 'diadesorte' or not isinstance(month, dict):
            raise ValueError('Mês da sorte inválido.')
        name, number = month.get('name'), month.get('number')
        if not isinstance(name, str) or len(name) > 20 or MONTHS.get(name.casefold()) is None or type(number) is not int or MONTHS[name.casefold()] != number:
            raise ValueError('Mês da sorte inválido.')
        result['month'] = {'name': name, 'number': number}
    else:
        result['month'] = None
        if require_special and key == 'diadesorte':
            raise ValueError('Mês da Sorte ausente.')
    team = draw.get('team')
    if team is not None and (key != 'timemania' or not isinstance(team, str) or not team.strip() or len(team) > 100):
        raise ValueError('Time inválido.')
    result['team'] = team
    if require_special and key == 'timemania' and team is None:
        raise ValueError('Time do Coração ausente.')
    special = draw.get('special_draw', False)
    if type(special) is not bool:
        raise ValueError('Indicador de concurso especial inválido.')
    result['special_draw'] = special
    return result


def validate_draws(game, draws, *, require_game=False, max_draws=MAX_DRAWS):
    if not isinstance(draws, list) or len(draws) > max_draws:
        raise ValueError(f'Informe até {max_draws} concursos.')
    validated = []
    contests = set()
    for draw in draws:
        item = validate_draw(game, draw, require_game=require_game)
        if item['contest'] in contests:
            raise ValueError('Concurso duplicado.')
        contests.add(item['contest'])
        validated.append(item)
    return validated
