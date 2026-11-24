"""API e aplicação web Lotomaster. Execute com: uvicorn lotomaster.api:app --port 8020."""
import csv
from io import StringIO
from pathlib import Path
from typing import Annotated, Literal
from zipfile import ZIP_DEFLATED, ZipFile
from xml.sax.saxutils import escape

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, StrictInt

from . import storage
from .assistant_access import authorize_server_gemini_request
from .analytics import analyze_draws, pareto_filter_data
from .assistant import build_assistant_report
from .caixa import BASE_URL, fetch_draw
from .catalog import get_spec, public_catalog, public_spec
from .validation import MAX_DRAWS, validate_draw, validate_draws
from .request_limits import DrawBodyLimit
from .client_draws import validate_client_draws
from .combination_counter import count_lotofacil_combinations
from .closures import exhaustive_closure
from .engine import generate_tickets, latest_result, list_history_page, list_results, simulate_tickets, simulate_ticket_history, ticket_probability
from .history_number_search import search_lotofacil_history
from .repeated_closure import repeated_closure

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"

app = FastAPI(
    title="Lotomaster — Estatísticas e Jogos",
    description="Resultados oficiais da CAIXA, gerador, simulador e estatísticas históricas.",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url=None,
)
app.add_middleware(DrawBodyLimit)


class GenerateRequest(BaseModel):
    count: StrictInt = Field(default=1, ge=1, le=100)
    pick_count: StrictInt | None = None
    fixed: list[StrictInt] = Field(default_factory=list, max_length=50)
    excluded: list[StrictInt] = Field(default_factory=list, max_length=100)
    bonus: dict = Field(default_factory=dict)
    filters: dict = Field(default_factory=dict)
    columns: dict = Field(default_factory=dict)
    weights: dict | None = None
    pareto: bool = False
    seed: StrictInt | None = None


class ClosureRequest(BaseModel):
    pool: list[StrictInt] = Field(max_length=100)
    pick_count: StrictInt
    fixed: list[StrictInt] = Field(default_factory=list, max_length=100)
    filters: dict = Field(default_factory=dict)
    reference_contest: StrictInt | None = Field(default=None, ge=1)
    offset: StrictInt = Field(default=0, ge=0)
    page_size: StrictInt = Field(default=1000, ge=1, le=1000)


class RepeatedClosureRequest(BaseModel):
    previous_draw: list[StrictInt] = Field(min_length=15, max_length=15)
    repeated: list[StrictInt] = Field(min_length=6, max_length=12)
    filters: dict = Field(default_factory=dict)
    reference_contest: StrictInt | None = Field(default=None, ge=1)
    offset: StrictInt = Field(default=0, ge=0)
    page_size: StrictInt = Field(default=1000, ge=1, le=1000)


class Ticket(BaseModel):
    numbers: list[StrictInt] = Field(default_factory=list, max_length=50)
    columns: list[Annotated[list[StrictInt], Field(min_length=1, max_length=10)]] | None = Field(default=None, max_length=7)
    bonus: dict = Field(default_factory=dict)
    ticket_number: StrictInt | None = None


class SimulateRequest(BaseModel):
    tickets: list[Ticket] = Field(default_factory=list, max_length=500)
    contest: StrictInt | None = None
    draw: dict | None = None


class HistorySimulateRequest(BaseModel):
    tickets: list[Ticket] = Field(default_factory=list, max_length=500)
    draws: list[dict] = Field(default_factory=list, max_length=5000)


class AnalyzeDrawsRequest(BaseModel):
    draws: list[dict] = Field(default_factory=list, max_length=5000)


class HistoryNumberSearchRequest(BaseModel):
    numbers: list[StrictInt] = Field(min_length=1, max_length=15)
    draws: list[dict] = Field(..., max_length=5000)
    match_mode: Literal["contains_all", "exact", "excludes_all"] = "contains_all"


class AssistantDrawsRequest(AnalyzeDrawsRequest):
    draws: list[dict] = Field(default_factory=list, max_length=300)
    use_gemini: bool = False


@app.on_event("startup")
def startup():
    storage.initialize()


@app.get("/api/v1/health")
def health():
    return {
        "status": "ok",
        "app": "Lotomaster",
        "version": app.version,
        "official_results_source": "API pública da CAIXA",
        "official_results_transport": "Cloudflare Worker (proxy somente leitura)",
        "caixa_proxy_url": BASE_URL,
        "frontend_auto_refresh_minutes": 5,
    }


