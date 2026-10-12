"""Cliente somente leitura da API pública do Portal de Loterias da CAIXA."""
from datetime import datetime, timezone
import requests

from .catalog import get_spec

BASE_URL = "https://servicebus2.caixa.gov.br/portaldeloterias/api"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Lotomaster/1.1; consulta de resultados publicos)",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://loterias.caixa.gov.br/",
    "Origin": "https://loterias.caixa.gov.br",
}
MONTHS = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "março": 3, "abril": 4,
    "maio": 5, "junho": 6, "julho": 7, "agosto": 8, "setembro": 9,
    "outubro": 10, "novembro": 11, "dezembro": 12,
}


def _integers(values):
    result = []
    for value in values or []:
        try:
            result.append(int(str(value).strip()))
        except (TypeError, ValueError):
            continue
    return result


def _clean_text(value):
    if value is None:
        return None
    cleaned = "".join(ch for ch in str(value) if ch.isprintable()).strip()
    return cleaned or None


def normalize_draw(game: str, data: dict) -> dict:
    spec = get_spec(game)
    key = spec["key"]
    numbers = _integers(data.get("listaDezenas") or data.get("dezenasSorteadasOrdemSorteio"))
    if key != "supersete":
        numbers = sorted(numbers)
    ordered = _integers(data.get("dezenasSorteadasOrdemSorteio"))
    second = _integers(data.get("listaDezenasSegundoSorteio"))
    if key == "duplasena" and not second and len(ordered) >= 12:
        second = ordered[6:12]
    raw_bonus = data.get("trevosSorteados") or []
    trevos = _integers(raw_bonus)
    if key == "maismilionaria" and not trevos and len(ordered) >= 8:
        trevos = ordered[-2:]
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
    awards = []
    for item in data.get("listaRateioPremio") or []:
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
        "contest": int(data.get("numero") or 0),
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
