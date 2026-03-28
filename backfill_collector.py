"""
SIAOL-PRO v8 - Coletor Massivo de Dados Historicos (Backfill)
Baixa TODOS os concursos de cada loteria desde o concurso #1.
Projetado para rodar 1 vez e alimentar o motor ML com 16.000+ registros.

USO: python backfill_collector.py
Tempo estimado: 2-4 horas (rate limiting da API da Caixa)
"""
import os
import json
import time
import sys
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

CAIXA_API = "https://servicebus2.caixa.gov.br/portaldeloterias/api"
FALLBACK_API = "https://loteriascaixa-api.herokuapp.com/api"

LOTTERIES = {
    "megasena": {"caixa": "megasena", "fallback": "mega-sena", "range": (1, 60), "pick": 6},
    "lotofacil": {"caixa": "lotofacil", "fallback": "lotofacil", "range": (1, 25), "pick": 15},
    "quina": {"caixa": "quina", "fallback": "quina", "range": (1, 80), "pick": 5},
    "lotomania": {"caixa": "lotomania", "fallback": "lotomania", "range": (0, 99), "pick": 20},
}

HEADERS_SUPABASE = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal"
}


def get_latest_draw(lottery_type):
    """Busca o numero do ultimo concurso."""
    config = LOTTERIES[lottery_type]
    try:
        resp = requests.get(f"{CAIXA_API}/{config['caixa']}", timeout=15,
                           headers={"User-Agent": "SIAOL-PRO/8.0"})
        if resp.status_code == 200:
            return resp.json().get("numero", 0)
    except:
        pass
    try:
        resp = requests.get(f"{FALLBACK_API}/{config['fallback']}/latest", timeout=15)
        if resp.status_code == 200:
            return resp.json().get("concurso", 0)
    except:
        pass
    return 0


def get_existing_draws(lottery_type):
    """Busca quais concursos ja existem no Supabase."""
    existing = set()
    url = (f"{SUPABASE_URL}/rest/v1/lottery_data"
           f"?lottery_type=eq.{lottery_type}"
           f"&select=draw_number"
           f"&limit=10000")
    try:
        resp = requests.get(url, headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}"
        }, timeout=30)
        if resp.status_code == 200:
            for row in resp.json():
                existing.add(row.get("draw_number", 0))
    except Exception as e:
        print(f"  Erro ao buscar existentes: {e}")
    return existing


def parse_caixa(data, lottery_type):
    """Parse resposta da Caixa."""
    try:
        for field in ["listaDezenasSorteadasOrdemSorteio", "dezenasSorteadasOrdemSorteio", "listaDezenas"]:
            if field in data:
                numbers = sorted([int(n) for n in data[field]])
                if numbers:
                    draw_date = data.get("dataApuracao", "")
                    if "/" in draw_date:
                        parts = draw_date.split("/")
                        draw_date = f"{parts[2]}-{parts[1]}-{parts[0]}"
                    return {
                        "lottery_type": lottery_type,
                        "draw_number": data.get("numero", 0),
                        "draw_date": draw_date,
                        "numbers": numbers,
                        "metadata": {
                            "accumulated_prize": data.get("valorAcumuladoProximoConcurso", 0),
                            "is_accumulated": data.get("acumulado", False),
                            "collected_at": datetime.now().isoformat(),
                            "source": "backfill_caixa"
                        }
                    }
    except:
        pass
    return None


def parse_fallback(data, lottery_type):
    """Parse resposta do fallback."""
    try:
        numbers = sorted([int(n) for n in data.get("dezenas", [])])
        if numbers:
            return {
                "lottery_type": lottery_type,
                "draw_number": data.get("concurso", 0),
                "draw_date": data.get("data", ""),
                "numbers": numbers,
                "metadata": {
                    "accumulated_prize": data.get("acumuladaProxConcurso", 0),
                    "is_accumulated": data.get("acumulou", False),
                    "collected_at": datetime.now().isoformat(),
                    "source": "backfill_fallback"
                }
            }
    except:
        pass
    return None


