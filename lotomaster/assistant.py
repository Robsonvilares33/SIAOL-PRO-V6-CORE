"""Análise explicável do histórico; nenhum padrão é tratado como preditor."""
import json
import os

import requests

from .analytics import analyze_draws
from .catalog import get_spec

_GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def _local_commentary(spec: dict, analysis: dict) -> str:
    draws = int(analysis.get("draws_analyzed", 0))
    if not draws:
        return (
            f"Ainda não há concursos carregados para {spec['name']}. "
            "A seleção de jogos deve permanecer aleatória: este serviço não prevê sorteios."
        )
    frequency = analysis.get("frequency", [])
    frequent = frequency[:3]
    rare = sorted(frequency, key=lambda row: (row.get("count", 0), row.get("number", 0)))[:3]
    frequent_text = ", ".join(f"{row['number']:02d} ({row['count']})" for row in frequent) or "indisponível"
    rare_text = ", ".join(f"{row['number']:02d} ({row['count']})" for row in rare) or "indisponível"
    return (
        f"Nos {draws} concursos deste recorte de {spec['name']}, as maiores contagens observadas "
        f"foram {frequent_text}; as menores, {rare_text}. São descrições retrospectivas, "
        "não probabilidades calibradas nem indicação de maior ou menor chance no próximo sorteio. "
        "Em sorteios justos e independentes, o histórico não altera as chances teóricas."
    )


def _gemini_commentary(spec: dict, analysis: dict, local_commentary: str) -> tuple[str, str | None, str]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return local_commentary, None, "not_configured"

    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    compact = {
        "game": spec["name"],
        "draws_analyzed": analysis.get("draws_analyzed", 0),
        "latest_contest": analysis.get("latest_contest"),
        "historical_top_frequencies": analysis.get("frequency", [])[:10],
        "historical_low_frequencies": sorted(
            analysis.get("frequency", []),
            key=lambda row: (row.get("count", 0), row.get("number", 0)),
        )[:10],
        "parity_distribution": analysis.get("parity_distribution", [])[:8],
        "sum_summary": analysis.get("sum", {}),
        "theoretical_probability_note": (
            "Only exact combinatorial odds may be described as probabilities;"
            " historical frequencies are not calibrated future probabilities."
        ),
    }
    system_instruction = (
        "You are an explanatory statistics assistant inside a Brazilian lottery-results website. "
        "Use only the supplied historical summary. Describe what was observed, not what will happen. "
        "Never recommend hot/cold/overdue numbers, never claim patterns predict or change future draws, "
        "never call a score a probability, and never promise a winning ticket. "
        "Explicitly say that each eligible combination has the same theoretical chance under a fair "
        "independent draw. Answer in concise Brazilian Portuguese, with no betting encouragement."
    )
    try:
        response = requests.post(
            _GEMINI_URL.format(model=model),
            headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
            json={
                "systemInstruction": {"parts": [{"text": system_instruction}]},
                "contents": [{"role": "user", "parts": [{"text": json.dumps(compact, ensure_ascii=False)}]}],
                "generationConfig": {"temperature": 0.1, "maxOutputTokens": 450},
            },
            timeout=18,
        )
        response.raise_for_status()
        payload = response.json()
        parts = payload.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        text = " ".join(part.get("text", "").strip() for part in parts if part.get("text", "").strip())
        if not text:
            raise ValueError("O modelo não retornou uma análise textual.")
        # A ressalva é sempre anexada pelo servidor, mesmo com uma resposta generativa.
        return text, model, "available"
    except Exception:
        # Não derruba a consulta de dados quando o provedor de IA está indisponível.
        return local_commentary, model, "temporarily_unavailable"


def build_assistant_report(game: str, draws: list[dict], use_gemini: bool = True) -> dict:
    spec = get_spec(game)
    analysis = analyze_draws(spec["key"], draws)
    local_commentary = _local_commentary(spec, analysis)
    if use_gemini:
        commentary, model, ai_status = _gemini_commentary(spec, analysis, local_commentary)
    else:
        commentary, model, ai_status = local_commentary, None, "local_only"

    return {
        "game": spec["key"],
        "game_name": spec["name"],
        "draws_analyzed": analysis["draws_analyzed"],
        "latest_contest": analysis["latest_contest"],
        "historical_summary": {
            "most_frequent": analysis["frequency"][:10],
            "least_frequent": sorted(
                analysis["frequency"],
                key=lambda row: (row.get("count", 0), row.get("number", 0)),
            )[:10],
            "parity_distribution": analysis["parity_distribution"],
            "sum": analysis["sum"],
        },
        "commentary": commentary,
        "ai": {
            "status": ai_status,
            "provider": "Google Gemini" if ai_status == "available" else "análise local explicável",
            "model": model,
        },
        "selection_policy": "uniform_random",
        "probabilities_calibrated_out_of_sample": False,
        "disclaimer": (
            "Frequências, atrasos e padrões descrevem somente o histórico consultado; "
            "não são probabilidades futuras nem aumentam a chance de uma combinação. "
            "A geração de jogos é aleatória e não promete prêmio."
        ),
    }