@app.get("/api/v1/lotteries")
def lotteries():
    return {"items": public_catalog(), "count": len(public_catalog())}


@app.get("/api/v1/lotofacil/combination-count")
def lotofacil_combination_count(
    pick_count: StrictInt = Query(...),
    fixed_count: StrictInt = Query(...),
    removed_count: StrictInt = Query(...),
):
    """Contar combinações possíveis sem gerar nem persistir jogos."""
    try:
        return count_lotofacil_combinations(pick_count, fixed_count, removed_count)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.post("/api/v1/lotofacil/history-number-search")
def lotofacil_history_number_search(request: HistoryNumberSearchRequest):
    """Pesquisar por inclusão, igualdade exata ou exclusão em histórico enviado pelo cliente."""
    try:
        return search_lotofacil_history(request.numbers, request.draws, request.match_mode)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.get("/api/v1/{game}/latest")
def game_latest(game: str):
    try:
        spec = get_spec(game)
        return latest_result(spec["key"])
    except KeyError:
        raise HTTPException(status_code=404, detail="Modalidade não encontrada.")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.get("/api/v1/{game}/results")
def game_results(game: str, limit: int = Query(default=20, ge=1, le=300)):
    try:
        spec = get_spec(game)
        items = list_results(spec["key"], limit=limit)
        warning = next((item.get("warning") for item in items if item.get("warning")), None)
        newest_item = max(items, key=lambda item: int(item["contest"]), default={})
        source = newest_item.get("source")
        checked_at = newest_item.get("_latest_checked_at") if not warning else None
        fresh = source == "CAIXA via Cloudflare Worker" or (source == "cache" and bool(checked_at))
        if not fresh and not warning:
            warning = "Último concurso obtido do cache do servidor ou de origem não informada; pode estar desatualizado."
        newest = max((int(item.get("_known_latest_contest", item["contest"])) for item in items), default=0)
        expected = min(limit, newest)
        present = {int(item["contest"]) for item in items if int(item["contest"]) > newest - expected}
        return {"game": spec["key"], "name": spec["name"], "items": items, "count": len(items), "source": "CAIXA via Worker e cache do servidor", "expected_count": expected, "partial": len(present) < expected, "provenance": {"latest_lookup": "server_fetch" if source == "CAIXA via Cloudflare Worker" else "server_cache" if source == "cache" else "unknown", "recently_checked": fresh, "verified": False, **({"last_successful_lookup_at": checked_at} if checked_at else {})}, **({"warning": warning} if warning else {})}
    except KeyError:
        raise HTTPException(status_code=404, detail="Modalidade não encontrada.")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.get("/api/v1/{game}/history")
def game_history(
    game: str,
    limit: int = Query(default=100, ge=1, le=100),
    before: int | None = Query(default=None, ge=1),
):
    """Paginated full CAIXA archive; ``before`` is an exclusive contest cursor."""
    try:
        spec = get_spec(game)
        page = list_history_page(spec["key"], limit=limit, before=before)
        return {"game": spec["key"], "name": spec["name"], "source": "CAIXA via Worker e cache do servidor", **page}
    except KeyError:
        raise HTTPException(status_code=404, detail="Modalidade não encontrada.")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.post("/api/v1/{game}/statistics/from-draws")
def game_statistics_from_draws(game: str, request: AnalyzeDrawsRequest):
    try:
        spec = get_spec(game)
        if not request.draws or len(request.draws) > MAX_DRAWS:
            raise HTTPException(status_code=422, detail=f"Informe de 1 a {MAX_DRAWS} concursos para análise.")
        draws = validate_draws(spec["key"], request.draws, require_game=True)
        report = analyze_draws(spec["key"], draws)
        return {**report, "provenance": {"kind": "client_supplied", "verified": False, "description": "Concursos fornecidos pelo cliente; o servidor não verificou sua origem nem autenticidade."}}
    except KeyError:
        raise HTTPException(status_code=404, detail="Modalidade não encontrada.")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.get("/api/v1/{game}/statistics")
