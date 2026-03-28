"""
SIAOL-PRO v6.0 - Controlador Principal Autonomo
Orquestra a coleta de dados, analise ML e predicoes
baseado no calendario de sorteios das loterias brasileiras.

CALENDARIO DE SORTEIOS:
  Mega-Sena:  Terca, Quinta, Sabado
  Lotofacil:  Segunda a Sabado
  Quina:      Segunda a Sabado
  Lotomania:  Segunda, Quarta, Sexta
  Dupla Sena: Terca, Quinta, Sabado
  Timemania:  Terca, Quinta, Sabado

O sistema roda a cada 30 minutos via GitHub Actions.
Em dias de sorteio, coleta resultados e gera novas predicoes.
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
        "metadata": {"source": "main_controller", "timestamp": datetime.now(BR_TZ).isoformat()}
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
    # Retrocede 1 dia (pois a cron roda 12:00 do dia seguinte para garantir dados estaveis)
    target_date = now - timedelta(days=1)
    weekday = target_date.weekday()
    
    lotteries = LOTTERY_SCHEDULE.get(weekday, [])
    # Retorna as 'loterias do dia', mas baseadas na rotina cronologica perfeita.
    return lotteries, DAY_NAMES.get(weekday, "Desconhecido"), now


# Funções de should_collect e should_run removidas pois o agendamento será unificado na nuvem.

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
    """Executa analise ML para as loterias do dia."""
    try:
        from ml_engine import run_analysis
        results = {}
        for lottery in lotteries:
            print(f"  Analisando {lottery}...")
            result = run_analysis(lottery)
            if result:
                results[lottery] = {
                    "draws_analyzed": result["draws_analyzed"],
                    "predictions_count": len(result.get("predictions", []))
                }
        return results
    except ImportError as e:
        print(f"Erro ao importar ml_engine: {e}")
        log_to_supabase(f"Erro ao importar ml_engine: {e}", "ERROR")
        return {}
    except Exception as e:
        print(f"Erro na analise ML: {e}")
        log_to_supabase(f"Erro na analise ML: {e}", "ERROR")
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
                        f"&limit=5"
                        f"&select=predicted_numbers,created_at")
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
                    for pred in predictions:
                        pred_numbers = set(pred.get("predicted_numbers", []))
                        match = len(real_numbers & pred_numbers)
                        best_match = max(best_match, match)

                    results[lottery] = {
                        "best_match": best_match,
                        "total_numbers": len(real_numbers),
                        "accuracy_pct": round(best_match / max(len(real_numbers), 1) * 100, 1)
                    }
                    print(f"  Autopsia {lottery}: melhor match = {best_match}/{len(real_numbers)} ({results[lottery]['accuracy_pct']}%)")
        except Exception as e:
            print(f"  Erro na autopsia de {lottery}: {e}")

    return results


def main():
    """Ciclo principal do SIAOL-PRO v6.0."""
    print("=" * 60)
    print("  SIAOL-PRO v6.0 - Ciclo Autonomo")
    print("=" * 60)

    # Obter loterias do dia
    lotteries, day_name, now = get_today_lotteries()
    print(f"\nData/Hora (BR): {now.strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"Dia: {day_name}")
    print(f"Loterias do dia: {', '.join(lotteries) if lotteries else 'Nenhuma (Domingo)'}")

    log_to_supabase(
        f"Ciclo autonomo iniciado. Dia: {day_name}. "
        f"Loterias: {', '.join(lotteries) if lotteries else 'Nenhuma'}. "
        f"Hora: {now.strftime('%H:%M')}"
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
    print(f"\n--- FASE 1: Coleta de Dados ---")
    collection_results = run_data_collection(lotteries)
    log_to_supabase(f"Coleta de dados concluida: {json.dumps(collection_results)}")

    # FASE 2: Autopsia Semantica (comparar predicoes vs resultados)
    print(f"\n--- FASE 2: Autopsia Semantica ---")
    autopsy_results = run_autopsy(lotteries)
    if autopsy_results:
        log_to_supabase(f"Autopsia semantica concluida: {json.dumps(autopsy_results)}")

    # FASE 3: Analise ML e Novas Predicoes
    print(f"\n--- FASE 3: Analise ML e Predicoes ---")
    ml_results = run_ml_analysis(lotteries)
    if ml_results:
        log_to_supabase(f"Analise ML concluida: {json.dumps(ml_results)}")

    # Resumo final
    print(f"\n{'=' * 60}")
    print(f"  Ciclo concluido com sucesso!")
    print(f"  Proximo ciclo em 30 minutos.")
    print(f"{'=' * 60}")

    log_to_supabase("Ciclo autonomo concluido com sucesso.")


if __name__ == "__main__":
    main()
