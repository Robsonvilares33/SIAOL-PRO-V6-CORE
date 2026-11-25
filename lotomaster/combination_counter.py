"""Contagem exata de combinações da Lotofácil; sem gerar ou persistir jogos."""
from math import comb


def count_lotofacil_combinations(pick_count: int, fixed_count: int, removed_count: int) -> dict:
    """Retorna C(25-f-r, p-f), rejeitando valores que não sejam inteiros estritos."""
    values = {
        "pick_count": pick_count,
        "fixed_count": fixed_count,
        "removed_count": removed_count,
    }
    if any(type(value) is not int for value in values.values()):
        raise ValueError("pick_count, fixed_count e removed_count devem ser inteiros.")

    p, f, r = pick_count, fixed_count, removed_count
    if not 15 <= p <= 20:
        raise ValueError("pick_count deve estar entre 15 e 20.")
    if f < 0 or r < 0:
        raise ValueError("fixed_count e removed_count devem ser maiores ou iguais a zero.")
    if f > p:
        raise ValueError("fixed_count não pode exceder pick_count.")
    if f + r > 25:
        raise ValueError("A soma de fixas e removidas não pode exceder 25.")
    if p > 25 - r:
        raise ValueError("pick_count não pode exceder as dezenas não removidas.")

    n, k = 25 - f - r, p - f
    total = comb(n, k)
    return {
        "game": "lotofacil",
        "pick_count": p,
        "fixed_count": f,
        "removed_count": r,
        "available_after_removals": 25 - r,
        "free_to_choose": n,
        "free_picks": k,
        "formula": f"C(25 - {f} - {r}, {p} - {f}) = C({n}, {k})",
        "formula_expression": f"C({n}, {k})",
        "combination_count": str(total),
        "disclaimer": (
            "Esta resposta é apenas uma contagem combinatória, não representa chance de prêmio nem garantia. "
            "A condição de que as dezenas fixas estejam corretas não está demonstrada."
        ),
    }
