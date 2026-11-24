"""Cliente somente leitura da API pública do Portal de Loterias da CAIXA."""
from datetime import datetime, timezone
import math
import os
import re

import requests

from .catalog import get_spec
from .validation import validate_draw

BASE_URL = os.getenv(
    "LOTOMASTER_CAIXA_PROXY_URL",
    "https://lotomaster-caixa-proxy-test.robsonboiling.workers.dev",
).rstrip("/")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Lotomaster/1.1; consulta de resultados publicos)",
    "Accept": "application/json",
}
MONTHS = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "março": 3, "abril": 4,
    "maio": 5, "junho": 6, "julho": 7, "agosto": 8, "setembro": 9,
    "outubro": 10, "novembro": 11, "dezembro": 12,
}


def _integer(value, field: str) -> int:
    """Accept integers and decimal digit strings, never bools/floats/truncations."""
    if isinstance(value, bool):
        raise ValueError(f"Campo {field} inválido.")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and re.fullmatch(r"\s*[+-]?\d+\s*", value):
        return int(value)
    raise ValueError(f"Campo {field} inválido.")


def _integer_list(values, field: str) -> list[int]:
    if values is None:
        return []
    if not isinstance(values, (list, tuple)):
        raise ValueError(f"Campo {field} precisa ser uma lista.")
    if len(values) > 20:
        raise ValueError(f"Campo {field} é excessivo.")
    return [_integer(value, field) for value in values]


def _integers(values):
    """Compatibilidade interna para arrays de dezenas opcionais da CAIXA."""
    return _integer_list(values, "dezenas")


def _clean_text(value):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Campo textual da resposta da CAIXA inválido.")
    cleaned = " ".join("".join(" " if ch.isspace() else ch if ch.isprintable() else "" for ch in value).split())
    return cleaned or None


def _validate_numbers(values: list[int], spec: dict, field: str, *, count=None, unique=True) -> list[int]:
    expected = spec["draw_size"] if count is None else count
    if len(values) != expected:
        raise ValueError(f"Campo {field} precisa conter exatamente {expected} dezenas.")
    if unique and len(set(values)) != len(values):
        raise ValueError(f"Campo {field} contém dezenas duplicadas.")
    minimum, maximum = spec["minimum"], spec["maximum"]
    if any(number < minimum or number > maximum for number in values):
        raise ValueError(f"Campo {field} contém dezenas fora da faixa {minimum}–{maximum}.")
    return values


def _amount(value, field: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"Campo {field} inválido.")
    try:
        result = float(value or 0)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"Campo {field} inválido.") from exc
    if not math.isfinite(result) or result < 0:
        raise ValueError(f"Campo {field} precisa ser um valor finito não negativo.")
    return result


def _date(value, field: str):
    text = _clean_text(value)
    if text is None:
        return None
    try:
        datetime.strptime(text, "%d/%m/%Y")
    except ValueError as exc:
        raise ValueError(f"Campo {field} não é uma data válida no formato DD/MM/AAAA.") from exc
    return text