def game_statistics(
    game: str,
    limit: int = Query(default=50, ge=1, le=300),
    table: str | None = None,
):
    try:
        spec = get_spec(game)
        draws = list_results(spec["key"], limit=limit)
        report = analyze_draws(spec["key"], draws)
        warning = next((draw.get("warning") for draw in draws if draw.get("warning")), None)
        if warning:
            report["warning"] = warning
        newest = max((int(draw.get("_known_latest_contest", draw["contest"])) for draw in draws), default=0)
        expected = min(limit, newest)
        present = {int(draw["contest"]) for draw in draws if int(draw["contest"]) > newest - expected}
        report.update({"expected_count": expected, "partial": len(present) < expected})
        if table:
            selected = report["tables"].get(table)
            if selected is None:
                raise HTTPException(status_code=404, detail="Tabela estatística não encontrada para esta modalidade.")
            return {"game": spec["key"], "game_name": spec["name"], "draws_analyzed": report["draws_analyzed"], "table": table, "result": selected, "disclaimer": report["disclaimer"], "expected_count": expected, "partial": report["partial"], **({"warning": warning} if warning else {})}
        return report
    except KeyError:
        raise HTTPException(status_code=404, detail="Modalidade não encontrada.")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.get("/api/v1/{game}/assistant")
def game_assistant(
    game: str,
    http_request: Request,
    limit: int = Query(default=50, ge=1, le=300),
    use_gemini: bool = False,
):
    if use_gemini:
        authorize_server_gemini_request(http_request)
    try:
        spec = get_spec(game)
        draws = list_results(spec["key"], limit=limit)
        report = build_assistant_report(spec["key"], draws, use_gemini=use_gemini)
        warning = next((draw.get("warning") for draw in draws if draw.get("warning")), None)
        newest = max((int(draw.get("_known_latest_contest", draw["contest"])) for draw in draws), default=0)
        expected = min(limit, newest)
        present = {int(draw["contest"]) for draw in draws if int(draw["contest"]) > newest - expected}
        latest = max(draws, key=lambda draw: int(draw["contest"]), default={})
        source = latest.get("source") or "origem não informada"
        if source == "cache" and not warning:
            warning = "Último concurso obtido do cache do servidor; pode estar desatualizado."
        report.update({"expected_count": expected, "partial": not draws or len(present) < expected, "source": source})
        if warning:
            report["warning"] = warning
        return report
    except KeyError:
        raise HTTPException(status_code=404, detail="Modalidade não encontrada.")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.post("/api/v1/{game}/assistant/from-draws")
def game_assistant_from_draws(game: str, http_request: Request, request: AssistantDrawsRequest):
    if request.use_gemini:
        authorize_server_gemini_request(http_request)
    try:
        spec = get_spec(game)
        if not request.draws or len(request.draws) > 300:
            raise HTTPException(status_code=422, detail="Informe de 1 a 300 concursos para análise.")
        draws = validate_draws(spec["key"], request.draws, require_game=True, max_draws=300)
        report = build_assistant_report(spec["key"], draws, use_gemini=request.use_gemini)
        return {**report, "provenance": {"kind": "client_supplied", "verified": False, "description": "Concursos fornecidos pelo cliente; o servidor não verificou sua origem nem autenticidade."}}
    except KeyError:
        raise HTTPException(status_code=404, detail="Modalidade não encontrada.")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.post("/api/v1/{game}/generate")
def game_generate(game: str, request: GenerateRequest):
    try:
        spec = get_spec(game)
        options = request.model_dump(exclude_none=True) if hasattr(request, "model_dump") else request.dict(exclude_none=True)
        pareto_details = pareto_filter_data(spec["key"], storage.list_draws(spec["key"], 1000)) if request.pareto else None
        if pareto_details is not None:
            options["_pareto_details"] = pareto_details
        games = generate_tickets(spec["key"], options)
        method = "amostragem ponderada manual sem reposição" if request.weights else "aleatório com fixos, removidos e filtros opcionais"
        response = {"game": spec["key"], "game_name": spec["name"], "items": games, "count": len(games), "method": method, "disclaimer": "Filtros e pesos são escolhas estruturais de seleção, não previsões, e não alteram a chance matemática de cada jogo no sorteio."}
        if pareto_details is not None:
            response["pareto"] = {key: value for key, value in pareto_details.items() if key != "numbers"}
            response["pareto"]["selected_numbers"] = pareto_details["numbers"]
            response["pareto"]["scope"] = "Até os 1.000 concursos mais recentes presentes no cache local desta modalidade; a regra seleciona dezenas em ordem de frequência decrescente, desempate crescente, até acumular 80% das aparições observadas."
        return response
    except KeyError:
        raise HTTPException(status_code=404, detail="Modalidade não encontrada.")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/v1/{game}/closures/exhaustive")
