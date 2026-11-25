"""Serviços de negócio da Lotomaster: histórico oficial, geração e conferência de jogos."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
from math import comb, isfinite, prod
from datetime import datetime, timezone
import random
from itertools import combinations, product
import threading
import time

from .analytics import pareto_filter_data
from .catalog import get_spec
from .caixa import fetch_draw
from .client_draws import validate_client_draws
from . import storage

_LATEST_TTL_SECONDS = 90
logger = logging.getLogger(__name__)
_latest_cache: dict[str, tuple[float, dict]] = {}
_latest_lock = threading.Lock()


def latest_result(game: str, refresh: bool = True) -> dict:
    spec = get_spec(game)
    key = spec["key"]
    now = time.monotonic()
    with _latest_lock:
        cached_mem = _latest_cache.get(key)
    if not refresh and cached_mem and 0 <= now - cached_mem[0] < _LATEST_TTL_SECONDS:
        return {**cached_mem[1], "source": "cache"}
    try:
        draw = fetch_draw(key)
        try:
            storage.save_draw(draw)
        except Exception:
            logger.error("Não foi possível persistir o resultado consultado para %s", key)
        checked_at = datetime.now(timezone.utc).isoformat()
        draw = {**draw, "_latest_checked_at": checked_at}
        with _latest_lock:
            concurrent_mem = _latest_cache.get(key)
            if (
                concurrent_mem is not None
                and concurrent_mem[1].get("_latest_checked_at")
                and int(concurrent_mem[1]["contest"]) > int(draw["contest"])
            ):
                return {**concurrent_mem[1], "source": "CAIXA via Cloudflare Worker"}
            _latest_cache[key] = (now, draw)
        return {**draw, "source": "CAIXA via Cloudflare Worker"}
    except Exception:
        cached_db = storage.latest_draw(key)
        fallback_warning = (
            "A CAIXA está temporariamente indisponível; "
            "o resultado em cache pode estar desatualizado."
        )
        stale = None
        if cached_db:
            cached_db = {k: v for k, v in cached_db.items() if k not in {"_latest_checked_at", "_known_latest_contest"}}
            stale = {
                **cached_db,
                "source": "cache",
                "warning": fallback_warning,
            }
        with _latest_lock:
            concurrent_mem = _latest_cache.get(key)
            if concurrent_mem is not None and concurrent_mem is not cached_mem:
                current_draw = concurrent_mem[1]
                if current_draw.get("_latest_checked_at"):
                    return {**current_draw, "source": "CAIXA via Cloudflare Worker"}
                return {**current_draw, "source": "cache"}
            if (
                concurrent_mem is not None
                and concurrent_mem[1].get("_latest_checked_at")
                and (stale is None or int(concurrent_mem[1]["contest"]) > int(stale["contest"]))
            ):
                return {
                    **concurrent_mem[1],
                    "source": "cache",
                    "warning": fallback_warning,
                }
            if stale is not None:
                _latest_cache[key] = (now, stale)
                return stale
        raise RuntimeError("Não foi possível consultar a CAIXA.") from None


def list_results(game: str, limit: int = 20, refresh_latest: bool = True) -> list[dict]:
    spec = get_spec(game)
    key = spec["key"]
    limit = max(1, min(int(limit), 300))
    latest = None
    try:
        latest = latest_result(key, refresh=refresh_latest)
    except Exception:
        latest = storage.latest_draw(key)
        if not latest:
            raise
    current_contest = int(latest["contest"])
    lower = max(1, current_contest - limit + 1)
    cached = storage.list_draws_range(key, lower, current_contest)
    if latest:
        current_contest = int(latest["contest"])
        have = {int(draw["contest"]) for draw in cached}
        # Retry only gaps inside the known, bounded recent contest window.
        target_contests = [n for n in range(current_contest, max(0, current_contest - limit), -1) if n not in have]
        if target_contests:
            with ThreadPoolExecutor(max_workers=5) as pool:
                futures = {pool.submit(fetch_draw, key, contest): contest for contest in target_contests}
                for future in as_completed(futures):
                    try:
                        storage.save_draw(future.result())
                    except Exception:
                        continue
    results = storage.list_draws_range(key, lower, current_contest)
    # Do not fill gaps in the requested recent window with older cached rows.
    if latest:
        newest = int(latest.get("_known_latest_contest", latest["contest"]))
        results = [row for row in results if newest - limit < int(row["contest"]) <= newest]
        # Keep a validated latest draw visible even if SQLite could not save it.
        # Preserve transient provenance by preferring this object on duplicates.
        latest_contest = int(latest["contest"])
        if newest - limit < latest_contest <= newest:
            results_by_contest = {int(row["contest"]): row for row in results}
            results_by_contest[latest_contest] = latest
            results = sorted(
                results_by_contest.values(),
                key=lambda row: int(row["contest"]),
                reverse=True,
            )[:limit]
    if latest and not results:
        raise RuntimeError("Nenhum concurso válido disponível no recorte solicitado; há lacunas no cache.")
    return results


def list_history_page(game: str, limit: int = 100, before: int | None = None) -> dict:
    """Load one bounded CAIXA history page; ``before`` is an exclusive cursor."""
    spec = get_spec(game)
    key = spec["key"]
    limit = max(1, min(int(limit), 100))
    if before is not None and int(before) <= 1:
        return {"items": [], "expected_count": 0, "missing_contests": [], "next_before": None, "provenance": {"latest_lookup": "unknown", "recently_checked": False, "verified": False}, "warning": "Último concurso não consultado nesta página vazia; pode estar desatualizado."}

    # Pagination requests are frequent; reuse a still-fresh latest lookup while
    # retaining an explicit cache-bypass path for callers that need refresh=True.
    latest = latest_result(key, refresh=False)
    latest_contest = int(latest.get("_known_latest_contest", latest["contest"]))
    source = latest.get("source")
    checked_at = latest.get("_latest_checked_at") if not latest.get("warning") else None
    fresh = source == "CAIXA via Cloudflare Worker" or (source == "cache" and bool(checked_at))
    freshness_warning = latest.get("warning") or ("Último concurso obtido do cache do servidor ou de origem não informada; pode estar desatualizado." if not fresh else None)
    provenance = {"latest_lookup": "server_fetch" if source == "CAIXA via Cloudflare Worker" else "server_cache" if source == "cache" else "unknown", "recently_checked": fresh, "verified": False, **({"last_successful_lookup_at": checked_at} if checked_at else {})}
    upper = min(latest_contest, int(before) - 1) if before is not None else latest_contest
    lower = max(1, upper - limit + 1)
    if upper < lower:
        return {"items": [], "expected_count": 0, "missing_contests": [], "next_before": None, "provenance": provenance, **({"warning": freshness_warning} if freshness_warning else {})}

    cached = storage.list_draws_range(key, lower, upper)
    have = {int(draw["contest"]) for draw in cached}
    missing = [contest for contest in range(upper, lower - 1, -1) if contest not in have]
    if missing:
        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = {pool.submit(fetch_draw, key, contest): contest for contest in missing}
            for future in as_completed(futures):
                try:
                    storage.save_draw(future.result())
                except Exception:
                    continue

    items = storage.list_draws_range(key, lower, upper)
    returned = {int(draw["contest"]) for draw in items}
    missing_after_fetch = [contest for contest in range(upper, lower - 1, -1) if contest not in returned]
    return {
        "items": items,
        "from_contest": lower,
        "to_contest": upper,
        "expected_count": upper - lower + 1,
        "missing_contests": missing_after_fetch,
        "next_before": lower if lower > 1 else None,
        "provenance": provenance,
        **({"warning": freshness_warning} if freshness_warning else {}),
    }


def generate_tickets(game: str, options: dict | None = None) -> list[dict]:
    spec = get_spec(game)
    options = options or {}
    count = int(options.get("count", 1))
    if count < 1 or count > 100:
        raise ValueError("A quantidade de jogos deve ficar entre 1 e 100.")
    seed = options.get("seed")
    rng = random.Random(seed) if seed is not None else random.SystemRandom()
    filters = options.get("filters", {})
    if "weights" in options and spec["key"] == "supersete":
        raise ValueError("A ponderação por dezena não é suportada no Super Sete.")
    weights = _validate_number_weights(options.get("weights"), spec) if "weights" in options else None
    pareto_details = options.get("_pareto_details")
    if options.get("pareto") and pareto_details is None:
        pareto_details = pareto_filter_data(spec["key"], storage.list_draws(spec["key"], 1000))
    pareto_numbers = _validated_pareto_numbers(pareto_details, spec) if options.get("pareto") else None
    latest = storage.latest_draw(spec["key"])
    previous = set(latest.get("numbers", [])) if latest else set()
    generated = []

    if spec["key"] == "supersete":
        _validate_generator_filters(spec, filters, spec["pick_size"])
        columns_cfg = options.get("columns") or {}
        for ticket_index in range(count):
            columns = []
            for column in range(1, 8):
                raw = columns_cfg.get(str(column), columns_cfg.get(column, {})) or {}
                fixed = sorted(set(_int_list(raw.get("fixed", []))))
                excluded = set(_int_list(raw.get("excluded", [])))
                pick_count = int(raw.get("pick_count", 1))
                if pick_count < 1 or pick_count > 10:
                    raise ValueError("Cada coluna do Super Sete deve conter de 1 a 10 opções.")
                if any(n < 0 or n > 9 for n in fixed + list(excluded)) or set(fixed) & excluded or len(fixed) > pick_count:
                    raise ValueError(f"Fixos/removidos inválidos na coluna {column}.")
                available = [n for n in range(10) if n not in excluded and n not in fixed]
                if len(fixed) + len(available) < pick_count:
                    raise ValueError(f"Não há dígitos suficientes na coluna {column}.")
                if pareto_numbers is not None:
                    if not set(fixed).issubset(pareto_numbers):
                        raise ValueError("As dezenas fixas precisam pertencer ao conjunto do filtro Pareto histórico.")
                    available = [n for n in available if n in pareto_numbers]
                    if len(fixed) + len(available) < pick_count:
                        raise ValueError(f"O filtro Pareto histórico não deixa dígitos suficientes na coluna {column}.")
                chosen = fixed + rng.sample(available, pick_count - len(fixed))
                columns.append(sorted(chosen))
            generated.append(_ticket_summary(spec, {"columns": columns, "numbers": [c[0] for c in columns]}, ticket_index + 1, previous))
        return generated

    pick_count = int(options.get("pick_count", spec["pick_size"]))
    if pick_count < spec["min_pick"] or pick_count > spec["max_pick"]:
        raise ValueError(f"{spec['name']} aceita jogos de {spec['min_pick']} a {spec['max_pick']} dezenas nesta ferramenta.")
    _validate_generator_filters(spec, filters, pick_count)
    fixed = sorted(set(_int_list(options.get("fixed", []))))
    excluded = sorted(set(_int_list(options.get("excluded", []))))
    if set(fixed) & set(excluded):
        raise ValueError("Uma dezena não pode estar fixa e removida ao mesmo tempo.")
    if any(n < spec["minimum"] or n > spec["maximum"] for n in fixed + excluded):
        raise ValueError(f"As dezenas precisam estar no intervalo {spec['minimum']}–{spec['maximum']}.")
    if len(fixed) > pick_count or len(set(range(spec["minimum"], spec["maximum"] + 1)) - set(excluded)) < pick_count:
        raise ValueError("Os fixos/removidos não deixam dezenas suficientes para montar o jogo.")

    bonus = spec.get("bonus") or {}
    bonus_options = options.get("bonus") or {}
    candidates = list(range(spec["minimum"], spec["maximum"] + 1))
    if pareto_numbers is not None:
        if not set(fixed).issubset(pareto_numbers):
            raise ValueError("As dezenas fixas precisam pertencer ao conjunto do filtro Pareto histórico.")
        candidates = [number for number in candidates if number in pareto_numbers]
    available = [n for n in candidates if n not in excluded and n not in fixed]
    if len(available) + len(fixed) < pick_count:
        raise ValueError("O filtro Pareto histórico, junto às dezenas removidas/fixas, não deixa dezenas suficientes para montar o jogo.")
    quadrant_limits = _quadrant_limits(spec, filters, pick_count)
    allocations = None
    if quadrant_limits is not None:
        sectors = _quadrants(candidates)
        fixed_q = [sum(n in fixed for n in sector) for sector in sectors]
        available_q = [[n for n in sector if n in available] for sector in sectors]
        ranges = []
        for i, nums in enumerate(available_q):
            lo = max(quadrant_limits[i][0], fixed_q[i])
            hi = min(quadrant_limits[i][1], fixed_q[i] + len(nums))
            if lo > hi:
                raise ValueError(f"Filtros quadrantes inviáveis no Q{i + 1} com fixos/removidos.")
            ranges.append(range(lo, hi + 1))
        allocations = [a for a in product(*ranges) if sum(a) == pick_count]
        if not allocations:
            raise ValueError("Não existe alocação que satisfaça os limites dos quadrantes, fixos/removidos e pick_count.")
    tries = max(300, count * 300)
    weighted = bool(weights)
    allocation_weights = (
        _quadrant_allocation_weights(available_q, allocations, fixed_q)
        if allocations is not None else None
    )
    for ticket_index in range(count):
        chosen = None
        for _ in range(tries):
            if allocations is not None:
                allocation = rng.choices(allocations, weights=allocation_weights, k=1)[0]
                numbers = []
                for sector, pool, total in zip(sectors, available_q, allocation):
                    fixed_sector = [n for n in fixed if n in sector]
                    k = total - len(fixed_sector)
                    local_weights = {n: weights[n] for n in pool if weights and n in weights}
                    drawn = _weighted_sample(rng, pool, k, local_weights) if local_weights else rng.sample(pool, k)
                    numbers.extend(fixed_sector + drawn)
                numbers.sort()
            elif weighted:
                drawn = _weighted_sample(rng, available, pick_count - len(fixed), weights)
                numbers = sorted(fixed + drawn)
            else:
                drawn = rng.sample(available, pick_count - len(fixed))
                numbers = sorted(fixed + drawn)
            if _passes_filters(numbers, filters, previous):
                chosen = numbers
                break
        if chosen is None:
            raise ValueError("Nenhum jogo atendeu aos filtros. Ajuste soma, paridade ou dezenas fixas/removidas.")
        extra = {}
        bonus_type = bonus.get("type")
        if bonus_type == "month":
            month = bonus_options.get("month")
            if month in (None, ""):
                month = rng.randint(bonus["minimum"], bonus["maximum"])
            else:
                try:
                    if isinstance(month, bool) or not (
                        isinstance(month, int)
                        or isinstance(month, str) and month.strip().isascii() and month.strip().isdigit()
                    ):
                        raise ValueError
                    month = int(month)
                except (TypeError, ValueError):
                    raise ValueError(f"O Mês da Sorte deve estar entre {bonus['minimum']} e {bonus['maximum']}.") from None
                if not bonus["minimum"] <= month <= bonus["maximum"]:
                    raise ValueError(f"O Mês da Sorte deve estar entre {bonus['minimum']} e {bonus['maximum']}.")
            extra["month"] = month
        elif bonus_type == "team":
            team = bonus_options.get("team")
            if not isinstance(team, str) or not team.strip() or len(team) > 100:
                raise ValueError("Informe o Time do Coração para gerar um jogo completo.")
            extra["team"] = team.strip()
        elif bonus_type == "trevos":
            trevo_count = bonus_options.get("trevo_count", 2)
            if type(trevo_count) is not int or not bonus["minimum"] <= trevo_count <= bonus["maximum"]:
                raise ValueError(f"O gerador de +Milionária aceita de {bonus['minimum']} a {bonus['maximum']} trevos.")
            extra["trevos"] = sorted(rng.sample(range(1, 7), trevo_count))
        generated.append(_ticket_summary(spec, {"numbers": chosen, **extra}, ticket_index + 1, previous))
    return generated


def _validate_number_weights(raw, spec: dict) -> dict[int, float]:
    """Validate per-number selection preferences. Unspecified numbers default to 1."""
    if not isinstance(raw, dict):
        raise ValueError("weights deve ser um objeto de dezenas para pesos.")
    if len(raw) > spec["maximum"] - spec["minimum"] + 1:
        raise ValueError("weights contém mais chaves do que dezenas disponíveis.")
    result = {}
    for key, value in raw.items():
        if isinstance(key, bool) or not isinstance(key, (int, str)):
            raise ValueError("Cada chave de weights deve ser uma dezena inteira ou string numérica canônica.")
        if isinstance(key, str) and (not key.isascii() or not key.isdigit() or str(int(key)) != key):
            raise ValueError("Cada chave de weights deve ser uma dezena inteira ou string numérica canônica.")
        number = key if isinstance(key, int) else int(key)
        if number < spec["minimum"] or number > spec["maximum"]:
            raise ValueError(f"A dezena {number} em weights está fora do intervalo {spec['minimum']}–{spec['maximum']}.")
        if number in result:
            raise ValueError(f"Chaves de weights conflitantes para a dezena {number}.")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("Cada peso deve ser finito, maior que zero e no máximo 1.000.000.")
        try:
            numeric_weight = float(value)
        except (OverflowError, ValueError):
            raise ValueError("Cada peso deve ser finito, maior que zero e no máximo 1.000.000.") from None
        if not isfinite(numeric_weight) or numeric_weight <= 0 or numeric_weight > 1_000_000:
            raise ValueError("Cada peso deve ser finito, maior que zero e no máximo 1.000.000.")
        result[number] = numeric_weight
    return result


def _validated_pareto_numbers(details, spec: dict) -> set[int]:
    if not isinstance(details, dict) or not details.get("draws_analyzed"):
        raise ValueError("O filtro Pareto precisa de concursos históricos no cache local.")
    numbers = details.get("numbers")
    if not isinstance(numbers, list) or not numbers or any(type(number) is not int for number in numbers):
        raise ValueError("O conjunto Pareto histórico está vazio ou inválido.")
    if any(number < spec["minimum"] or number > spec["maximum"] for number in numbers):
        raise ValueError("O conjunto Pareto histórico contém dezenas fora da modalidade.")
    return set(numbers)


def _weighted_sample(rng, population: list[int], k: int, weights: dict[int, float]) -> list[int]:
    """Selection preference only; no MazuSoft equivalence or prize-probability claim."""
    remaining = list(population)
    selected = []
    for _ in range(k):
        total = sum(weights.get(number, 1.0) for number in remaining)
        point = rng.random() * total
        for index, number in enumerate(remaining):
            point -= weights.get(number, 1.0)
            if point < 0:
                selected.append(number)
                del remaining[index]
                break
        else:
            # Rounding can place the point on the upper endpoint, especially
            # for subnormal floats; never return an incomplete ticket.
            selected.append(remaining.pop())
    return selected


def _ticket_summary(spec: dict, ticket: dict, ticket_number: int, previous: set[int]) -> dict:
    numbers = ticket.get("numbers", [])
    if spec["key"] == "supersete":
        column_picks = [len(column) for column in ticket.get("columns", [])]
        probability = ticket_probability("supersete", column_pick_counts=column_picks)
    else:
        probability = ticket_probability(spec["key"], len(numbers), len(ticket.get("trevos", [])) or 2)
    summary = {
        "ticket_number": ticket_number,
        "numbers": numbers,
        "columns": ticket.get("columns"),
        "bonus": {k: v for k, v in ticket.items() if k not in {"numbers", "columns"}},
        "sum": sum(numbers) if spec["key"] != "supersete" else None,
        "even_count": sum(n % 2 == 0 for n in numbers),
        "odd_count": sum(n % 2 != 0 for n in numbers),
        "repeated_from_latest": len(set(numbers) & previous),
        "probability": probability,
    }
    if spec["key"] == "lotomania":
        summary["quadrant_counts"] = _quadrant_counts(numbers)
    return summary


def _quadrants(numbers):
    sectors = [[], [], [], []]
    for number in numbers:
        row, column = divmod(number, 10)
        sectors[(0 if row < 5 else 2) + (0 if column < 5 else 1)].append(number)
    return sectors


def _quadrant_counts(numbers):
    return {f"q{i + 1}": len(sector) for i, sector in enumerate(_quadrants(numbers))}


def _quadrant_allocation_weights(available_q, allocations, fixed_q):
    """Count concrete number-sets represented by each feasible quadrant allocation."""
    return [
        prod(comb(len(pool), total - fixed) for pool, total, fixed in zip(available_q, allocation, fixed_q))
        for allocation in allocations
    ]


def _quadrant_limits(spec, filters, pick_count):
    names = [f"{bound}_q{i}" for i in range(1, 5) for bound in ("min", "max")]
    if not any(filters.get(name) not in (None, "") for name in names):
        return None
    if spec["key"] != "lotomania":
        raise ValueError("Filtros quadrantes estão disponíveis somente na Lotomania.")
    result = []
    for i in range(1, 5):
        lo_key, hi_key = f"min_q{i}", f"max_q{i}"
        lo = _filter_integer(filters[lo_key], lo_key, 0, 25) if filters.get(lo_key) not in (None, "") else 0
        hi = _filter_integer(filters[hi_key], hi_key, 0, 25) if filters.get(hi_key) not in (None, "") else 25
        if lo > hi:
            raise ValueError(f"{lo_key} não pode ser maior que {hi_key}.")
        result.append((lo, hi))
    if sum(x[0] for x in result) > pick_count or sum(x[1] for x in result) < pick_count:
        raise ValueError("Limites dos quadrantes não podem somar o pick_count solicitado.")
    return result


def _passes_filters(numbers: list[int], filters: dict, previous: set[int]) -> bool:
    return not _filter_failures(numbers, filters, previous)


def diagnose_ticket_filters(game: str, numbers: list[int], filters: dict, reference_draw=None) -> list[str]:
    """Validate a ticket's filter contract and return every local failure reason."""
    spec = get_spec(game)
    _validate_generator_filters(spec, filters, len(numbers))
    repeat_filter = any(filters.get(key) not in (None, "") for key in ("min_repeated", "max_repeated"))
    if repeat_filter and reference_draw is None:
        raise ValueError("Filtros de repetidas exigem um concurso de referência explícito.")
    previous = set(reference_draw or [])
    return _filter_failures(numbers, filters, previous)


