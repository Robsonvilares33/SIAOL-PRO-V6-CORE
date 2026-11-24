"""Busca local por concursos que contêm todas as dezenas consultadas."""

from .client_draws import validate_client_draws

MATCH_MODES = {
    "contains_all": "contém todas as dezenas selecionadas",
    "exact": "combinação exata",
    "excludes_all": "não contém nenhuma das dezenas selecionadas",
}

DISCLAIMER = (
    "A busca considera somente os concursos enviados nesta solicitação; a amostra pode ser parcial. "
    "A origem e a integridade dos dados enviados pelo cliente não são verificadas pelo servidor. "
    "O resultado indica coocorrência histórica e não prevê sorteios futuros."
)


def search_lotofacil_history(
    numbers: list[int], draws: list[dict], match_mode: str = "contains_all"
) -> dict:
    """Pesquisar concursos por inclusão, igualdade exata ou exclusão de dezenas."""
    if not isinstance(numbers, list) or not 1 <= len(numbers) <= 15:
        raise ValueError("Informe de 1 a 15 dezenas para pesquisar.")
    if any(type(number) is not int or not 1 <= number <= 25 for number in numbers):
        raise ValueError("As dezenas devem ser inteiros de 1 a 25.")
    if len(set(numbers)) != len(numbers):
        raise ValueError("As dezenas não podem se repetir.")
    if match_mode not in MATCH_MODES:
        raise ValueError("Critério de pesquisa desconhecido.")
    if match_mode == "exact" and len(numbers) != 15:
        raise ValueError("A combinação exata da Lotofácil exige exatamente 15 dezenas.")

    validate_client_draws("lotofacil", draws, require_game=False, limit=5000)
    selected = set(numbers)
    matches = []
    for draw in draws:
        drawn = set(draw["numbers"])
        if match_mode == "contains_all" and selected.issubset(drawn):
            matches.append(draw)
        elif match_mode == "exact" and selected == drawn:
            matches.append(draw)
        elif match_mode == "excludes_all" and selected.isdisjoint(drawn):
            matches.append(draw)
    return {
        "numbers": numbers,
        "match_mode": match_mode,
        "match_description": MATCH_MODES[match_mode],
        "matching_draws": matches,
        "match_count": len(matches),
        "examined_count": len(draws),
        "disclaimer": DISCLAIMER,
    }
