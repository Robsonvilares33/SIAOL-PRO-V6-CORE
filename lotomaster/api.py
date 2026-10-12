"""API e aplicação web Lotomaster. Execute com: uvicorn lotomaster.api:app --port 8020."""
import csv
from io import StringIO
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import storage
from .analytics import analyze_draws
from .assistant import build_assistant_report
from .caixa import BASE_URL, fetch_draw
from .catalog import get_spec, public_catalog, public_spec
from .engine import generate_tickets, latest_result, list_results, simulate_tickets, ticket_probability

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"

app = FastAPI(
    title="Lotomaster — Estatísticas e Jogos",
    description="Resultados oficiais da CAIXA, gerador, simulador e estatísticas históricas.",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url=None,
)


class GenerateRequest(BaseModel):
    count: int = 1
    pick_count: int | None = None
    fixed: list[int] = Field(default_factory=list)
    excluded: list[int] = Field(default_factory=list)
    bonus: dict = Field(default_factory=dict)
    filters: dict = Field(default_factory=dict)
    columns: dict = Field(default_factory=dict)
    seed: int | None = None


class Ticket(BaseModel):
    numbers: list[int] = Field(default_factory=list)
    columns: list[list[int]] | None = None
    bonus: dict = Field(default_factory=dict)
    ticket_number: int | None = None


class SimulateRequest(BaseModel):
    tickets: list[Ticket] = Field(default_factory=list)
    contest: int | None = None
    draw: dict | None = None


class AnalyzeDrawsRequest(BaseModel):
    draws: list[dict] = Field(default_factory=list)


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
        return {"game": spec["key"], "name": spec["name"], "items": items, "count": len(items), "source": "CAIXA + cache local"}
    except KeyError:
        raise HTTPException(status_code=404, detail="Modalidade não encontrada.")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.post("/api/v1/{game}/statistics/from-draws")
def game_statistics_from_draws(game: str, request: AnalyzeDrawsRequest):
    try:
        spec = get_spec(game)
        if not request.draws or len(request.draws) > 300:
            raise HTTPException(status_code=422, detail="Informe de 1 a 300 concursos para análise.")
        if any(draw.get("game") != spec["key"] for draw in request.draws):
            raise HTTPException(status_code=422, detail="Todos os concursos precisam ser da mesma modalidade.")
        return analyze_draws(spec["key"], request.draws)
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
        if table:
            selected = report["tables"].get(table)
            if selected is None:
                raise HTTPException(status_code=404, detail="Tabela estatística não encontrada para esta modalidade.")
            return {"game": spec["key"], "game_name": spec["name"], "draws_analyzed": report["draws_analyzed"], "table": table, "result": selected, "disclaimer": report["disclaimer"]}
        return report
    except KeyError:
        raise HTTPException(status_code=404, detail="Modalidade não encontrada.")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.get("/api/v1/{game}/assistant")
def game_assistant(game: str, limit: int = Query(default=50, ge=1, le=300), use_gemini: bool = True):
    try:
        spec = get_spec(game)
        draws = list_results(spec["key"], limit=limit)
        return build_assistant_report(spec["key"], draws, use_gemini=use_gemini)
    except KeyError:
        raise HTTPException(status_code=404, detail="Modalidade não encontrada.")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.post("/api/v1/{game}/assistant/from-draws")
def game_assistant_from_draws(game: str, request: AnalyzeDrawsRequest):
    try:
        spec = get_spec(game)
        if not request.draws or len(request.draws) > 300:
            raise HTTPException(status_code=422, detail="Informe de 1 a 300 concursos para análise.")
        if any(draw.get("game") != spec["key"] for draw in request.draws):
            raise HTTPException(status_code=422, detail="Todos os concursos precisam ser da mesma modalidade.")
        return build_assistant_report(spec["key"], request.draws)
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
        games = generate_tickets(spec["key"], request.model_dump(exclude_none=True) if hasattr(request, "model_dump") else request.dict(exclude_none=True))
        return {"game": spec["key"], "game_name": spec["name"], "items": games, "count": len(games), "method": "aleatório com fixos, removidos e filtros opcionais", "disclaimer": "Filtros e frequências históricas não aumentam a chance matemática de sorteio."}
    except KeyError:
        raise HTTPException(status_code=404, detail="Modalidade não encontrada.")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/v1/{game}/simulate")
def game_simulate(game: str, request: SimulateRequest):
    try:
        spec = get_spec(game)
        if not request.tickets:
            raise HTTPException(status_code=422, detail="Informe ao menos um jogo para conferir.")
        if request.draw is not None:
            draw = request.draw
            if draw.get("game") != spec["key"] or not draw.get("contest") or not draw.get("numbers"):
                raise HTTPException(status_code=422, detail="O resultado informado não corresponde à modalidade ou está incompleto.")
        elif request.contest:
            draw = storage.get_draw(spec["key"], request.contest)
            if not draw:
                draw = fetch_draw(spec["key"], request.contest)
                storage.save_draw(draw)
        else:
            draw = latest_result(spec["key"])
        tickets = [item.model_dump(exclude_none=True) if hasattr(item, "model_dump") else item.dict(exclude_none=True) for item in request.tickets]
        results = simulate_tickets(spec["key"], tickets, draw)
        return {"game": spec["key"], "game_name": spec["name"], "contest": draw.get("contest"), "draw_date": draw.get("draw_date"), "draw": draw, "results": results, "count": len(results)}
    except KeyError:
        raise HTTPException(status_code=404, detail="Modalidade não encontrada.")
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.get("/api/v1/{game}/probability")
def game_probability(game: str, pick_count: int | None = Query(default=None, ge=1, le=100), trevo_count: int = Query(default=2, ge=2, le=6)):
    try:
        spec = get_spec(game)
        result = ticket_probability(spec["key"], pick_count, trevo_count)
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
        {"id": "export", "name": "Exportar histórico CSV/TXT", "available": True},
        {"id": "closures", "name": "Desdobramentos/fechamentos", "available": False, "note": "Não ativado nesta primeira entrega; fechamento exaustivo pode gerar milhões de combinações."},
    ]
    if spec["key"] == "lotomania":
        tools.append({"id": "quadrants", "name": "Gerador com quadrantes", "available": True})
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