def game_exhaustive_closure(game: str, request: ClosureRequest):
    """Enumerate one bounded page and diagnose all filters locally."""
    try:
        spec = get_spec(game)
        repeat_filter = any(request.filters.get(key) not in (None, "") for key in ("min_repeated", "max_repeated"))
        reference = None
        if repeat_filter:
            if request.reference_contest is None:
                raise ValueError("Filtros de repetidas exigem um concurso de referência explícito")
            reference = _reference_draw(spec["key"], request.reference_contest)
        result = exhaustive_closure(
            spec["key"], request.pool, request.pick_count, request.fixed,
            filters=request.filters,
            reference_draw=reference.get("numbers") if reference else None,
            offset=request.offset,
            page_size=request.page_size,
        )
        if reference:
            result["reference_contest"] = reference["contest"]
        return result
    except KeyError:
        raise HTTPException(status_code=404, detail="Modalidade não encontrada.")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Não foi possível consultar o concurso de referência: {exc}")


@app.post("/api/v1/lotofacil/closures/repeated")
def lotofacil_repeated_closure(request: RepeatedClosureRequest):
    """Desdobrar repetidas localmente; busca CAIXA apenas se um filtro pedir referência explícita."""
    try:
        repeat_filter = any(request.filters.get(key) not in (None, "") for key in ("min_repeated", "max_repeated"))
        reference = None
        if repeat_filter:
            if request.reference_contest is None:
                raise ValueError("Filtros de repetidas exigem um concurso de referência explícito")
            reference = _reference_draw("lotofacil", request.reference_contest)
        result = repeated_closure(
            request.previous_draw, request.repeated,
            filters=request.filters,
            reference_draw=reference.get("numbers") if reference else None,
            offset=request.offset,
            page_size=request.page_size,
        )
        if reference:
            result["reference_contest"] = reference["contest"]
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Não foi possível consultar o concurso de referência: {exc}")


def _reference_draw(game: str, contest: int) -> dict:
    draw = storage.get_draw(game, contest) or fetch_draw(game, contest)
    if int(draw.get("contest", 0)) != contest:
        raise ValueError("O concurso retornado não corresponde à referência solicitada")
    return draw


@app.post("/api/v1/{game}/simulate")
def game_simulate(game: str, request: SimulateRequest):
    try:
        spec = get_spec(game)
        if not 1 <= len(request.tickets) <= 500:
            raise HTTPException(status_code=422, detail="Informe de 1 a 500 jogos para conferir.")
        if request.draw is not None:
            draw = request.draw
            provenance = {"kind": "client_supplied", "verified": False, "description": "Resultado fornecido pelo cliente; o servidor não verificou sua origem nem autenticidade."}
            validate_client_draws(spec["key"], [draw], require_special=True)
        elif request.contest is not None:
            draw = storage.get_draw(spec["key"], request.contest)
            if draw:
                provenance = {"kind": "server_cache", "verified": False, "description": "Resultado do cache do servidor; não foi atualizado nesta conferência."}
            else:
                draw = fetch_draw(spec["key"], request.contest)
                validate_draw(spec["key"], draw, require_game=True, require_special=True)
                storage.save_draw(draw)
                provenance = {"kind": "server_fetch", "verified": False, "description": "Resultado consultado pelo servidor via Worker; confirme na CAIXA."}
        else:
            draw = latest_result(spec["key"])
            if draw.get("source") == "cache":
                provenance = {"kind": "server_cache", "verified": False, "description": "Resultado do cache do servidor; pode estar desatualizado."}
            elif draw.get("source") == "CAIXA via Cloudflare Worker":
                provenance = {"kind": "server_fetch", "verified": False, "description": "Resultado consultado pelo servidor via Worker; confirme na CAIXA."}
            else:
                provenance = {"kind": "unknown", "verified": False, "description": "Origem do resultado não informada; confirme na CAIXA."}
        # Validate every source, including old cache entries, before checking awards.
        draw = {**draw, **validate_draw(spec["key"], draw, require_game=True, require_special=True)}
        tickets = [item.model_dump(exclude_none=True) if hasattr(item, "model_dump") else item.dict(exclude_none=True) for item in request.tickets]
        results = simulate_tickets(spec["key"], tickets, draw)
        return {"game": spec["key"], "game_name": spec["name"], "contest": draw.get("contest"), "draw_date": draw.get("draw_date"), "draw": draw, "results": results, "count": len(results), "provenance": provenance}
    except KeyError:
        raise HTTPException(status_code=404, detail="Modalidade não encontrada.")
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.post("/api/v1/{game}/simulate/history")
def game_simulate_history(game: str, request: HistorySimulateRequest):
    """Conferir histórico normalizado enviado pelo cliente; não busca nem persiste concursos."""
    try:
        spec = get_spec(game)
        validate_client_draws(spec["key"], request.draws, require_game=False, require_special=True, limit=5000)
        tickets = [item.model_dump(exclude_none=True) if hasattr(item, "model_dump") else item.dict(exclude_none=True) for item in request.tickets]
        report = simulate_ticket_history(spec["key"], tickets, request.draws)
        provenance = {"kind": "client_supplied", "verified": False, "description": "Concursos fornecidos pelo cliente; o servidor não verificou sua origem nem autenticidade."}
        return {"game": spec["key"], "game_name": spec["name"], **report, "provenance": provenance, "draw_origin": "client_submitted", "origin_verified": False}
    except KeyError:
        raise HTTPException(status_code=404, detail="Modalidade não encontrada.")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.get("/api/v1/{game}/probability")
