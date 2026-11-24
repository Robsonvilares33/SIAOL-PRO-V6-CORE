"""Fechamento exaustivo paginado; não implementa a lógica proprietária MazuSoft."""
from math import comb
from typing import Iterable

from .catalog import get_spec
from .engine import _validate_generator_filters, diagnose_ticket_filters

MAX_GAMES = 1000
MAX_POOL = 100
_UNSUPPORTED = {"supersete"}
_REPEAT_FILTERS = {"min_repeated", "max_repeated"}


def exhaustive_closure(
    lottery: str,
    pool: Iterable[int],
    pick_count: int,
    fixed: Iterable[int] = (),
    *,
    filters: dict | None = None,
    reference_draw: Iterable[int] | None = None,
    offset: int = 0,
    page_size: int = MAX_GAMES,
    max_pool: int = MAX_POOL,
) -> dict:
    """Return one bounded page and per-ticket filter diagnostics.

    ``offset`` is the zero-based rank in the complete lexicographic closure;
    pages are generated on demand without materializing earlier combinations.
    """
    try:
        spec = get_spec(lottery)
    except (KeyError, AttributeError, TypeError) as exc:
        raise ValueError("modalidade inválida") from exc
    if spec["key"] in _UNSUPPORTED or spec.get("bonus") is not None:
        raise ValueError("modalidade não suportada: bônus/colunas exigem dados adicionais")
    if type(page_size) is not int or not 1 <= page_size <= MAX_GAMES:
        raise ValueError(f"page_size deve ser inteiro entre 1 e {MAX_GAMES}")
    if type(offset) is not int or offset < 0:
        raise ValueError("offset deve ser um inteiro não negativo")
    if type(max_pool) is not int or not 1 <= max_pool <= MAX_POOL:
        raise ValueError(f"max_pool deve ser inteiro entre 1 e {MAX_POOL}")
    if type(pick_count) is not int or not spec["min_pick"] <= pick_count <= spec["max_pick"]:
        raise ValueError("pick_count fora dos tamanhos permitidos no catálogo")

    numbers = _validated_numbers(pool, "pool", spec["minimum"], spec["maximum"])
    if len(numbers) > max_pool:
        raise ValueError(f"pool excede o limite de {max_pool} dezenas")
    fixed_numbers = _validated_numbers(fixed, "fixed", spec["minimum"], spec["maximum"])
    if not set(fixed_numbers).issubset(numbers):
        raise ValueError("todas as dezenas fixas devem pertencer ao pool")
    if len(fixed_numbers) > pick_count:
        raise ValueError("quantidade de fixas excede pick_count")
    if len(numbers) < pick_count:
        raise ValueError("pool menor que pick_count")

    selected_filters = {} if filters is None else filters
    _validate_generator_filters(spec, selected_filters, pick_count)
    has_repeat_filter = any(selected_filters.get(key) not in (None, "") for key in _REPEAT_FILTERS)
    if has_repeat_filter and reference_draw is None:
        raise ValueError("Filtros de repetidas exigem um concurso de referência explícito")
    reference = None if reference_draw is None else _validated_numbers(reference_draw, "reference_draw", spec["minimum"], spec["maximum"])

    total = comb(len(numbers) - len(fixed_numbers), pick_count - len(fixed_numbers))
    fixed_set = set(fixed_numbers)
    optional = [number for number in numbers if number not in fixed_set]
    choose_count = pick_count - len(fixed_numbers)
    items = []
    if offset < total:
        for choice in _combinations_from_rank(optional, choose_count, offset):
            game = sorted((*fixed_numbers, *choice))
            reasons = diagnose_ticket_filters(spec["key"], game, selected_filters, reference)
            items.append({"numbers": game, "approved": not reasons, "reasons": reasons})
            if len(items) >= page_size:
                break

    next_offset = offset + len(items) if offset + len(items) < total else None
    return {
        "lottery": spec["key"],
        "pick_count": pick_count,
        "pool": list(numbers),
        "fixed": list(fixed_numbers),
        "coverage": "Enumeração lexicográfica local de todas as combinações do universo informado, em páginas; filtros são descrições locais e não garantem prêmio nem preveem sorteios.",
        "game_count": total,
        "candidate_count": total,
        "offset": offset,
        "page_size": page_size,
        "returned_count": len(items),
        "approved_count": sum(item["approved"] for item in items),
        "next_offset": next_offset,
        "items": items,
        # Kept for compatibility with callers that consume a page of game arrays.
        "games": [item["numbers"] for item in items],
    }


def _combinations_from_rank(values: list[int], choose_count: int, rank: int):
    """Yield lexicographic combinations starting at ``rank`` without skipping from 0."""
    n = len(values)
    total = comb(n, choose_count)
    if rank >= total:
        return
    if choose_count == 0:
        yield ()
        return

    remaining_rank = rank
    indices = []
    start = 0
    for position in range(choose_count):
        remaining_slots = choose_count - position - 1
        for candidate in range(start, n - remaining_slots):
            block = comb(n - candidate - 1, remaining_slots)
            if remaining_rank < block:
                indices.append(candidate)
                start = candidate + 1
                break
            remaining_rank -= block

    while True:
        yield tuple(values[index] for index in indices)
        for position in range(choose_count - 1, -1, -1):
            maximum = n - choose_count + position
            if indices[position] < maximum:
                indices[position] += 1
                for following in range(position + 1, choose_count):
                    indices[following] = indices[following - 1] + 1
                break
        else:
            return


def _validated_numbers(values: Iterable[int], name: str, minimum: int, maximum: int) -> tuple[int, ...]:
    if isinstance(values, (str, bytes)):
        raise ValueError(f"{name} deve ser uma coleção de inteiros")
    try:
        result = tuple(values)
    except TypeError as exc:
        raise ValueError(f"{name} deve ser uma coleção de inteiros") from exc
    if any(type(number) is not int for number in result):
        raise ValueError(f"{name} deve conter apenas inteiros")
    if len(set(result)) != len(result):
        raise ValueError(f"{name} não pode conter duplicatas")
    if any(number < minimum or number > maximum for number in result):
        raise ValueError(f"{name} contém dezenas fora da faixa {minimum}..{maximum}")
    return tuple(sorted(result))
