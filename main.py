"""
SIAOL-PRO v7.0 - Controlador Principal Autonomo Multi-Cerebro
Orquestra a coleta de dados, analise ML, analise por IA Multi-Cerebro
e predicoes otimizadas baseadas no calendario de sorteios brasileiros.

MOTORES:
  1. Motor Estatistico (frequencia, gaps, sequencias, quadrantes, tendencia)
  2. Motor IA Groq (LLaMA 3.3 70B - ultra-rapido)
  3. Motor IA Gemini (Google Gemini 2.0 Flash - backup inteligente)
  4. Motor de Consenso (cruza resultados de todas as IAs)

CALENDARIO DE SORTEIOS:
  Mega-Sena:  Terca, Quinta, Sabado
  Lotofacil:  Segunda a Sabado
  Quina:      Segunda a Sabado
  Lotomania:  Segunda, Quarta, Sexta

O sistema roda 1x ao dia (12:00 BRT) via GitHub Actions.
"""
import os
import sys
import json
import requests
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Timezone Brasil (UTC-3)
BR_TZ = timezone(timedelta(hours=-3))

# Calendario de sorteios por dia da semana (0=Segunda, 6=Domingo)
LOTTERY_SCHEDULE = {
    0: ["lotofacil", "quina", "lotomania"],           # Segunda
    1: ["lotofacil", "quina", "megasena"],             # Terca
    2: ["lotofacil", "quina", "lotomania"],            # Quarta
    3: ["lotofacil", "quina", "megasena"],             # Quinta
    4: ["lotofacil", "quina", "lotomania"],            # Sexta
    5: ["lotofacil", "quina", "megasena"],             # Sabado
    6: []                                              # Domingo - sem sorteio
}

DAY_NAMES = {
    0: "Segunda-feira",
    1: "Terca-feira",
    2: "Quarta-feira",
    3: "Quinta-feira",
    4: "Sexta-feira",
    5: "Sabado",
    6: "Domingo"
}


