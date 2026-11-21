"""Cliente somente leitura da API pública do Portal de Loterias da CAIXA."""
from datetime import datetime, timezone
import os
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


def _integers(values):
    if values is None:
        return []
    if not isinstance(values, list) or len(values) > 20:
        raise ValueError("Lista de dezenas inválida ou excessiva.")
    result = []
    for value in values:
        if type(value) is int:
            result.append(value)
        elif isinstance(value, str) and 1 <= len(value.strip()) <= 3 and value.strip().isascii() and value.strip().isdigit():
            result.append(int(value.strip()))
        else:
            raise ValueError("Dezena inválida na resposta da CAIXA.")
    return result


def _clean_text(value):
    if value is None:
        return None
    cleaned = " ".join("".join(" " if ch.isspace() else ch if ch.isprintable() else "" for ch in str(value)).split())
    return cleaned or None


def normalize_draw(game: str, data: dict) -> dict:
    spec = get_spec(game)
    key = spec["key"]
    if not isinstance(data, dict):
        raise ValueError("Resposta da CAIXA inválida.")
    raw_contest = data.get("numero")
    if type(raw_contest) is int:
        contest = raw_contest
    elif isinstance(raw_contest, str) and raw_contest.isascii() and raw_contest.isdigit() and len(raw_contest) <= 10:
        contest = int(raw_contest)
    else:
        raise ValueError("Número de concurso inválido.")
    main = data.get("listaDezenas")
    numbers = _integers(main if main is not None else data.get("dezenasSorteadasOrdemSorteio"))
    combined_trevos = numbers[6:] if key == "maismilionaria" and len(numbers) == 8 else []
    if (main is None and key in {"duplasena", "maismilionaria"}) or combined_trevos:
        numbers = numbers[:spec["draw_size"]]
    if key != "supersete":
        numbers = sorted(numbers)
    ordered = _integers(data.get("dezenasSorteadasOrdemSorteio"))
    second = _integers(data.get("listaDezenasSegundoSorteio"))
    if key == "duplasena" and not second and len(ordered) >= 12:
        second = ordered[6:12]
    raw_bonus = data.get("trevosSorteados") or []
    trevos = _integers(raw_bonus)
    if key == "maismilionaria":
        candidates = [x for x in (combined_trevos, ordered[6:] if len(ordered) == 8 else [], trevos) if x]
        if candidates and any(sorted(x) != sorted(candidates[0]) for x in candidates[1:]):
            raise ValueError("Trevos contraditórios na resposta.")
        if not trevos:
            trevos = ordered[6:] if len(ordered) == 8 else combined_trevos
    month_name = None
    month_number = None
    team = None
    special = _clean_text(data.get("nomeTimeCoracaoMesSorte"))
    if key == "diadesorte":
        month_name = special
        if month_name:
            month_number = MONTHS.get(month_name.casefold())
    elif key == "timemania":
        team = special
    special_value = str(data.get("indicadorConcursoEspecial", "")).strip().casefold()
    is_special_draw = special_value in {"true", "1", "s", "sim"}
    contest_type = _clean_text(data.get("tipoJogo"))
    validate_draw(key, {
        "game": key, "contest": contest, "numbers": numbers,
        "ordered_numbers": ordered or numbers, "second_numbers": second,
        "trevos": trevos, "month": {"name": month_name, "number": month_number} if month_name else None,
        "team": team, "special_draw": is_special_draw,
    }, require_game=True, require_special=True)
    awards = []
    raw_awards = data.get("listaRateioPremio") or []
    if not isinstance(raw_awards, list) or len(raw_awards) > 50:
        raise ValueError("Lista de rateios inválida ou excessiva.")
    for item in raw_awards:
        awards.append({
            "label": _clean_text(item.get("descricaoFaixa")) or "Faixa",
            "winners": int(item.get("numeroDeGanhadores") or 0),
            "prize": float(item.get("valorPremio") or 0),
        })
    draw_date = _clean_text(data.get("dataApuracao"))
    next_date = _clean_text(data.get("dataProximoConcurso"))
    return {
        "game": key,
        "name": spec["name"],
        "contest": contest,
        "draw_date": draw_date,
        "next_draw_date": next_date,
        "numbers": numbers,
        "ordered_numbers": ordered or numbers,
        "second_numbers": second,
        "trevos": trevos,
        "month": {"name": month_name, "number": month_number} if month_name else None,
        "team": team,
        "special_draw": is_special_draw,
        "contest_type": contest_type,
        "accumulated": bool(data.get("acumulado", False)),
        "estimated_prize": float(data.get("valorEstimadoProximoConcurso") or 0),
        "next_prize": float(data.get("valorAcumuladoProximoConcurso") or 0),
        "location": _clean_text(data.get("localSorteio")),
        "winners_by_tier": awards,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def fetch_draw(game: str, contest: int | None = None) -> dict:
    spec = get_spec(game)
    url = f"{BASE_URL}/{spec['endpoint']}"
    if contest is not None:
        url += f"/{int(contest)}"
    response = requests.get(url, headers=HEADERS, timeout=18)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or not payload.get("numero"):
        raise ValueError(f"A CAIXA não retornou um concurso válido para {spec['name']}.")
    draw = normalize_draw(spec["key"], payload)
    if contest is not None and draw["contest"] != int(contest):
        raise ValueError(f"A CAIXA retornou o concurso {draw['contest']} em vez do concurso {int(contest)}.")
    if not draw["numbers"]:
        raise ValueError(f"A resposta da CAIXA não trouxe dezenas para {spec['name']}.")
    return draw