def _filter_failures(numbers: list[int], filters: dict, previous: set[int]) -> list[str]:
    if not isinstance(filters, dict):
        raise ValueError("Os filtros devem ser informados como objeto.")
    failures = []

    def check(key: str, actual: int, minimum: int, maximum: int, label: str):
        for bound, compare, wording in (("min", lambda a, b: a >= b, "abaixo do mínimo"), ("max", lambda a, b: a <= b, "acima do máximo")):
            name = f"{bound}_{key}"
            if filters.get(name) not in (None, ""):
                threshold = _filter_integer(filters[name], name, minimum, maximum)
                if not compare(actual, threshold):
                    failures.append(f"{label} {actual} {wording} {threshold}")

    if any(filters.get(f"{bound}_q{i}") not in (None, "") for i in range(1, 5) for bound in ("min", "max")):
        counts = _quadrant_counts(numbers)
        for i in range(1, 5):
            check(f"q{i}", counts[f"q{i}"], 0, 25, f"Q{i}")
    total = sum(numbers)
    evens = sum(n % 2 == 0 for n in numbers)
    repeats = len(set(numbers) & previous)
    check("sum", total, 0, 10000, "Soma")
    check("even", evens, 0, len(numbers), "Pares")
    check("repeated", repeats, 0, len(numbers), "Repetidas do concurso de referência")
    # Todas as modalidades usam dezenas até 99. Zero não conta como Fibonacci
    # por convenção desta ferramenta; não representa uma regra da MazuSoft.
    primes = {2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71, 73, 79, 83, 89, 97}
    fibonacci = {1, 2, 3, 5, 8, 13, 21, 34, 55, 89}
    prime_count = sum(n in primes for n in numbers)
    fibonacci_count = sum(n in fibonacci for n in numbers)
    longest_run = current = 0
    previous_n = None
    # Convenção própria: salto é cada par adjacente de dezenas ordenadas
    # cuja distância excede 1; não equivale a qualquer implementação MazuSoft.
    jumps = 0
    for n in sorted(numbers):
        if previous_n is not None and n - previous_n > 1:
            jumps += 1
        current = current + 1 if previous_n is not None and n == previous_n + 1 else 1
        longest_run, previous_n = max(longest_run, current), n
    check("jumps", jumps, 0, max(0, len(numbers) - 1), "Saltos")
    check("prime", prime_count, 0, len(numbers), "Primos")
    check("fibonacci", fibonacci_count, 0, len(numbers), "Fibonacci")
    check("sequence", longest_run, 1, len(numbers), "Maior sequência consecutiva")
    if any(filters.get(k) not in (None, "") for k in ("min_line", "max_line", "min_column", "max_column")):
        rows = [sum((n - 1) // 5 == i for n in numbers) for i in range(5)]
        columns = [sum((n - 1) % 5 == i for n in numbers) for i in range(5)]
        for key, counts, label in (("line", rows, "Linha"), ("column", columns, "Coluna")):
            for suffix, compare, wording in (("min", lambda a, b: a >= b, "abaixo do mínimo"), ("max", lambda a, b: a <= b, "acima do máximo")):
                name = f"{suffix}_{key}"
                if filters.get(name) not in (None, ""):
                    threshold = _filter_integer(filters[name], name, 0, 5)
                    failures.extend(f"{label} {index + 1} com {count} {wording} {threshold}" for index, count in enumerate(counts) if not compare(count, threshold))
    return failures


def _filter_integer(value, key: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        raise ValueError(f"O filtro {key} deve ser um inteiro entre {minimum} e {maximum}.")
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"O filtro {key} deve ser um inteiro entre {minimum} e {maximum}.") from None
    if str(value).strip() != str(parsed) or not minimum <= parsed <= maximum:
        raise ValueError(f"O filtro {key} deve ser um inteiro entre {minimum} e {maximum}.")
    return parsed


def _validate_generator_filters(spec: dict, filters: dict, pick_count: int) -> None:
    if not isinstance(filters, dict):
        raise ValueError("Os filtros devem ser informados como objeto.")
    if spec["key"] == "supersete":
        if filters:
            raise ValueError("Filtros numéricos não são compatíveis com o Super Sete.")
        return
    bounds = {key: (0, pick_count) for key in ("min_even", "max_even", "min_repeated", "max_repeated", "min_prime", "max_prime", "min_fibonacci", "max_fibonacci")}
    bounds.update({"min_jumps": (0, pick_count - 1), "max_jumps": (0, pick_count - 1)})
    bounds.update({"min_sum": (0, spec["maximum"] * pick_count), "max_sum": (0, spec["maximum"] * pick_count), "min_sequence": (1, pick_count), "max_sequence": (1, pick_count)})
    if spec["key"] == "lotofacil":
        bounds.update({key: (0, 5) for key in ("min_line", "max_line", "min_column", "max_column")})
    if spec["key"] == "lotomania":
        bounds.update({f"{bound}_q{i}": (0, 25) for i in range(1, 5) for bound in ("min", "max")})
        _quadrant_limits(spec, filters, pick_count)
    if spec["key"] != "lotofacil" and any(k in filters and filters[k] not in (None, "") for k in ("min_line", "max_line", "min_column", "max_column")):
        raise ValueError("Contagens por linha/coluna estão disponíveis somente na Lotofácil.")
    for key, value in filters.items():
        if value in (None, ""):
            continue
        if key not in bounds:
            raise ValueError(f"Filtro desconhecido: {key}.")
        _filter_integer(value, key, *bounds[key])
    for low, high in (("min_sum", "max_sum"), ("min_even", "max_even"), ("min_repeated", "max_repeated"), ("min_prime", "max_prime"), ("min_fibonacci", "max_fibonacci"), ("min_sequence", "max_sequence"), ("min_jumps", "max_jumps"), ("min_line", "max_line"), ("min_column", "max_column")):
        if filters.get(low) not in (None, "") and filters.get(high) not in (None, "") and int(filters[low]) > int(filters[high]):
            raise ValueError(f"{low} não pode ser maior que {high}.")


def simulate_tickets(game: str, tickets: list[dict], draw: dict) -> list[dict]:
    spec = get_spec(game)
    results = []
    for idx, ticket in enumerate(tickets, 1):
        _validate_ticket(spec, ticket)
        numbers = _int_list(ticket.get("numbers", []))
        if spec["key"] == "supersete":
            columns = ticket.get("columns") or [[n] for n in numbers]
            winning = draw.get("numbers", [])
            per_column = [bool(set(_int_list(choice)) & {winning[i]}) for i, choice in enumerate(columns[:7]) if i < len(winning)]
            hits = sum(per_column)
            results.append({"ticket_number": ticket.get("ticket_number", idx), "hits": hits, "main_hits": hits, "column_hits": per_column, "award": f"{hits} acertos" if hits >= 3 else None, "draw_contest": draw.get("contest")})
            continue
        chosen = set(numbers)
        main_hits = len(chosen & set(draw.get("numbers", [])))
        if spec["key"] == "duplasena":
            second_hits = len(chosen & set(draw.get("second_numbers", [])))
            results.append({"ticket_number": ticket.get("ticket_number", idx), "main_hits": main_hits, "second_hits": second_hits, "award": {"first": _award(spec, main_hits), "second": _award(spec, second_hits)}, "draw_contest": draw.get("contest")})
            continue
        bonus = ticket.get("bonus", {}) or {}
        extra = {}
        award = _award(spec, main_hits)
        if spec["key"] == "diadesorte":
            month_drawn = (draw.get("month") or {}).get("number")
            month_hit = bool(bonus.get("month") and month_drawn and int(bonus["month"]) == int(month_drawn))
            extra["month_hit"] = month_hit
            extra["drawn_month"] = draw.get("month")
            if month_hit:
                award = award or "Mês da Sorte"
        elif spec["key"] == "timemania":
            drawn_team = " ".join((draw.get("team") or "").split()).casefold()
            team_hit = bool(bonus.get("team") and drawn_team and " ".join(str(bonus["team"]).split()).casefold() == drawn_team)
            extra["team_hit"] = team_hit
            extra["drawn_team"] = draw.get("team")
            if team_hit:
                award = award or "Time do Coração"
        elif spec["key"] == "maismilionaria":
            picked_trevos = sorted(set(_int_list(bonus.get("trevos", []))))
            drawn_trevos = sorted(set(_int_list(draw.get("trevos", []))))
            trevo_hits = len(set(picked_trevos) & set(drawn_trevos))
            extra["trevo_hits"] = trevo_hits
            extra["drawn_trevos"] = draw.get("trevos", [])
            award_counts = _million_subbet_award_counts(main_hits, len(numbers), trevo_hits, len(picked_trevos))
            extra["subbets_total"] = comb(len(numbers), 6) * comb(len(picked_trevos), 2)
            extra["award_counts"] = award_counts
            extra["winning_subbets"] = sum(award_counts.values())
            extra["award_tiers_overlap"] = len(award_counts) > 1
            if len(numbers) == 6:
                extra["subbet_awards"] = [
                    {"trevos": list(pair), "trevo_hits": len(set(pair) & set(drawn_trevos)),
                     "award": _million_award(main_hits, len(set(pair) & set(drawn_trevos)))}
                    for pair in combinations(picked_trevos, 2)
                ]
            award = min(award_counts, key=lambda label: int(label.split("·", 1)[0].split()[-1])) if award_counts else None
        results.append({"ticket_number": ticket.get("ticket_number", idx), "main_hits": main_hits, "hits": main_hits, "award": award, "draw_contest": draw.get("contest"), **extra})
    return results


def simulate_ticket_history(game: str, tickets: list[dict], draws: list[dict]) -> dict:
    """Conferência própria contra histórico normalizado entregue pelo cliente, sem I/O."""
    spec = get_spec(game)
    if not isinstance(tickets, list) or not 1 <= len(tickets) <= 500:
        raise ValueError("Informe de 1 a 500 jogos.")
    if not isinstance(draws, list) or not 1 <= len(draws) <= 5000:
        raise ValueError("Informe de 1 a 5.000 concursos.")
    if len(tickets) * len(draws) > 100_000:
        raise ValueError("A combinação não pode exceder 100.000 conferências (jogos × concursos).")
    # Direct callers need the same completeness guarantees as the API path;
    # otherwise absent special results silently suppress prize categories.
    validate_client_draws(spec["key"], draws, require_game=False, require_special=True, limit=5000)
    contest_ids = set()
    normalized_draws = []
    for draw in draws:
        if not isinstance(draw, dict):
            raise ValueError("Cada concurso deve ser um objeto normalizado.")
        contest = draw.get("contest")
        if isinstance(contest, bool) or not isinstance(contest, int) or contest < 1:
            raise ValueError("Cada concurso precisa de número inteiro positivo em 'contest'.")
        if contest in contest_ids:
            raise ValueError(f"Concurso duplicado no histórico: {contest}.")
        contest_ids.add(contest)
        if draw.get("game") not in (None, spec["key"]):
            raise ValueError("Todos os concursos precisam pertencer à modalidade solicitada.")
        numbers = draw.get("numbers")
        if not isinstance(numbers, list) or len(numbers) != spec["draw_size"]:
            raise ValueError(f"O concurso {contest} precisa conter {spec['draw_size']} dezenas principais.")
        if any(type(value) is not int for value in numbers):
            raise ValueError(f"Dezenas inválidas no concurso {contest}.")
        parsed = list(numbers)
        if any(n < spec["minimum"] or n > spec["maximum"] for n in parsed):
            raise ValueError(f"Dezenas inválidas no concurso {contest}.")
        if spec["key"] != "supersete" and len(set(parsed)) != len(parsed):
            raise ValueError(f"Dezenas inválidas ou repetidas no concurso {contest}.")
        normalized_draw = dict(draw, numbers=parsed)
        if spec["key"] == "duplasena":
            second = draw.get("second_numbers")
            if not isinstance(second, list) or len(second) != 6:
                raise ValueError(f"O concurso {contest} da Dupla Sena precisa conter 'second_numbers' com seis dezenas.")
            if any(type(value) is not int for value in second):
                raise ValueError(f"Segundo sorteio inválido no concurso {contest}.")
            parsed_second = list(second)
            if len(set(parsed_second)) != 6 or any(n < spec["minimum"] or n > spec["maximum"] for n in parsed_second):
                raise ValueError(f"Segundo sorteio inválido no concurso {contest}.")
            normalized_draw["second_numbers"] = parsed_second
        if spec["key"] == "maismilionaria":
            trevos = draw.get("trevos")
            if not isinstance(trevos, list) or any(type(value) is not int for value in trevos):
                raise ValueError(f"O concurso {contest} da +Milionária precisa conter dois trevos distintos entre 1 e 6.")
            trevos = list(trevos)
            if len(trevos) != 2 or len(set(trevos)) != 2 or any(n < 1 or n > 6 for n in trevos):
                raise ValueError(f"O concurso {contest} da +Milionária precisa conter dois trevos distintos entre 1 e 6.")
            normalized_draw["trevos"] = trevos
        normalized_draws.append(normalized_draw)

    for ticket in tickets:
        _validate_ticket(spec, ticket)
    by_draw, summary = [], {}
    for draw in normalized_draws:
        results = simulate_tickets(spec["key"], tickets, draw)
        for result in results:
            award = result.get("award")
            if spec["key"] == "duplasena":
                for round_name, title in (("first", "1º sorteio"), ("second", "2º sorteio")):
                    tier = award.get(round_name)
                    if tier:
                        label = f"{title}: {tier}"
                        summary[label] = summary.get(label, 0) + 1
            elif spec["key"] == "maismilionaria":
                counts = result.get("award_counts")
                if counts is not None:
                    for tier, count in counts.items():
                        summary[tier] = summary.get(tier, 0) + count
                elif isinstance(award, str) and award:
                    summary[award] = summary.get(award, 0) + 1
            elif isinstance(award, str) and award and award not in {"Mês da Sorte", "Time do Coração"}:
                summary[award] = summary.get(award, 0) + 1
            if spec["key"] == "diadesorte" and result.get("month_hit"):
                summary["Mês da Sorte"] = summary.get("Mês da Sorte", 0) + 1
            elif spec["key"] == "timemania" and result.get("team_hit"):
                summary["Time do Coração"] = summary.get("Time do Coração", 0) + 1
        by_draw.append({"contest": draw["contest"], "draw_date": draw.get("draw_date"), "results": results})
    return {"draws": by_draw, "summary": summary, "evaluated_contests": len(draws), "evaluated_tickets": len(tickets)}


def _validate_ticket(spec: dict, ticket: dict) -> None:
    key = spec["key"]
    bonus = ticket.get("bonus", {}) or {}
    if key == "supersete":
        if bonus:
            raise ValueError("Campo especial incompatível com a modalidade.")
        columns = ticket.get("columns") or [[n] for n in _int_list(ticket.get("numbers", []))]
        if len(columns) != 7:
            raise ValueError("O Super Sete precisa de sete colunas, na ordem do volante.")
        for index, values in enumerate(columns, 1):
            digits = _int_list(values)
            if not digits or len(digits) > 10 or len(set(digits)) != len(digits) or any(n < 0 or n > 9 for n in digits):
                raise ValueError(f"A coluna {index} precisa ter de 1 a 10 dígitos distintos entre 0 e 9.")
        return
    numbers = _int_list(ticket.get("numbers", []))
    if len(set(numbers)) != len(numbers):
        raise ValueError("Um jogo não pode repetir dezenas.")
    valid_lotofacil_simulation = key == "lotofacil" and 15 <= len(numbers) <= 23
    if not spec["min_pick"] <= len(numbers) <= spec["max_pick"] and not valid_lotofacil_simulation:
        raise ValueError(f"{spec['name']} aceita jogos de {spec['min_pick']} a {spec['max_pick']} dezenas nesta ferramenta.")
    if any(n < spec["minimum"] or n > spec["maximum"] for n in numbers):
        raise ValueError(f"As dezenas de {spec['name']} precisam estar no intervalo {spec['minimum']}–{spec['maximum']}.")
    allowed = {"diadesorte": {"month"}, "timemania": {"team"}, "maismilionaria": {"trevos"}}.get(key, set())
    if set(bonus) - allowed:
        raise ValueError("Campo especial incompatível com a modalidade.")
    if key == "diadesorte":
        month = bonus.get("month")
        if type(month) is not int or not 1 <= month <= 12:
            raise ValueError("Informe o Mês da Sorte como inteiro entre 1 e 12.")
    if key == "timemania":
        team = bonus.get("team")
        if not isinstance(team, str) or not team.strip() or len(team) > 100:
            raise ValueError("Informe o Time do Coração.")
    if key == "maismilionaria":
        trevos = bonus.get("trevos")
        if not isinstance(trevos, list) or any(type(n) is not int for n in trevos):
            raise ValueError("Informe os trevos como números inteiros.")
        bonus_spec = spec.get("bonus") or {}
        minimum = bonus_spec.get("minimum", 2)
        maximum = bonus_spec.get("maximum", 6)
        if not minimum <= len(trevos) <= maximum or len(set(trevos)) != len(trevos) or any(n < 1 or n > 6 for n in trevos):
            raise ValueError(f"Escolha de {minimum} a {maximum} trevos distintos entre 1 e 6.")


def _award(spec: dict, hits: int) -> str | None:
    key = spec["key"]
    if key == "lotomania" and hits == 0:
        return "0 acertos"
    if hits in spec["prize_hits"]:
        return f"{hits} acertos"
    return None


def _million_award(main_hits: int, trevo_hits: int) -> str | None:
    tiers = {
        (6, 2): "Faixa 1 · 6 acertos + 2 trevos",
        (6, 1): "Faixa 2 · 6 acertos + 1 ou nenhum trevo",
        (6, 0): "Faixa 2 · 6 acertos + 1 ou nenhum trevo",
        (5, 2): "Faixa 3 · 5 acertos + 2 trevos",
        (5, 1): "Faixa 4 · 5 acertos + 1 ou nenhum trevo",
        (5, 0): "Faixa 4 · 5 acertos + 1 ou nenhum trevo",
        (4, 2): "Faixa 5 · 4 acertos + 2 trevos",
        (4, 1): "Faixa 6 · 4 acertos + 1 ou nenhum trevo",
        (4, 0): "Faixa 6 · 4 acertos + 1 ou nenhum trevo",
        (3, 2): "Faixa 7 · 3 acertos + 2 trevos",
        (3, 1): "Faixa 8 · 3 acertos + 1 trevo",
        (2, 2): "Faixa 9 · 2 acertos + 2 trevos",
        (2, 1): "Faixa 10 · 2 acertos + 1 trevo",
    }
    return tiers.get((main_hits, trevo_hits))


def _choose_count(n: int, k: int) -> int:
    return comb(n, k) if n >= 0 and k >= 0 and k <= n else 0


def _million_subbet_award_counts(main_hits: int, pick_count: int, trevo_hits: int, trevo_count: int) -> dict[str, int]:
    """Count every six-number/two-trevo subbet by official tier for one draw."""
    award_counts = {}
    for subbet_main_hits in range(7):
        main_subbets = _choose_count(main_hits, subbet_main_hits) * _choose_count(pick_count - main_hits, 6 - subbet_main_hits)
        if not main_subbets:
            continue
        for subbet_trevo_hits in range(3):
            trevo_subbets = _choose_count(trevo_hits, subbet_trevo_hits) * _choose_count(trevo_count - trevo_hits, 2 - subbet_trevo_hits)
            if not trevo_subbets:
                continue
            award = _million_award(subbet_main_hits, subbet_trevo_hits)
            if award:
                award_counts[award] = award_counts.get(award, 0) + main_subbets * trevo_subbets
    return award_counts


def _hypergeometric_counts(population: int, picks: int, draw_size: int) -> tuple[dict[int, int], int]:
    """Exact favorable-outcome counts for the number of ticket/draw intersections."""
    denominator = comb(population, draw_size)
    minimum = max(0, draw_size - (population - picks))
    maximum = min(picks, draw_size)
    outcomes = {
        hits: comb(picks, hits) * comb(population - picks, draw_size - hits)
        for hits in range(minimum, maximum + 1)
    }
    return outcomes, denominator


def _outcome_record(favorable: int, total: int, label: str | None = None, **metadata) -> dict:
    probability = favorable / total if favorable else 0.0
    row = {
        "probability": probability,
        "one_in": round(total / favorable) if favorable else None,
        "percent": probability * 100,
        "favorable_outcomes": str(favorable),
        "total_outcomes": str(total),
    }
    if label is not None:
        row["label"] = label
    row.update(metadata)
    return row


def _super_seven_counts(column_picks: list[int]) -> tuple[list[int], int]:
    """Exact counts across 10^7 seven-column outcomes for the supplied ticket."""
    counts = [1]
    for picks in column_picks:
        updated = [0] * (len(counts) + 1)
        for hits, outcomes in enumerate(counts):
            updated[hits] += outcomes * (10 - picks)
            updated[hits + 1] += outcomes * picks
        counts = updated
    return counts, 10 ** 7


def ticket_probability(
    game: str,
    pick_count: int | None = None,
    trevo_count: int = 2,
    column_pick_counts: list[int] | None = None,
) -> dict:
    spec = get_spec(game)
    key = spec["key"]
    if key == "supersete":
        column_picks = [1] * 7 if column_pick_counts is None else column_pick_counts
        if not isinstance(column_picks, list) or len(column_picks) != 7 or any(type(value) is not int or not 1 <= value <= 10 for value in column_picks):
            raise ValueError("Informe exatamente sete quantidades inteiras de 1 a 10 opções, uma por coluna do Super Sete.")
        outcomes, denominator = _super_seven_counts(column_picks)
        winning = outcomes[7]
        result = {
            "event": "7 acertos em 7 colunas",
            "one_in": round(denominator / winning) if winning else None,
            "percent": winning / denominator * 100,
            "favorable_outcomes": str(winning),
            "total_outcomes": str(denominator),
            "method": "Contagem exata das combinações de dígitos por coluna; cada coluna sorteia um dígito de 0 a 9.",
            "hit_distribution": [
                _outcome_record(count, denominator, hits=hits)
                for hits, count in enumerate(outcomes)
            ],
            "hit_unit": "colunas acertadas",
            "prize_tiers": [
                _outcome_record(outcomes[hits], denominator, f"{hits} acertos", hits=hits)
                for hits in spec["prize_hits"]
            ],
            "any_prize": _outcome_record(sum(outcomes[hits] for hits in spec["prize_hits"]), denominator, "Qualquer faixa de prêmio"),
        }
        result["column_pick_counts"] = column_picks
        result["probability_scope"] = "Probabilidades teóricas exatas sob sorteios uniformes e independentes; os numeradores e denominadores são contagens inteiras."
        return result
    if pick_count is None:
        picks = spec["pick_size"]
    elif type(pick_count) is int:
        picks = pick_count
    else:
        raise ValueError("pick_count deve ser um número inteiro.")
    if picks < spec["min_pick"] or picks > spec["max_pick"]:
        if key == "maismilionaria":
            raise ValueError("A +Milionária aceita apostas de 6 a 12 dezenas nesta ferramenta.")
        raise ValueError(f"{spec['name']} aceita jogos de {spec['min_pick']} a {spec['max_pick']} dezenas nesta ferramenta.")
    if key == "maismilionaria" and (type(trevo_count) is not int or not 2 <= trevo_count <= 6):
        raise ValueError("trevo_count deve ser um número inteiro de 2 a 6.")
    if key == "lotomania":
        single_hit_counts, denominator = _hypergeometric_counts(100, picks, 20)
        winning = single_hit_counts.get(20, 0)
        label = "20 acertos"
    else:
        draw_size = spec["draw_size"]
        single_hit_counts, denominator = _hypergeometric_counts(spec["maximum"] - spec["minimum"] + 1, picks, draw_size)
        winning = single_hit_counts.get(draw_size, 0)
        label = f"{draw_size} acertos"
    hit_counts = single_hit_counts
    hit_denominator = denominator
    hit_unit = "acertos"
    if key == "duplasena":
        cumulative_single = 0
        previous_max_favorable = 0
        best_of_two_counts = {}
        for hits, count in sorted(single_hit_counts.items()):
            cumulative_single += count
            max_favorable = cumulative_single ** 2
            best_of_two_counts[hits] = max_favorable - previous_max_favorable
            previous_max_favorable = max_favorable
        hit_counts = best_of_two_counts
        hit_denominator = denominator ** 2
        hit_unit = "acertos no melhor dos dois sorteios"
    probability = winning / denominator
    event_favorable = winning
    event_denominator = denominator
    extra_method = None
    if key == "duplasena":
        event_favorable = denominator ** 2 - (denominator - winning) ** 2
        event_denominator = denominator ** 2
        probability = event_favorable / event_denominator
        label = "6 acertos em pelo menos um dos dois sorteios"
        extra_method = "Considera os dois sorteios independentes do concurso."
    elif key == "maismilionaria":
        event_favorable = winning * comb(trevo_count, 2)
        event_denominator = denominator * comb(6, 2)
        probability = event_favorable / event_denominator
        label = "Faixa 1 · ao menos uma subaposta"
        extra_method = f"Aposta múltipla de {picks} dezenas e {trevo_count} trevos; o cálculo considera cada combinação de 6 dezenas e 2 trevos."
    elif key == "timemania":
        extra_method = "Probabilidade exibida para as dezenas; o Time do Coração é uma categoria separada."
    elif key == "diadesorte":
        probability /= 12
        event_denominator = denominator * 12
        label = "7 dezenas + Mês da Sorte"
    result = {"event": label, "one_in": round(1 / probability) if probability > 0 else None, "percent": probability * 100, "favorable_outcomes": str(event_favorable), "total_outcomes": str(event_denominator), "method": extra_method or "Combinações equiprováveis conforme o universo numérico definido para a modalidade."}

    hit_rows = [
        _outcome_record(count, hit_denominator, hits=hits)
        for hits, count in sorted(hit_counts.items())
    ]
    result["hit_distribution"] = hit_rows
    result["hit_unit"] = hit_unit
    hit_map = single_hit_counts
    main_prize_hits = list(spec["prize_hits"])
    main_prize_outcomes = sum(hit_map.get(hits, 0) for hits in main_prize_hits)
    prize_rows = []

    if key == "duplasena":
        for hits in main_prize_hits:
            single = hit_map.get(hits, 0)
            if single:
                favorable = denominator ** 2 - (denominator - single) ** 2
                prize_rows.append(_outcome_record(favorable, denominator ** 2, f"Pelo menos um sorteio com {hits} acertos", hits=hits, scope="at_least_one_of_two_draws", may_overlap=True))
        any_prize = denominator ** 2 - (denominator - main_prize_outcomes) ** 2
        any_denominator = denominator ** 2
    elif key == "maismilionaria":
        official_tiers = (
            (1, 6, (2,), "Faixa 1 · 6 acertos + 2 trevos"),
            (2, 6, (0, 1), "Faixa 2 · 6 acertos + 1 ou nenhum trevo"),
            (3, 5, (2,), "Faixa 3 · 5 acertos + 2 trevos"),
            (4, 5, (0, 1), "Faixa 4 · 5 acertos + 1 ou nenhum trevo"),
            (5, 4, (2,), "Faixa 5 · 4 acertos + 2 trevos"),
            (6, 4, (0, 1), "Faixa 6 · 4 acertos + 1 ou nenhum trevo"),
            (7, 3, (2,), "Faixa 7 · 3 acertos + 2 trevos"),
            (8, 3, (1,), "Faixa 8 · 3 acertos + 1 trevo"),
            (9, 2, (2,), "Faixa 9 · 2 acertos + 2 trevos"),
            (10, 2, (1,), "Faixa 10 · 2 acertos + 1 trevo"),
        )
        # For each intersection size, count the six-number and two-trevo
        # subbets analytically. A tier row means at least one subbet wins it;
        # different tiers may occur on one ticket, but a draw counts once in
        # the union event below.
        trevo_draw_counts = {
            hits: _choose_count(trevo_count, hits) * _choose_count(6 - trevo_count, 2 - hits)
            for hits in range(3)
        }
        trevo_total = comb(6, 2)
        presence = {tier: 0 for tier, *_ in official_tiers}
        any_prize = 0
        for main_hits, main_outcomes in hit_map.items():
            for drawn_trevo_hits, trevo_draw_outcomes in trevo_draw_counts.items():
                if not trevo_draw_outcomes:
                    continue
                subbet_awards = _million_subbet_award_counts(main_hits, picks, drawn_trevo_hits, trevo_count)
                if subbet_awards:
                    any_prize += main_outcomes * trevo_draw_outcomes
                for tier_number, _tier_main_hits, _tier_trevo_hits, tier_label in official_tiers:
                    if tier_label in subbet_awards:
                        presence[tier_number] += main_outcomes * trevo_draw_outcomes
        for tier_number, main_hits, trevo_hits, label in official_tiers:
            favorable = presence[tier_number]
            total = denominator * trevo_total
            prize_rows.append(_outcome_record(
                favorable, total, label, hits=main_hits,
                trevo_hits=trevo_hits[0] if len(trevo_hits) == 1 else list(trevo_hits),
                tier=tier_number, may_overlap=True, probability_kind="presence_per_ticket",
            ))
        any_denominator = denominator * trevo_total
        result["ticket_subbets"] = comb(picks, 6) * comb(trevo_count, 2)
        result["pick_count"] = picks
        result["trevo_count"] = trevo_count
    else:
        for hits in main_prize_hits:
            favorable = hit_map.get(hits, 0)
            if favorable:
                prize_rows.append(_outcome_record(favorable, denominator, f"{hits} acertos", hits=hits))
        any_prize = main_prize_outcomes
        any_denominator = denominator

        if key == "diadesorte":
            prize_rows.append(_outcome_record(1, 12, "Mês da Sorte", overlaps_main_prizes=True))
            any_prize = denominator * 12 - (denominator - main_prize_outcomes) * 11
            any_denominator = denominator * 12
        elif key == "timemania":
            prize_rows.append(_outcome_record(1, 80, "Time do Coração", overlaps_main_prizes=True))
            any_prize = denominator * 80 - (denominator - main_prize_outcomes) * 79
            any_denominator = denominator * 80

    result["prize_tiers"] = prize_rows
    result["any_prize"] = _outcome_record(any_prize, any_denominator, "Pelo menos uma categoria de prêmio")
    result["probability_scope"] = "Probabilidades teóricas exatas sob sorteios uniformes e independentes; as faixas nomeadas são eventos específicos, não previsões."
    return result


def combinations_count(n: int, k: int) -> int:
    if n < 0 or k < 0 or k > n:
        return 0
    return comb(n, k)


def _int_list(values) -> list[int]:
    if values is None:
        return []
    if isinstance(values, str):
        values = [part.strip() for part in values.replace(";", ",").replace(" ", ",").split(",") if part.strip()]
    out = []
    for value in values:
        try:
            out.append(int(value))
        except (TypeError, ValueError):
            continue
    return out