def log_to_supabase(message, level="INFO"):
    """Registra log no Supabase."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        print(f"[{level}] {message}")
        return
    url = f"{SUPABASE_URL}/rest/v1/system_logs"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }
    data = {
        "message": message,
        "log_level": level,
        "metadata": {"source": "main_v7", "timestamp": datetime.now(BR_TZ).isoformat()}
    }
    try:
        resp = requests.post(url, headers=headers, json=data, timeout=10)
        if resp.status_code != 201:
            print(f"Erro ao logar: {resp.status_code} - {resp.text}")
    except Exception as e:
        print(f"Erro ao logar: {e}")


def get_today_lotteries():
    """Retorna as loterias que tiveram sorteio no dia anterior."""
    now = datetime.now(BR_TZ)
    # Retrocede 1 dia (cron roda 12:00 do dia seguinte para dados estaveis)
    target_date = now - timedelta(days=1)
    weekday = target_date.weekday()

    lotteries = LOTTERY_SCHEDULE.get(weekday, [])
    return lotteries, DAY_NAMES.get(weekday, "Desconhecido"), now


def run_data_collection(lotteries):
    """Executa coleta de dados para as loterias do dia."""
    try:
        from data_collector import collect_recent_results
        results = {}
        for lottery in lotteries:
            print(f"  Coletando dados de {lottery}...")
            collected, errors = collect_recent_results(lottery, 5)
            results[lottery] = {"collected": collected, "errors": errors}
            print(f"    -> {collected} coletados, {errors} erros")
        return results
    except ImportError as e:
        print(f"Erro ao importar data_collector: {e}")
        log_to_supabase(f"Erro ao importar data_collector: {e}", "ERROR")
        return {}
    except Exception as e:
        print(f"Erro na coleta de dados: {e}")
        log_to_supabase(f"Erro na coleta de dados: {e}", "ERROR")
        return {}


def run_ml_analysis(lotteries):
    """Executa analise ML estatistica para as loterias do dia."""
    try:
        from ml_engine import run_analysis
        results = {}
        for lottery in lotteries:
            print(f"  Analisando {lottery}...")
            result = run_analysis(lottery)
            if result:
                results[lottery] = result
        return results
    except ImportError as e:
        print(f"Erro ao importar ml_engine: {e}")
        log_to_supabase(f"Erro ao importar ml_engine: {e}", "ERROR")
        return {}
    except Exception as e:
        print(f"Erro na analise ML: {e}")
        log_to_supabase(f"Erro na analise ML: {e}", "ERROR")
        return {}


def run_ai_multi_brain(lotteries, ml_results):
    """FASE 4: Analise por IA Multi-Cerebro (Groq + Gemini)."""
    try:
        from ai_brain import run_ai_analysis, enhance_predictions
        from ml_engine import save_predictions

        ai_results = {}
        for lottery in lotteries:
            ml_data = ml_results.get(lottery)
            if not ml_data:
                continue

            draws = ml_data.get("draws", [])
            stat_summary = ml_data.get("stat_summary", {})

            if len(draws) < 5:
                continue

            # Rodar analise IA
            consensus = run_ai_analysis(lottery, draws, stat_summary)

            if consensus:
                # Aprimorar predicoes base com insights da IA
                base_predictions = ml_data.get("predictions", [])
                enhanced = enhance_predictions(base_predictions, consensus, lottery)

                if enhanced:
                    save_predictions(lottery, enhanced, engine="SIAOL-PRO-v7-MultiAI")
                    print(f"  [v7] {len(enhanced)} predicoes APRIMORADAS por IA salvas para {lottery}")
                    for p in enhanced:
                        consensus_count = p.get("consensus_count", 0)
                        print(f"    Jogo {p['game_number']}: {p['numbers']} "
                              f"(consenso={consensus_count}, soma={p['sum']})")

                ai_results[lottery] = {
                    "consensus": consensus,
                    "enhanced_predictions": len(enhanced) if enhanced else 0,
                    "providers": consensus.get("providers_consulted", []),
                    "avg_confidence": consensus.get("avg_confidence", 0),
                }

        return ai_results

    except ImportError as e:
        print(f"  [v7] ai_brain nao disponivel: {e}")
        log_to_supabase(f"ai_brain nao disponivel: {e}", "WARN")
        return {}
    except Exception as e:
        print(f"  [v7] Erro na analise Multi-Cerebro: {e}")
        log_to_supabase(f"Erro na analise Multi-Cerebro: {e}", "ERROR")
        return {}


def run_autopsy(lotteries):
    """Executa autopsia semantica - compara predicoes anteriores com resultados reais."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return {}

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }

    results = {}
    for lottery in lotteries:
        try:
            # Buscar ultima predicao
            pred_url = (f"{SUPABASE_URL}/rest/v1/lottery_predictions"
                        f"?lottery_type=eq.{lottery}"
                        f"&order=created_at.desc"
                        f"&limit=10"
                        f"&select=predicted_numbers,confidence,metadata,created_at")
            pred_resp = requests.get(pred_url, headers=headers, timeout=10)

            # Buscar ultimo resultado real
            real_url = (f"{SUPABASE_URL}/rest/v1/lottery_data"
                        f"?lottery_type=eq.{lottery}"
                        f"&order=draw_number.desc"
                        f"&limit=1"
                        f"&select=numbers,draw_number")
            real_resp = requests.get(real_url, headers=headers, timeout=10)

            if pred_resp.status_code == 200 and real_resp.status_code == 200:
                predictions = pred_resp.json()
                real_data = real_resp.json()

                if predictions and real_data:
                    real_numbers = set(real_data[0].get("numbers", []))
                    best_match = 0
                    best_pred = None
                    for pred in predictions:
                        pred_numbers = set(pred.get("predicted_numbers", []))
                        match = len(real_numbers & pred_numbers)
                        if match > best_match:
                            best_match = match
                            best_pred = pred

                    engine_used = "unknown"
                    if best_pred and best_pred.get("metadata"):
                        engine_used = best_pred["metadata"].get("engine", "unknown")

                    results[lottery] = {
                        "best_match": best_match,
                        "total_numbers": len(real_numbers),
                        "accuracy_pct": round(best_match / max(len(real_numbers), 1) * 100, 1),
                        "engine": engine_used,
                    }
                    print(f"  Autopsia {lottery}: melhor match = {best_match}/{len(real_numbers)} "
                          f"({results[lottery]['accuracy_pct']}%) [Motor: {engine_used}]")
        except Exception as e:
            print(f"  Erro na autopsia de {lottery}: {e}")

    return results


