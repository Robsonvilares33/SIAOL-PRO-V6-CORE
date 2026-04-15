"""
SIAOL-PRO v11.1 - MAIN ORCHESTRATOR "Quantum DNA"
Orquestrador principal do ciclo autônomo, integrando:
- Motor Anti-Sycophancy (v11.0)
- Cadeia de Pensamento Profunda / CoT (v11.0)
- Visão Computacional / Playwright Vision (v11.1)
- Mapa de Calor de Teses / Thesis Heatmap (v11.1)
- Preferência por Números Pares no ML Engine (v11.1)
"""
import os
import sys
import json
from datetime import datetime
from dotenv import load_dotenv

# Adicionar o diretório do projeto ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Importar módulos v11.0
from anti_sycophancy_engine import AntiSycophancyEngine
from llama_bridge import LlamaBridge

# Importar novos módulos v11.1
from playwright_vision import PlaywrightVisionEngine
from thesis_heatmap import ThesisHeatmapEngine

# Importar motor de ML atualizado
from ml_engine import (
    LOTTERY_CONFIG,
    fetch_historical_data,
    generate_prediction,
    analyze_frequency,
    analyze_gaps,
    analyze_even_odd,
    analyze_sum_distribution,
    analyze_sequences,
    analyze_quadrants,
    analyze_trends,
    log_to_supabase
)

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