def fetch_draw(lottery_type, concurso):
    """Busca um concurso especifico (Caixa primeiro, fallback depois)."""
    config = LOTTERIES[lottery_type]

    # Tentar Caixa
    try:
        resp = requests.get(f"{CAIXA_API}/{config['caixa']}/{concurso}",
                           timeout=10, headers={"User-Agent": "SIAOL-PRO/8.0"})
        if resp.status_code == 200:
            result = parse_caixa(resp.json(), lottery_type)
            if result:
                return result
    except:
        pass

    # Tentar Fallback
    try:
        resp = requests.get(f"{FALLBACK_API}/{config['fallback']}/{concurso}", timeout=10)
        if resp.status_code == 200:
            result = parse_fallback(resp.json(), lottery_type)
            if result:
                return result
    except:
        pass

    return None


def validate(data, lottery_type):
    """Valida dados coletados."""
    if not data:
        return False
    config = LOTTERIES[lottery_type]
    numbers = data.get("numbers", [])
    if len(numbers) != config["pick"]:
        return False
    min_n, max_n = config["range"]
    for n in numbers:
        if n < min_n or n > max_n:
            return False
    return data.get("draw_number", 0) > 0


def save_batch(batch):
    """Salva um lote de dados no Supabase."""
    if not batch:
        return 0
    url = f"{SUPABASE_URL}/rest/v1/lottery_data"
    saved = 0
    # Supabase aceita POST com array para bulk insert
    try:
        resp = requests.post(url, headers=HEADERS_SUPABASE, json=batch, timeout=30)
        if resp.status_code == 201:
            saved = len(batch)
        else:
            # Tentar um a um se falhar em lote
            for item in batch:
                try:
                    r = requests.post(url, headers=HEADERS_SUPABASE, json=item, timeout=10)
                    if r.status_code == 201:
                        saved += 1
                except:
                    pass
    except Exception as e:
        print(f"  Erro no batch: {e}")
        for item in batch:
            try:
                r = requests.post(url, headers=HEADERS_SUPABASE, json=item, timeout=10)
                if r.status_code == 201:
                    saved += 1
            except:
                pass
    return saved


def backfill_lottery(lottery_type):
    """Coleta TODOS os concursos de uma loteria."""
    config = LOTTERIES[lottery_type]
    latest = get_latest_draw(lottery_type)

    if latest == 0:
        print(f"  ✗ Nao consegui descobrir o ultimo concurso de {lottery_type}")
        return 0

    print(f"\n{'='*60}")
    print(f"  BACKFILL: {lottery_type.upper()} (Concursos 1 a {latest})")
    print(f"{'='*60}")

    # Verificar quais ja existem
    existing = get_existing_draws(lottery_type)
    print(f"  Ja existem {len(existing)} registros no banco.")

    # Calcular quais faltam
    missing = []
    for c in range(1, latest + 1):
        if c not in existing:
            missing.append(c)

    print(f"  Faltam {len(missing)} concursos para coletar.")

    if not missing:
        print(f"  ✓ Banco completo para {lottery_type}!")
        return 0

    total_saved = 0
    batch = []
    errors = 0
    batch_size = 20

    for i, concurso in enumerate(missing):
        data = fetch_draw(lottery_type, concurso)

        if data and validate(data, lottery_type):
            batch.append(data)
        else:
            errors += 1

        # Salvar em lotes
        if len(batch) >= batch_size:
            saved = save_batch(batch)
            total_saved += saved
            batch = []

        # Rate limiting
        time.sleep(0.5)

        # Progresso
        if (i + 1) % 50 == 0 or (i + 1) == len(missing):
            pct = (i + 1) / len(missing) * 100
            print(f"  [{lottery_type}] {i+1}/{len(missing)} ({pct:.1f}%) | "
                  f"Salvos: {total_saved} | Erros: {errors}")

    # Salvar resto do batch
    if batch:
        saved = save_batch(batch)
        total_saved += saved

    print(f"  ✓ {lottery_type}: {total_saved} concursos salvos, {errors} erros")
    return total_saved


def main():
    print("=" * 60)
    print("  SIAOL-PRO v8 - BACKFILL MASSIVO DE DADOS HISTORICOS")
    print("  Coletando TODOS os concursos desde o #1")
    print("=" * 60)
    print(f"  Inicio: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("  ✗ ERRO: Supabase nao configurado! Verifique o .env")
        sys.exit(1)

    grand_total = 0
    for lottery_type in LOTTERIES:
        saved = backfill_lottery(lottery_type)
        grand_total += saved

    print(f"\n{'='*60}")
    print(f"  BACKFILL CONCLUIDO!")
    print(f"  Total de registros salvos: {grand_total}")
    print(f"  Fim: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