def game_probability(
    game: str,
    pick_count: int | None = Query(default=None, ge=1, le=100),
    trevo_count: int = Query(default=2, ge=2, le=6),
    column_picks: list[int] | None = Query(default=None),
):
    try:
        spec = get_spec(game)
        if column_picks is not None and spec["key"] != "supersete":
            raise ValueError("column_picks está disponível somente para o Super Sete.")
        result = ticket_probability(spec["key"], pick_count, trevo_count, column_picks)
        return {"game": spec["key"], "game_name": spec["name"], **result, "disclaimer": "Cálculo combinatório teórico; cada sorteio é aleatório e independente."}
    except KeyError:
        raise HTTPException(status_code=404, detail="Modalidade não encontrada.")
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.get("/api/v1/{game}/export.csv")
def game_export(game: str, limit: int = Query(default=100, ge=1, le=300)):
    try:
        spec = get_spec(game)
        draws = list_results(spec["key"], limit=limit)
    except KeyError:
        raise HTTPException(status_code=404, detail="Modalidade não encontrada.")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    stream = StringIO()
    writer = csv.writer(stream)
    writer.writerow(["Concurso", "Data", "Dezenas", "Segundo sorteio", "Trevos", "Mês da Sorte", "Time do Coração"])
    for draw in draws:
        writer.writerow([
            draw.get("contest"), draw.get("draw_date"), " ".join(map(str, draw.get("numbers", []))),
            " ".join(map(str, draw.get("second_numbers", []))), " ".join(map(str, draw.get("trevos", []))),
            (draw.get("month") or {}).get("name", ""), draw.get("team") or "",
        ])
    filename = f"lotomaster-{spec['key']}-resultados.csv"
    return Response(stream.getvalue(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@app.get("/api/v1/{game}/export.txt")
def game_export_txt(game: str, limit: int = Query(default=100, ge=1, le=300)):
    try:
        spec = get_spec(game)
        draws = list_results(spec["key"], limit=limit)
    except KeyError:
        raise HTTPException(status_code=404, detail="Modalidade não encontrada.")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    lines = [f"Resultados de {spec['name']} — fonte pública CAIXA", ""]
    for draw in draws:
        lines.append(f"Concurso {draw.get('contest')} · {draw.get('draw_date') or 'data indisponível'}")
        lines.append("Dezenas: " + " ".join(map(str, draw.get("numbers", []))))
        if draw.get("second_numbers"):
            lines.append("2º sorteio: " + " ".join(map(str, draw["second_numbers"])))
        if draw.get("trevos"):
            lines.append("Trevos: " + " ".join(map(str, draw["trevos"])))
        if draw.get("month"):
            lines.append("Mês da Sorte: " + str(draw["month"].get("name") or ""))
        if draw.get("team"):
            lines.append("Time do Coração: " + str(draw["team"]))
        lines.append("")
    filename = f"lotomaster-{spec['key']}-resultados.txt"
    return Response("\n".join(lines), media_type="text/plain; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


def _xlsx_cell(reference: str, value) -> str:
    if isinstance(value, int) and not isinstance(value, bool):
        return f'<c r="{reference}"><v>{value}</v></c>'
    text = escape("" if value is None else str(value))
    preserve = ' xml:space="preserve"' if text[:1].isspace() or text[-1:].isspace() else ""
    return f'<c r="{reference}" t="inlineStr"><is><t{preserve}>{text}</t></is></c>'


def _xlsx_results(draws: list[dict]) -> bytes:
    """Create a minimal standards-compliant XLSX using only the Python stdlib."""
    columns = ["A", "B", "C", "D", "E", "F", "G"]
    matrix = [["Concurso", "Data", "Dezenas", "Segundo sorteio", "Trevos", "Mês da Sorte", "Time do Coração"]]
    matrix.extend([
        [
            draw.get("contest"), draw.get("draw_date"), " ".join(map(str, draw.get("numbers", []))),
            " ".join(map(str, draw.get("second_numbers", []))), " ".join(map(str, draw.get("trevos", []))),
            (draw.get("month") or {}).get("name", ""), draw.get("team") or "",
        ]
        for draw in draws
    ])
    sheet_rows = []
    for row_index, row in enumerate(matrix, 1):
        cells = "".join(_xlsx_cell(f"{column}{row_index}", value) for column, value in zip(columns, row))
        sheet_rows.append(f'<row r="{row_index}">{cells}</row>')
    worksheet = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(sheet_rows)}</sheetData></worksheet>')
    workbook = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Resultados" sheetId="1" r:id="rId1"/></sheets></workbook>')
    content_types = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '</Types>')
    package_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        '</Relationships>')
    workbook_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        '</Relationships>')
    from io import BytesIO
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", package_rels)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        archive.writestr("xl/worksheets/sheet1.xml", worksheet)
    return buffer.getvalue()


