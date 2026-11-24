"""Desdobramento local de dezenas repetidas da Lotofácil; não prevê resultados."""
from itertools import combinations
from math import comb
from typing import Iterable

from .catalog import get_spec
from .engine import _validate_generator_filters, diagnose_ticket_filters

MAX_GAMES = 1000
PREVIOUS_DRAW_SIZE = 15
MIN_REPEATED = 6
MAX_REPEATED = 12


def repeated_closure(
    previous_draw: Iterable[int],
    repeated: Iterable[int],
    *,
    filters: dict | None = None,
    reference_draw: Iterable[int] | None = None,
    offset: int = 0,
    page_size: int = MAX_GAMES,
) -> dict:
    """Generate one page from the chosen repeats and diagnose every filter."""
    previous = _numbers(previous_draw, "previous_draw")
    selected = _numbers(repeated, "repeated")
    if len(previous) != PREVIOUS_DRAW_SIZE:
        raise ValueError("previous_draw deve conter exatamente 15 dezenas distintas")
    if not MIN_REPEATED <= len(selected) <= MAX_REPEATED:
        raise ValueError("repeated deve conter de 6 a 12 dezenas distintas")
    if not set(selected).issubset(previous):
        raise ValueError("todas as repetidas devem pertencer ao resultado anterior")
    if type(offset) is not int or offset < 0:
        raise ValueError("offset deve ser um inteiro não negativo")
    if type(page_size) is not int or not 1 <= page_size <= MAX_GAMES:
        raise ValueError(f"page_size deve ser inteiro entre 1 e {MAX_GAMES}")

    chosen_filters = {} if filters is None else filters
    _validate_generator_filters({"key": "lotofacil", "minimum": 1, "maximum": 25}, chosen_filters, 15)
    has_repeat_filter = any(chosen_filters.get(key) not in (None, "") for key in ("min_repeated", "max_repeated"))
    if has_repeat_filter and reference_draw is None:
        raise ValueError("Filtros de repetidas exigem um concurso de referência explícito")
    reference = None if reference_draw is None else _numbers(reference_draw, "reference_draw")
    if has_repeat_filter and reference is not None and len(reference) != get_spec("lotofacil")["draw_size"]:
        raise ValueError("reference_draw deve conter exatamente 15 dezenas")

    absent = tuple(number for number in range(1, 26) if number not in set(previous))
    choose_count = 15 - len(selected)
    total = comb(len(absent), choose_count)
    if total > MAX_GAMES:
        raise ValueError(f"desdobramento exige {total} jogos; limite é {MAX_GAMES}")
    items = []
    if offset < total:
        for rank, choice in enumerate(combinations(absent, choose_count)):
            if rank < offset:
                continue
            game = sorted((*selected, *choice))
            reasons = diagnose_ticket_filters("lotofacil", game, chosen_filters, reference)
            items.append({"numbers": game, "approved": not reasons, "reasons": reasons})
            if len(items) >= page_size:
                break
    next_offset = offset + len(items) if offset + len(items) < total else None
    return {
        "label": f"Desdobramento de repetidas — {len(absent)} ausentes, {choose_count} por jogo",
        "previous_draw": list(previous),
        "repeated": list(selected),
        "absent": list(absent),
        "game_count": total,
        "candidate_count": total,
        "offset": offset,
        "page_size": page_size,
        "returned_count": len(items),
        "approved_count": sum(item["approved"] for item in items),
        "next_offset": next_offset,
        "items": items,
        "games": [item["numbers"] for item in items],
        "disclaimer": "Enumeração combinatória local baseada somente nos números enviados; filtros são estruturais e locais; não prevê sorteios, não garante prêmio e não afirma reproduzir algoritmos proprietários.",
    }


def _numbers(values: Iterable[int], name: str) -> tuple[int, ...]:
    if isinstance(values, (str, bytes)):
        raise ValueError(f"{name} deve ser uma coleção de inteiros")
    try:
        result = tuple(values)
    except TypeError as exc:
        raise ValueError(f"{name} deve ser uma coleção de inteiros") from exc
    if any(type(value) is not int for value in result):
        raise ValueError(f"{name} deve conter apenas inteiros (booleanos não são aceitos)")
    if len(set(result)) != len(result):
        raise ValueError(f"{name} não pode conter duplicatas")
    if any(value < 1 or value > 25 for value in result):
        raise ValueError(f"{name} contém dezenas fora da faixa 1..25")
    return tuple(sorted(result))
