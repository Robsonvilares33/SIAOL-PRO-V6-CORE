"""Validação estrutural de concursos enviados pelo cliente; não autentica a origem."""
from .catalog import get_spec


def validate_client_draws(game: str, draws: list[dict], *, require_game: bool = True,
                          require_special: bool = False, limit: int = 5000) -> None:
    """Rejeita dados incompletos/inconsistentes antes de calcular; não persiste dados."""
    spec = get_spec(game)
    if not isinstance(draws, list) or not 1 <= len(draws) <= limit:
        raise ValueError(f"Informe de 1 a {limit} concursos.")
    seen = set()
    for draw in draws:
        if not isinstance(draw, dict):
            raise ValueError("Cada concurso deve ser um objeto.")
        game_value = draw.get("game")
        if game_value != spec["key"] and (require_game or game_value is not None):
            raise ValueError("Todos os concursos precisam pertencer à modalidade solicitada.")
        contest = draw.get("contest")
        if type(contest) is not int or contest < 1:
            raise ValueError("O número do concurso deve ser inteiro positivo.")
        if contest in seen:
            raise ValueError(f"Concurso duplicado: {contest}.")
        seen.add(contest)
        _numbers(draw.get("numbers"), spec["draw_size"], spec["minimum"], spec["maximum"],
                 distinct=spec["key"] != "supersete", label="dezenas principais")
        if spec["key"] == "duplasena" and (require_special or draw.get("second_numbers")):
            _numbers(draw.get("second_numbers"), 6, spec["minimum"], spec["maximum"], label="second_numbers (segundo sorteio)")
        if spec["key"] == "maismilionaria" and (require_special or draw.get("trevos")):
            _numbers(draw.get("trevos"), 2, 1, 6, label="trevos")
        if spec["key"] == "diadesorte" and (require_special or draw.get("month") is not None):
            month = draw.get("month")
            if not isinstance(month, dict) or type(month.get("number")) is not int or not 1 <= month["number"] <= 12:
                raise ValueError("Mês da Sorte inválido no resultado informado.")
        if spec["key"] == "timemania" and (require_special or draw.get("team") is not None):
            team = draw.get("team")
            if not isinstance(team, str) or not team.strip() or len(team) > 200:
                raise ValueError("Time do Coração inválido no resultado informado.")


def _numbers(values, size: int, low: int, high: int, *, distinct: bool = True, label: str) -> None:
    if not isinstance(values, list) or len(values) != size:
        raise ValueError(f"Resultado inválido: {label} precisa conter {size} valores.")
    if any(type(value) is not int or value < low or value > high for value in values):
        raise ValueError(f"Resultado inválido: {label} fora do intervalo {low}–{high}.")
    if distinct and len(set(values)) != len(values):
        raise ValueError(f"Resultado inválido: {label} contém valores repetidos.")