def main():
    """Ciclo principal do SIAOL-PRO v7.0 Multi-Cerebro."""
    print("=" * 60)
    print("  SIAOL-PRO v7.0 - Motor Multi-Cerebro Autonomo")
    print("  Motores: Estatistico + Groq (LLaMA) + Gemini (Google)")
    print("=" * 60)

    # Detectar IAs disponiveis
    groq_ok = bool(os.getenv("GROQ_API_KEY"))
    gemini_ok = bool(os.getenv("GEMINI_API_KEY"))
    print(f"\n[CONFIG] Groq API: {'✓ Ativa' if groq_ok else '✗ Nao configurada'}")
    print(f"[CONFIG] Gemini API: {'✓ Ativa' if gemini_ok else '✗ Nao configurada'}")
    print(f"[CONFIG] Supabase: {'✓ Conectado' if SUPABASE_URL else '✗ Nao configurado'}")

    # Obter loterias do dia
    lotteries, day_name, now = get_today_lotteries()
    print(f"\nData/Hora (BR): {now.strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"Dia: {day_name}")
    print(f"Loterias do dia: {', '.join(lotteries) if lotteries else 'Nenhuma (Domingo)'}")

    log_to_supabase(
        f"SIAOL-PRO v7 Multi-Cerebro iniciado. Dia: {day_name}. "
        f"Loterias: {', '.join(lotteries) if lotteries else 'Nenhuma'}. "
        f"IAs: Groq={'ON' if groq_ok else 'OFF'}, Gemini={'ON' if gemini_ok else 'OFF'}."
    )

    if not lotteries:
        print("\nDomingo - sem sorteios. Executando manutencao...")
        log_to_supabase("Domingo - executando manutencao e coleta historica.")
        all_lotteries = ["megasena", "lotofacil", "quina", "lotomania"]
        collection_results = run_data_collection(all_lotteries)
        log_to_supabase(f"Manutencao dominical concluida. Coleta: {json.dumps(collection_results)}")
        print("Manutencao concluida.")
        return

    # FASE 1: Coleta de dados
    print(f"\n{'='*60}")
    print(f"  FASE 1: Coleta de Dados")
    print(f"{'='*60}")
    collection_results = run_data_collection(lotteries)
    log_to_supabase(f"Fase 1 concluida - Coleta: {json.dumps(collection_results)}")

    # FASE 2: Autopsia Semantica
    print(f"\n{'='*60}")
    print(f"  FASE 2: Autopsia Semantica (Precisao Historica)")
    print(f"{'='*60}")
    autopsy_results = run_autopsy(lotteries)
    if autopsy_results:
        log_to_supabase(f"Fase 2 concluida - Autopsia: {json.dumps(autopsy_results)}")

    # FASE 3: Analise Estatistica ML v7
    print(f"\n{'='*60}")
    print(f"  FASE 3: Analise Estatistica ML v7")
    print(f"  (Frequencia + Gaps + Sequencias + Quadrantes + Tendencia)")
    print(f"{'='*60}")
    ml_results = run_ml_analysis(lotteries)
    if ml_results:
        log_to_supabase(f"Fase 3 concluida - ML: {len(ml_results)} loterias analisadas")

    # FASE 3.5: Motor ML Avancado v8 (Markov + Ciclos + Ensemble)
    print(f"\n{'='*60}")
    print(f"  FASE 3.5: Motor ML Avancado v8")
    print(f"  (Markov + Janela Deslizante + Ciclos + Ensemble + Filtro)")
    print(f"{'='*60}")
    try:
        from ml_advanced import generate_advanced_predictions, backtest
        from ml_engine import save_predictions, fetch_historical_data
        for lottery in lotteries:
            draws = fetch_historical_data(lottery, 2000)
            if len(draws) >= 50:
                preds_adv, meta = generate_advanced_predictions(lottery, draws, 5)
                if preds_adv:
                    for p in preds_adv:
                        p['ai_enhanced'] = False
                        p['engine'] = 'SIAOL-PRO-v8-Advanced'
                    save_predictions(lottery, preds_adv, engine='SIAOL-PRO-v8-Advanced')
                    top_nums = [n for n, s in meta.get('top_ensemble_numbers', [])[:10]]
                    print(f"  {lottery}: {len(preds_adv)} pred avancadas | "
                          f"Markov: {meta.get('markov_built')} | "
                          f"Ciclos devidos: {meta.get('cycles_detected')} | "
                          f"Top: {top_nums}")
                    for p in preds_adv:
                        print(f"    Jogo {p['game_number']}: {p['numbers']} "
                              f"(soma={p['sum']}, {p['even_count']}P/{p['odd_count']}I)")
                    # Injetar dados avancados no ml_results para a IA usar
                    if lottery in ml_results:
                        ml_results[lottery]['advanced_predictions'] = preds_adv
                        ml_results[lottery]['advanced_meta'] = meta
            else:
                print(f"  {lottery}: {len(draws)} registros (minimo 50). Execute backfill_collector.py!")
    except Exception as e:
        print(f"  Motor avancado indisponivel: {e}")
        log_to_supabase(f"Motor avancado indisponivel: {e}", "WARN")

    # FASE 4: Analise por IA Multi-Cerebro
    print(f"\n{'='*60}")
    print(f"  FASE 4: Analise por IA Multi-Cerebro")
    print(f"  (Groq LLaMA 3.3 70B + Google Gemini 2.0 Flash)")
    print(f"{'='*60}")
    ai_results = run_ai_multi_brain(lotteries, ml_results)
    if ai_results:
        ai_summary = {k: {"providers": v["providers"], "confidence": v["avg_confidence"]}
                      for k, v in ai_results.items()}
        log_to_supabase(f"Fase 4 concluida - IA Multi-Cerebro: {json.dumps(ai_summary)}")

    # FASE 5: Resumo Final
    print(f"\n{'='*60}")
    print(f"  FASE 5: Relatorio Final")
    print(f"{'='*60}")

    total_predictions = 0
    for lottery in lotteries:
        ml_preds = len(ml_results.get(lottery, {}).get("predictions", []))
        ai_preds = ai_results.get(lottery, {}).get("enhanced_predictions", 0)
        total_predictions += ml_preds + ai_preds
        if ai_preds > 0:
            providers = ai_results[lottery].get("providers", [])
            confidence = ai_results[lottery].get("avg_confidence", 0)
            print(f"  {lottery}: {ml_preds} estatisticas + {ai_preds} IA ({', '.join(providers)}) "
                  f"[confianca: {confidence:.1%}]")
        else:
            print(f"  {lottery}: {ml_preds} predicoes estatisticas (IA indisponivel)")

    print(f"\n  Total: {total_predictions} predicoes geradas neste ciclo")
    print(f"  Proximo ciclo: amanha ao meio-dia (12:00 BRT)")
    print(f"{'='*60}")

    # FASE 6: Backtesting Automatico (se dados suficientes)
    try:
        from ml_advanced import backtest
        from ml_engine import fetch_historical_data
        print(f"\n{'='*60}")
        print(f"  FASE 6: Backtesting (Validacao Cientifica)")
        print(f"{'='*60}")
        for lottery in lotteries:
            draws = fetch_historical_data(lottery, 2000)
            if len(draws) >= 100:
                bt = backtest(lottery, draws, test_size=30, num_games=10)
                if bt:
                    print(f"  {lottery}: Media {bt['avg_match']:.1f}/{bt['pick']} "
                          f"({bt['avg_accuracy_pct']:.1f}%) | "
                          f"Melhor: {bt['best_match']}/{bt['pick']} | "
                          f"Pior: {bt['worst_match']}/{bt['pick']}")
            else:
                print(f"  {lottery}: Dados insuficientes para backtest ({len(draws)}/100)")
    except Exception as e:
        print(f"  Backtesting indisponivel: {e}")

    # FASE 7: Auto-Evolucao (SIAOL-PRO v9.0)
    print(f"\n{'='*60}")
    print(f"  FASE 7: Auto-Evolucao (The Organism)")
    print(f"{'='*60}")
    try:
        from auto_evolve import run_evolution_cycle
        # Evoluir a lotofacil (principal foco de precisao)
        if "lotofacil" in lotteries:
            evo_res = run_evolution_cycle("lotofacil")
            if evo_res and evo_res["improvement"] > 0:
                print(f"  [EVO] Sucesso! Melhoria de +{evo_res['improvement']:.3f} encontrada.")
            else:
                print("  [EVO] Nenhuma melhoria aceita nesta geracao.")
    except Exception as e:
        print(f"  [EVO] Erro no ciclo evolutivo: {e}")

    log_to_supabase(
        f"SIAOL-PRO v9.0 ciclo completo. "
        f"Total predicoes: {total_predictions}. "
        f"IAs usadas: {list(ai_results.keys()) if ai_results else 'Nenhuma'}."
    )



if __name__ == "__main__":
    main()