def normalize_draw(game: str, data: dict) -> dict:
    """Normalize only structurally plausible CAIXA results; reject incomplete draws."""
    if not isinstance(data, dict):
        raise ValueError("A resposta da CAIXA precisa ser um objeto.")
    spec = get_spec(game)
    key = spec["key"]
    ordered_raw = data.get("dezenasSorteadasOrdemSorteio")
    ordered = _integer_list(ordered_raw, "dezenasSorteadasOrdemSorteio") if ordered_raw is not None else []
    raw_numbers = data.get("listaDezenas")
    if raw_numbers is None:
        # Known legacy encodings put main numbers first; +Milionária appends trevos.
        raw_numbers = ordered[:spec["draw_size"]]
    parsed_numbers = _integer_list(raw_numbers, "listaDezenas")
    combined_trevos = parsed_numbers[6:] if key == "maismilionaria" and len(parsed_numbers) == 8 else []
    if combined_trevos:
        parsed_numbers = parsed_numbers[:6]
    numbers = _validate_numbers(parsed_numbers, spec, "listaDezenas", unique=key != "supersete")
    numbers = numbers[:] if key == "supersete" else sorted(numbers)
    if ordered:
        if key == "duplasena" and len(ordered) in {6, 12}:
            _validate_numbers(ordered[:6], spec, "dezenasSorteadasOrdemSorteio 1º sorteio")
            if len(ordered) == 12:
                _validate_numbers(ordered[6:], spec, "dezenasSorteadasOrdemSorteio 2º sorteio")
        elif key == "maismilionaria" and len(ordered) in {6, 8}:
            _validate_numbers(ordered[:6], spec, "dezenasSorteadasOrdemSorteio")
        else:
            ordered = _validate_numbers(ordered, spec, "dezenasSorteadasOrdemSorteio", unique=key != "supersete")
    else:
        ordered = numbers[:]

    second_raw = data.get("listaDezenasSegundoSorteio")
    if second_raw is None and key == "duplasena" and len(ordered) == 12:
        second_raw = ordered[6:12]
    second = _integer_list(second_raw, "listaDezenasSegundoSorteio") if second_raw is not None else []
    if key == "duplasena":
        second = sorted(_validate_numbers(second, spec, "listaDezenasSegundoSorteio"))
    elif second:
        raise ValueError(f"Campo listaDezenasSegundoSorteio não é aplicável a {spec['name']}.")

    raw_bonus = data.get("trevosSorteados")
    trevos = _integer_list(raw_bonus, "trevosSorteados") if raw_bonus is not None else []
    candidates = [candidate for candidate in (
        combined_trevos,
        ordered[6:] if key == "maismilionaria" and len(ordered) == 8 else [],
        trevos,
    ) if candidate]
    if key == "maismilionaria" and candidates and any(sorted(candidate) != sorted(candidates[0]) for candidate in candidates[1:]):
        raise ValueError("Trevos contraditórios na resposta.")
    if key == "maismilionaria" and not trevos and candidates:
        trevos = candidates[0]
    if key == "maismilionaria":
        bonus = spec["bonus"]
        # bonus.minimum is the minimum count selected, not the lowest trevo value.
        trevo_spec = {**spec, "minimum": 1, "maximum": bonus["maximum"]}
        trevos = _validate_numbers(trevos, trevo_spec, "trevosSorteados", count=bonus["draw_size"])
    elif trevos:
        raise ValueError(f"Campo trevosSorteados não é aplicável a {spec['name']}.")
    month_name = None
    month_number = None
    team = None
    special = _clean_text(data.get("nomeTimeCoracaoMesSorte"))
    if key == "diadesorte":
        month_name = special
        month_number = MONTHS.get(month_name.casefold()) if month_name else None
        if month_number is None:
            raise ValueError("Resposta da CAIXA sem um Mês da Sorte reconhecido.")
    elif key == "timemania":
        team = special
        if not team:
            raise ValueError("Resposta da CAIXA sem Time do Coração.")
    elif special:
        raise ValueError(f"Campo nomeTimeCoracaoMesSorte não é aplicável a {spec['name']}.")

    special_value = data.get("indicadorConcursoEspecial", "")
    if not isinstance(special_value, (str, int, bool)):
        raise ValueError("Campo indicadorConcursoEspecial inválido.")
    # CAIXA uses 1 for regular contests and 2 for special contests.
    is_special_draw = str(special_value).strip().casefold() in {"true", "2", "s", "sim"}
    contest = _integer(data.get("numero"), "numero")
    if contest <= 0:
        raise ValueError("Número de concurso precisa ser positivo.")
    validate_draw(key, {
        "game": key, "contest": contest, "numbers": numbers,
        "ordered_numbers": ordered or numbers, "second_numbers": second,
        "trevos": trevos, "month": {"name": month_name, "number": month_number} if month_name else None,
        "team": team, "special_draw": is_special_draw,
    }, require_game=True, require_special=True)
    raw_awards = data.get("listaRateioPremio") or []
    if not isinstance(raw_awards, list) or len(raw_awards) > 50:
        raise ValueError("Lista de rateios inválida ou excessiva.")
    awards = []
    for item in raw_awards:
        if not isinstance(item, dict):
            raise ValueError("Faixa de premiação inválida.")
        winners = _integer(item.get("numeroDeGanhadores", 0), "numeroDeGanhadores")
        if winners < 0:
            raise ValueError("Campo numeroDeGanhadores não pode ser negativo.")
        awards.append({
            "label": _clean_text(item.get("descricaoFaixa")) or "Faixa",
            "winners": winners,
            "prize": _amount(item.get("valorPremio", 0), "valorPremio"),
        })

    return {
        "game": key,
        "name": spec["name"],
        "contest": contest,
        "draw_date": _date(data.get("dataApuracao"), "dataApuracao"),
        "next_draw_date": _date(data.get("dataProximoConcurso"), "dataProximoConcurso"),
        "numbers": numbers,
        "ordered_numbers": ordered,
        "second_numbers": second,
        "trevos": trevos,
        "month": {"name": month_name, "number": month_number} if month_name else None,
        "team": team,
        "special_draw": is_special_draw,
        "contest_type": _clean_text(data.get("tipoJogo")),
        "accumulated": bool(data.get("acumulado", False)),
        "estimated_prize": _amount(data.get("valorEstimadoProximoConcurso", 0), "valorEstimadoProximoConcurso"),
        "next_prize": _amount(data.get("valorAcumuladoProximoConcurso", 0), "valorAcumuladoProximoConcurso"),
        "location": _clean_text(data.get("localSorteio")),
        "winners_by_tier": awards,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def fetch_draw(game: str, contest: int | None = None) -> dict:
    spec = get_spec(game)
    url = f"{BASE_URL}/{spec['endpoint']}"
    if contest is not None:
        contest = _integer(contest, "concurso solicitado")
        if contest <= 0:
            raise ValueError("Número de concurso solicitado precisa ser positivo.")
        url += f"/{contest}"
    response = requests.get(url, headers=HEADERS, timeout=18)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError(f"A CAIXA não retornou um concurso válido para {spec['name']}.")
    draw = normalize_draw(spec["key"], payload)
    if contest is not None and draw["contest"] != contest:
        raise ValueError(f"A CAIXA retornou o concurso {draw['contest']} em vez do concurso {contest}.")
    return draw
