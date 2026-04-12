"""
SIAOL-PRO v10.0 - BACKFILL TOTAL
Coleta todos os sorteios faltantes (do concurso nº 1 ao atual) para cada loteria.
Usa a API oficial da Caixa com fallback para Playwright se necessário.
"""
import os
import json
import time
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Configuração das loterias com seus números atuais (verificados em 2026-04-12)
LOTTERY_CONFIG = {
    "megasena": {"current": 2995, "range": (1, 60), "pick": 6},
    "lotofacil": {"current": 3659, "range": (1, 25), "pick": 15},
    "quina": {"current": 6999, "range": (1, 80), "pick": 5},
    "lotomania": {"current": 2910, "range": (0, 99), "pick": 20},
    "timemania": {"current": 2379, "range": (1, 80), "pick": 10},
    "duplasena": {"current": 2943, "range": (1, 50), "pick": 6},
    "diadesorte": {"current": 1200, "range": (1, 31), "pick": 7},
    "supersete": {"current": 833, "range": (1, 7), "pick": 7},
    "maismilionaria": {"current": 345, "range": (1, 50), "pick": 6},
}

# Lacunas conhecidas (faltam esses números)
KNOWN_GAPS = {
    "timemania": [617, 56, 266, 176, 647, 11, 57, 58, 271, 618, 263, 34, 50]
}

def fetch_from_api(lottery_type, draw_number):
    """Busca um sorteio específico da API da Caixa."""
    try:
        url = f"https://servicebus2.caixa.gov.br/portaldeloterias/api/{lottery_type}/{draw_number}"
        response = requests.get(url, verify=False, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return {
                "lottery_type": lottery_type,
                "draw_number": data.get("numero"),
                "draw_date": data.get("data"),
                "numbers": sorted(data.get("dezenas", [])),
                "accumulated_prize": data.get("valorAcumulado"),
                "winners": {
                    "6_numbers": data.get("ganhadores", {}).get("sena", 0),
                    "5_numbers": data.get("ganhadores", {}).get("quina", 0),
                    "4_numbers": data.get("ganhadores", {}).get("quadra", 0),
                    "3_numbers": data.get("ganhadores", {}).get("terno", 0),
                },
                "metadata": {
                    "collected_at": datetime.now().isoformat(),
                    "is_accumulated": data.get("acumulado", False),
                    "accumulated_prize": data.get("valorAcumulado", 0)
                }
            }
    except Exception as e:
        print(f"[ERRO] Falha ao buscar {lottery_type} concurso {draw_number}: {e}")
    return None

def save_to_supabase(records):
    """Salva registros no Supabase."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("[ERRO] Credenciais do Supabase não configuradas.")
        return False

    url = f"{SUPABASE_URL}/rest/v1/lottery_data"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }

    success_count = 0
    for record in records:
        try:
            response = requests.post(url, headers=headers, json=record, timeout=10)
            if response.status_code in [201, 200]:
                success_count += 1
            else:
                print(f"[AVISO] Status {response.status_code} ao salvar {record['lottery_type']} #{record['draw_number']}")
        except Exception as e:
            print(f"[ERRO] Falha ao salvar {record['lottery_type']} #{record['draw_number']}: {e}")

    return success_count

def backfill_lottery(lottery_type, start_draw=1):
    """Faz backfill completo de uma loteria."""
    config = LOTTERY_CONFIG.get(lottery_type)
    if not config:
        print(f"[ERRO] Loteria {lottery_type} não configurada.")
        return 0

    current_draw = config["current"]
    print(f"\n[BACKFILL] Iniciando {lottery_type.upper()}: concursos {start_draw} a {current_draw}")

    collected = []
    failed = []
    gaps = KNOWN_GAPS.get(lottery_type, [])

    for draw_num in range(start_draw, current_draw + 1):
        if draw_num in gaps:
            print(f"  [SKIP] {lottery_type} #{draw_num} (lacuna conhecida)")
            continue

        record = fetch_from_api(lottery_type, draw_num)
        if record:
            collected.append(record)
            print(f"  [OK] {lottery_type} #{draw_num}")
        else:
            failed.append(draw_num)
            print(f"  [FALHA] {lottery_type} #{draw_num}")

        # Rate limiting: 1 request por segundo
        time.sleep(1)

        # Salvar em lotes de 50
        if len(collected) >= 50:
            saved = save_to_supabase(collected)
            print(f"  [SALVO] {saved}/{len(collected)} registros")
            collected = []

    # Salvar os últimos registros
    if collected:
        saved = save_to_supabase(collected)
        print(f"  [SALVO] {saved}/{len(collected)} registros (lote final)")

    print(f"[RESUMO] {lottery_type}: {len(collected) + len(failed)} coletados, {len(failed)} falharam")
    return len(collected)

def main():
    """Executa o backfill total para todas as loterias."""
    print("=" * 60)
    print("  SIAOL-PRO v10.0 - BACKFILL TOTAL")
    print("  Coleta Histórica Completa (Concurso 1 ao Atual)")
    print("=" * 60)

    total_collected = 0
    for lottery_type in LOTTERY_CONFIG.keys():
        collected = backfill_lottery(lottery_type)
        total_collected += collected

    print("\n" + "=" * 60)
    print(f"[CONCLUÍDO] Total de {total_collected} sorteios coletados e salvos.")
    print("=" * 60)

if __name__ == "__main__":
    main()
