"""Serviços de negócio da Lotomaster: histórico oficial, geração e conferência de jogos."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from math import comb
import random
import threading
import time

from .catalog import get_spec
from .caixa import fetch_draw
from . import storage

_LATEST_TTL_SECONDS = 90
_latest_cache: dict[str, tuple[float, dict]] = {}
_latest_lock = threading.Lock()


def latest_result(game: str, refresh: bool = True) -> dict:
    spec = get_spec(game)
    key = spec["key"]
    now = time.monotonic()
    cached_mem = _latest_cache.get(key)
    if not refresh and cached_mem and now - cached_mem[0] < _LATEST_TTL_SECONDS:
        return {**cached_mem[1], "source": "cache"}
    cached_db = storage.latest_draw(key)
    if cached_mem and now - cached_mem[0] < _LATEST_TTL_SECONDS:
        return {**cached_mem[1], "source": "cache"}
    try:
        draw = fetch_draw(key)
        storage.save_draw(draw)
        _latest_cache[key] = (now, draw)
        return {**draw, "source": "CAIXA"}
    except Exception as exc:
        if cached_db:
            _latest_cache[key] = (now, cached_db)
            return {**cached_db, "source": "cache", "warning": f"A CAIXA está temporariamente indisponível: {exc}"}
        raise RuntimeError(f"Não foi possível consultar a CAIXA para {spec['name']}: {exc}") from exc


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
    cached = storage.list_draws(key, limit)
    if limit > 1 and latest:
        current_contest = int(latest["contest"])
        have = {int(draw["contest"]) for draw in cached}
        target_contests = [n for n in range(current_contest - 1, max(0, current_contest - limit), -1) if n not in have]
        if target_contests:
            with ThreadPoolExecutor(max_workers=5) as pool:
                futures = {pool.submit(fetch_draw, key, contest): contest for contest in target_contests}
                for future in as_completed(futures):
                    try:
                        storage.save_draw(future.result())
                    except Exception:
                        continue
    results = storage.list_draws(key, limit)
    return results or ([latest] if latest else [])


def generate_tickets(game: str, options: dict | None = None) -> list[dict]:
    spec = get_spec(game)
    options = options or {}
    count = int(options.get("count", 1))
    if count < 1 or count > 100:
        raise ValueError("A quantidade de jogos deve ficar entre 1 e 100.")
    seed = options.get("seed")
    rng = random.Random(seed) if seed is not None else random.SystemRandom()
    filters = options.get("filters") or {}
    latest = storage.latest_draw(spec["key"])
    previous = set(latest.get("numbers", [])) if latest else set()
    generated = []

    if spec["key"] == "supersete":
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
                chosen = fixed + rng.sample(available, pick_count - len(fixed))
                columns.append(sorted(chosen))
            generated.append(_ticket_summary(spec, {"columns": columns, "numbers": [c[0] for c in columns]}, ticket_index + 1, previous))
        return generated

    pick_count = int(options.get("pick_count", spec["pick_size"]))
    if pick_count < spec["min_pick"] or pick_count > spec["max_pick"]:
        raise ValueError(f"{spec['name']} aceita jogos de {spec['min_pick']} a {spec['max_pick']} dezenas nesta ferramenta.")
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
    available = [n for n in candidates if n not in excluded and n not in fixed]
    tries = max(300, count * 300)
    for ticket_index in range(count):
        chosen = None
        for _ in range(tries):
            numbers = sorted(fixed + rng.sample(available, pick_count - len(fixed)))
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
                    month = int(month)
                except (TypeError, ValueError):
                    raise ValueError(f"O Mês da Sorte deve estar entre {bonus['minimum']} e {bonus['maximum']}.") from None
                if not bonus["minimum"] <= month <= bonus["maximum"]:
                    raise ValueError(f"O Mês da Sorte deve estar entre {bonus['minimum']} e {bonus['maximum']}.")
            extra["month"] = month
        elif bonus_type == "team":
            extra["team"] = str(bonus_options.get("team", "")).strip()
        elif bonus_type == "trevos":
            trevo_count = int(bonus_options.get("trevo_count", 2))
            if trevo_count < bonus["minimum"] or trevo_count > bonus["maximum"]:
                raise ValueError(f"Escolha entre {bonus['minimum']} e {bonus['maximum']} trevos.")
            extra["trevos"] = sorted(rng.sample(range(1, 7), trevo_count))
        generated.append(_ticket_summary(spec, {"numbers": chosen, **extra}, ticket_index + 1, previous))
    return generated


def _ticket_summary(spec: dict, ticket: dict, ticket_number: int, previous: set[int]) -> dict:
    numbers = ticket.get("numbers", [])
    if spec["key"] == "supersete":
        probability_value = 1.0
        for column in ticket.get("columns", []):
            probability_value *= len(column) / 10
        probability = {"event": "7 acertos em 7 colunas", "one_in": round(1 / probability_value) if probability_value else None, "percent": probability_value * 100, "method": "Produto da seleção de dígitos por coluna; não é previsão."}
    else:
        probability = ticket_probability(spec["key"], len(numbers), len(ticket.get("trevos", [])) or 2)
    return {
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


def _passes_filters(numbers: list[int], filters: dict, previous: set[int]) -> bool:
    total = sum(numbers)
    evens = sum(n % 2 == 0 for n in numbers)
    repeats = len(set(numbers) & previous)
    conditions = (
        ("min_sum", total, lambda a, b: a >= b),
        ("max_sum", total, lambda a, b: a <= b),
        ("min_even", evens, lambda a, b: a >= b),
        ("max_even", evens, lambda a, b: a <= b),
        ("min_repeated", repeats, lambda a, b: a >= b),
        ("max_repeated", repeats, lambda a, b: a <= b),
    )
    for key, actual, compare in conditions:
        if filters.get(key) not in (None, "") and not compare(actual, int(filters[key])):
            return False
    return True


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
            drawn_team = (draw.get("team") or "").casefold()
            team_hit = bool(bonus.get("team") and drawn_team and str(bonus["team"]).casefold() == drawn_team)
            extra["team_hit"] = team_hit
            extra["drawn_team"] = draw.get("team")
            if team_hit:
                award = award or "Time do Coração"
        elif spec["key"] == "maismilionaria":
            trevo_hits = len(set(_int_list(bonus.get("trevos", []))) & set(draw.get("trevos", [])))
            extra["trevo_hits"] = trevo_hits
            extra["drawn_trevos"] = draw.get("trevos", [])
            award = _million_award(main_hits, trevo_hits)
        results.append({"ticket_number": ticket.get("ticket_number", idx), "main_hits": main_hits, "hits": main_hits, "award": award, "draw_contest": draw.get("contest"), **extra})
    return results


def _validate_ticket(spec: dict, ticket: dict) -> None:
    key = spec["key"]
    bonus = ticket.get("bonus", {}) or {}
    if key == "supersete":
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
    if not spec["min_pick"] <= len(numbers) <= spec["max_pick"]:
        raise ValueError(f"{spec['name']} aceita jogos de {spec['min_pick']} a {spec['max_pick']} dezenas nesta ferramenta.")
    if any(n < spec["minimum"] or n > spec["maximum"] for n in numbers):
        raise ValueError(f"As dezenas de {spec['name']} precisam estar no intervalo {spec['minimum']}–{spec['maximum']}.")
    if bonus.get("month") not in (None, "") and not 1 <= int(bonus["month"]) <= 12:
        raise ValueError("O Mês da Sorte deve estar entre 1 e 12.")
    if key == "maismilionaria" or bonus.get("trevos"):
        trevos = _int_list(bonus.get("trevos"))
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
        (6, 2): "6 acertos + 2 trevos", (6, 1): "6 acertos + 1 trevo", (6, 0): "6 acertos",
        (5, 2): "5 acertos + 2 trevos", (5, 1): "5 acertos + 1 trevo", (5, 0): "5 acertos",
        (4, 2): "4 acertos + 2 trevos", (4, 1): "4 acertos + 1 trevo", (4, 0): "4 acertos",
        (3, 2): "3 acertos + 2 trevos", (3, 1): "3 acertos + 1 trevo",
        (2, 2): "2 acertos + 2 trevos",
    }
    return tiers.get((main_hits, trevo_hits))


def ticket_probability(game: str, pick_count: int | None = None, trevo_count: int = 2) -> dict:
    spec = get_spec(game)
    key = spec["key"]
    if key == "supersete":
        total = 10 ** 7
        one = 1 / total
        return {"event": "7 acertos em 7 colunas", "one_in": total, "percent": one * 100, "method": "7 algarismos independentes em 7 colunas"}
    picks = int(pick_count or spec["pick_size"])
    if picks < spec["min_pick"] or picks > spec["max_pick"]:
        raise ValueError(f"{spec['name']} aceita jogos de {spec['min_pick']} a {spec['max_pick']} dezenas nesta ferramenta.")
    if key == "lotomania":
        denominator = comb(100, 20)
        winning = comb(picks, 20) if picks >= 20 else 0
        probability = winning / denominator
        label = "20 acertos"
    else:
        draw_size = spec["draw_size"]
        denominator = comb(spec["maximum"] - spec["minimum"] + 1, draw_size)
        winning = comb(picks, draw_size) if picks >= draw_size else 0
        probability = winning / denominator
        label = f"{draw_size} acertos"
    extra_method = None
    if key == "duplasena":
        probability = 1 - (1 - probability) ** 2
        label = "6 acertos em pelo menos um dos dois sorteios"
        extra_method = "Considera os dois sorteios independentes do concurso."
    elif key == "maismilionaria":
        trevo_count = max(2, min(6, int(trevo_count)))
        probability *= comb(trevo_count, 2) / comb(6, 2)
        label = "6 dezenas + os 2 trevos sorteados"
        extra_method = f"Inclui seleção de {trevo_count} trevos dentre 6."
    elif key == "timemania":
        extra_method = "Probabilidade exibida para as dezenas; o Time do Coração é uma categoria separada."
    elif key == "diadesorte":
        probability /= 12
        label = "7 dezenas + Mês da Sorte"
    return {"event": label, "one_in": round(1 / probability) if probability > 0 else None, "percent": probability * 100, "method": extra_method or "Combinações equiprováveis conforme o universo numérico definido para a modalidade."}


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