class MainOrchestratorV11:
    """Orquestra o ciclo autônomo do SIAOL-PRO v11.1 'Quantum DNA'."""

    def __init__(self):
        self.session_id = datetime.now().isoformat()
        print(f"\n{'='*60}")
        print(f"  SIAOL-PRO v11.1 'Quantum DNA' - ORCHESTRATOR")
        print(f"  Sessão: {self.session_id}")
        print(f"{'='*60}\n")

        # Inicializar módulos v11.0
        self.anti_sycophancy_engine = AntiSycophancyEngine()
        self.llama_bridge = LlamaBridge()

        # Inicializar módulos v11.1
        self.vision_engine = PlaywrightVisionEngine()
        self.heatmap_engine = ThesisHeatmapEngine()

    def run_cycle(self, lottery_type, num_games=5, even_preference_weight=0.2):
        """Executa um ciclo completo de predição para uma loteria."""
        config = LOTTERY_CONFIG.get(lottery_type)
        if not config:
            print(f"[ERRO] Tipo de loteria desconhecido: {lottery_type}")
            return None

        print(f"\n{'='*60}")
        print(f"  CICLO AUTÔNOMO - {config['name'].upper()}")
        print(f"{'='*60}")

        # ============================================================
        # FASE 1: COLETA DE DADOS HISTÓRICOS
        # ============================================================
        print(f"\n[FASE 1] Coletando dados históricos para {config['name']}...")
        historical_data = fetch_historical_data(lottery_type, limit=500, config=config)
        if not historical_data:
            print(f"[ERRO] Não foi possível obter dados históricos para {lottery_type}")
            log_to_supabase(f"Falha na coleta de dados para {lottery_type}", "ERROR")
            return None
        print(f"[FASE 1] {len(historical_data)} sorteios coletados.")

        # ============================================================
        # FASE 2: VISÃO COMPUTACIONAL (Análise de Gráficos)
        # ============================================================
        print(f"\n[FASE 2] Executando análise de Visão Computacional...")
        portals = [
            f"https://www.caixa.gov.br/loterias/{lottery_type}/estatisticas",
            f"https://www.loterias.caixa.gov.br/wps/portal/loterias/landing/{lottery_type}"
        ]
        vision_insights = self.vision_engine.run_vision_analysis_cycle(lottery_type, portals)
        print(f"[FASE 2] Visão Computacional concluída. Confiança: {vision_insights.get('overall_confidence', 0):.2%}")

        # ============================================================
        # FASE 3: MAPA DE CALOR DE TESES
        # ============================================================
        print(f"\n[FASE 3] Gerando Mapa de Calor de Teses...")
        df_performance = self.heatmap_engine.analyze_teses_performance(lottery_type, historical_data)
        heatmap_report = self.heatmap_engine.generate_heatmap_report(df_performance)
        top_teses = self.heatmap_engine.get_top_teses(df_performance, top_n=3)
        print(heatmap_report)
        print(f"[FASE 3] Top Teses Recomendadas:")
        for t in top_teses:
            print(f"  - {t['id']}: {t['name']} ({t['recent_score']}%)")

        # ============================================================
        # FASE 4: PREDIÇÃO INICIAL (ML Engine com Preferência por Pares)
        # ============================================================
        print(f"\n[FASE 4] Gerando predição inicial com ML Engine (Pref. Pares: {even_preference_weight})...")
        initial_predictions = generate_prediction(
            lottery_type, historical_data, num_games=num_games,
            even_preference_weight=even_preference_weight
        )
        if not initial_predictions:
            print(f"[ERRO] ML Engine não gerou predições para {lottery_type}")
            log_to_supabase(f"Falha na geração de predições para {lottery_type}", "ERROR")
            return None

        print(f"[FASE 4] {len(initial_predictions)} jogos gerados pelo ML Engine.")
        for i, pred in enumerate(initial_predictions):
            even_count = sum(1 for n in pred if n % 2 == 0)
            print(f"  Jogo {i+1:02d}: {sorted(pred)} (Pares: {even_count}/{len(pred)})")

        # ============================================================
        # FASE 5: ANÁLISE ANTI-SYCOPHANCY
        # ============================================================
        print(f"\n[FASE 5] Executando análise Anti-Sycophancy...")
        # Usar a primeira predição como representativa para a análise
        representative_prediction = initial_predictions[0] if initial_predictions else []
        anti_syc_results = self.anti_sycophancy_engine.run_anti_sycophancy_check(
            lottery_type, representative_prediction, historical_data
        )
        print(f"[FASE 5] Anti-Sycophancy concluído.")
        if anti_syc_results:
            weaknesses = anti_syc_results.get("weaknesses", [])
            print(f"  Fraquezas encontradas: {len(weaknesses)}")
            for w in weaknesses:
                if isinstance(w, dict):
                    print(f"    - {w.get('type', 'N/A')}: {w.get('description', 'N/A')}")
                else:
                    print(f"    - {w}")

        # ============================================================
        # FASE 6: CADEIA DE PENSAMENTO PROFUNDA (CoT) com Llama
        # ============================================================
        print(f"\n[FASE 6] Executando Cadeia de Pensamento Profunda (CoT) com Llama...")
        llama_analysis = self.llama_bridge.analyze_patterns(
            lottery_type, historical_data, num_predictions=num_games
        )

        final_predictions = initial_predictions  # Fallback
        if llama_analysis and "final_recommended_games" in llama_analysis:
            final_predictions = llama_analysis["final_recommended_games"]
            print(f"[FASE 6] Llama CoT gerou {len(final_predictions)} jogos refinados.")
        else:
            print("[FASE 6] Llama não disponível. Usando predições do ML Engine.")

        # ============================================================
        # FASE 7: CONSOLIDAÇÃO E RELATÓRIO
        # ============================================================
        print(f"\n[FASE 7] Consolidando resultados...")

        cycle_report = {
            "session_id": self.session_id,
            "lottery_type": lottery_type,
            "lottery_name": config["name"],
            "timestamp": datetime.now().isoformat(),
            "draws_analyzed": len(historical_data),
            "vision_confidence": vision_insights.get("overall_confidence", 0),
            "top_teses": [{"id": t["id"], "name": t["name"], "score": t["recent_score"]} for t in top_teses],
            "even_preference_weight": even_preference_weight,
            "anti_sycophancy_weaknesses": len(anti_syc_results.get("weaknesses", [])) if anti_syc_results else 0,
            "initial_predictions": initial_predictions,
            "final_predictions": final_predictions,
        }

        # Salvar relatório localmente
        report_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"cycle_report_{lottery_type}.json")
        with open(report_path, 'w') as f:
            json.dump(cycle_report, f, indent=2, ensure_ascii=False)
        print(f"[FASE 7] Relatório do ciclo salvo em: {report_path}")

        # Salvar no Supabase
        log_to_supabase(
            f"Ciclo v11.1 concluído para {config['name']}. "
            f"Jogos: {len(final_predictions)}, "
            f"Pref. Pares: {even_preference_weight}, "
            f"Top Tese: {top_teses[0]['name'] if top_teses else 'N/A'}",
            "INFO"
        )

        print(f"\n{'='*60}")
        print(f"  CICLO CONCLUÍDO - {config['name'].upper()}")
        print(f"  Jogos Finais: {len(final_predictions)}")
        print(f"  Confiança Visual: {vision_insights.get('overall_confidence', 0):.2%}")
        print(f"  Top Tese: {top_teses[0]['name'] if top_teses else 'N/A'}")
        print(f"{'='*60}")

        return cycle_report


def main():
    """Ponto de entrada principal."""
    orchestrator = MainOrchestratorV11()

    # Executar ciclo para as loterias prioritárias
    lotteries_to_run = [
        {"type": "megasena", "games": 10, "even_pref": 0.2},
        {"type": "lotomania", "games": 20, "even_pref": 0.15},
        {"type": "quina", "games": 10, "even_pref": 0.2},
    ]

    all_reports = []
    for lottery in lotteries_to_run:
        report = orchestrator.run_cycle(
            lottery_type=lottery["type"],
            num_games=lottery["games"],
            even_preference_weight=lottery["even_pref"]
        )
        if report:
            all_reports.append(report)

    # Resumo final
    print(f"\n{'='*60}")
    print(f"  RESUMO GERAL DO CICLO v11.1")
    print(f"{'='*60}")
    for report in all_reports:
        print(f"  {report['lottery_name']}: {len(report['final_predictions'])} jogos gerados")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