@app.get("/api/v1/{game}/export.xlsx")
def game_export_xlsx(game: str, limit: int = Query(default=100, ge=1, le=300)):
    try:
        spec = get_spec(game)
        draws = list_results(spec["key"], limit=limit)
    except KeyError:
        raise HTTPException(status_code=404, detail="Modalidade não encontrada.")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    filename = f"lotomaster-{spec['key']}-resultados.xlsx"
    return Response(
        _xlsx_results(draws),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/v1/{game}/tools")
def game_tools(game: str):
    try:
        spec = get_spec(game)
    except KeyError:
        raise HTTPException(status_code=404, detail="Modalidade não encontrada.")
    tools = [
        {"id": "generator", "name": "Gerador de jogos", "available": True},
        {"id": "simulator", "name": "Testar jogo / múltiplos jogos", "available": True},
        {"id": "import", "name": "Importar jogos por texto", "available": True},
        {"id": "probability", "name": "Calculadora de probabilidades", "available": True},
        {"id": "statistics", "name": "Tabelas e estatísticas", "available": True},
        {"id": "export", "name": "Exportar histórico CSV/TXT/Excel", "available": True},
        {"id": "closures", "name": "Desdobramento exaustivo paginado", "available": spec["key"] != "supersete" and spec.get("bonus") is None, "note": "Até 1.000 combinações por página, com diagnóstico local dos filtros; modalidades com bônus ou colunas ainda não são suportadas."},
    ]
    if spec["key"] == "lotofacil":
        tools.append({"id": "repeated_closure", "name": "Desdobramento completo de repetidas", "available": True, "note": "Enumeração combinatória local a partir das repetidas escolhidas; não é fechamento proprietário nem garantia de prêmio."})
    if spec["key"] == "lotomania":
        tools.append({"id": "quadrants", "name": "Gerador com quadrantes", "available": True, "note": "Quatro blocos 5×5 na grade 10×10 (linhas/colunas 0–4 e 5–9); filtros estruturais, não previsões."})
    return {"game": spec["key"], "tools": tools}


@app.get("/api/v1/{game}/profile")
def game_profile(game: str):
    try:
        return public_spec(get_spec(game))
    except KeyError:
        raise HTTPException(status_code=404, detail="Modalidade não encontrada.")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")


if STATIC.exists():
    app.mount("/assets", StaticFiles(directory=STATIC), name="assets")


@app.get("/{path:path}", include_in_schema=False)
def frontend_fallback(path: str):
    if path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Endpoint não encontrado.")
    return FileResponse(STATIC / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("lotomaster.api:app", host="0.0.0.0", port=8020, reload=False)
