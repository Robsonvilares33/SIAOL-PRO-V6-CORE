"""
SIAOL-PRO v6.0 - Coletor de Dados de Loterias Brasileiras
Coleta dados reais da API oficial da Caixa Economica Federal
e da API publica guilhermeasn/loteria.json como fallback.
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

# Configuracao das loterias
LOTTERIES = {
    "megasena": {
        "name": "Mega-Sena",
        "caixa_endpoint": "megasena",
        "fallback_endpoint": "mega-sena",
        "num_range": (1, 60),
        "numbers_per_draw": 6,
        "draws_to_collect": 100,
        "draw_days": [1, 3, 5]  # Ter, Qui, Sab (0=Seg)
    },
    "lotofacil": {
        "name": "Lotofacil",
        "caixa_endpoint": "lotofacil",
        "fallback_endpoint": "lotofacil",
        "num_range": (1, 25),
        "numbers_per_draw": 15,
        "draws_to_collect": 100,
        "draw_days": [0, 1, 2, 3, 4, 5]  # Seg a Sab
    },
    "quina": {
        "name": "Quina",
        "caixa_endpoint": "quina",
        "fallback_endpoint": "quina",
        "num_range": (1, 80),
        "numbers_per_draw": 5,
        "draws_to_collect": 100,
        "draw_days": [0, 1, 2, 3, 4, 5]  # Seg a Sab
    },
    "lotomania": {
        "name": "Lotomania",
        "caixa_endpoint": "lotomania",
        "fallback_endpoint": "lotomania",
        "num_range": (0, 99),
        "numbers_per_draw": 20,
        "draws_to_collect": 100,
        "draw_days": [0, 2, 4]  # Seg, Qua, Sex
    }
}

CAIXA_API_BASE = "https://servicebus2.caixa.gov.br/portaldeloterias/api"
FALLBACK_API_BASE = "https://loteriascaixa-api.herokuapp.com/api"


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
        "metadata": {"source": "data_collector", "timestamp": datetime.now().isoformat()}
    }
    try:
        requests.post(url, headers=headers, json=data, timeout=10)
    except Exception as e:
        print(f"Erro ao logar: {e}")


def fetch_latest_from_caixa(lottery_type):
    """Busca o ultimo resultado da API da Caixa."""
    config = LOTTERIES[lottery_type]
    url = f"{CAIXA_API_BASE}/{config['caixa_endpoint']}"
    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "SIAOL-PRO/6.0"})
        if resp.status_code == 200:
            data = resp.json()
            return parse_caixa_response(data, lottery_type)
    except Exception as e:
        print(f"Erro na API Caixa para {lottery_type}: {e}")
    return None


def fetch_from_caixa(lottery_type, concurso):
    """Busca um concurso especifico da API da Caixa."""
    config = LOTTERIES[lottery_type]
    url = f"{CAIXA_API_BASE}/{config['caixa_endpoint']}/{concurso}"
    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "SIAOL-PRO/6.0"})
        if resp.status_code == 200:
            data = resp.json()
            return parse_caixa_response(data, lottery_type)
    except Exception as e:
        print(f"Erro na API Caixa para {lottery_type}/{concurso}: {e}")
    return None


def parse_caixa_response(data, lottery_type):
    """Converte resposta da API da Caixa para formato padrao."""
    try:
        # A API da Caixa usa diferentes nomes de campo
        numbers_field = "listaDezenasSorteadasOrdemSorteio"
        if numbers_field not in data:
            numbers_field = "dezenasSorteadasOrdemSorteio"
        if numbers_field not in data:
            numbers_field = "listaDezenas"

        numbers = [int(n) for n in data.get(numbers_field, [])]
        if not numbers:
            return None

        draw_date = data.get("dataApuracao", "")
        # Converter formato dd/mm/yyyy para yyyy-mm-dd
        if "/" in draw_date:
            parts = draw_date.split("/")
            draw_date = f"{parts[2]}-{parts[1]}-{parts[0]}"

        return {
            "lottery_type": lottery_type,
            "draw_number": data.get("numero", 0),
            "draw_date": draw_date,
            "numbers": sorted(numbers),
            "accumulated_prize": data.get("valorAcumuladoProximoConcurso", 0),
            "is_accumulated": data.get("acumulado", False)
        }
    except Exception as e:
        print(f"Erro ao parsear resposta Caixa: {e}")
        return None


def fetch_from_fallback(lottery_type, concurso=None):
    """Busca dados da API alternativa."""
    config = LOTTERIES[lottery_type]
    endpoint = config["fallback_endpoint"]
    if concurso:
        url = f"{FALLBACK_API_BASE}/{endpoint}/{concurso}"
    else:
        url = f"{FALLBACK_API_BASE}/{endpoint}/latest"
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            numbers = [int(n) for n in data.get("dezenas", [])]
            if not numbers:
                return None
            return {
                "lottery_type": lottery_type,
                "draw_number": data.get("concurso", 0),
                "draw_date": data.get("data", ""),
                "numbers": sorted(numbers),
                "accumulated_prize": data.get("acumuladaProxConcurso", 0),
                "is_accumulated": data.get("acumulou", False)
            }
    except Exception as e:
        print(f"Erro na API fallback para {lottery_type}: {e}")
    return None


def validate_data(data, lottery_type):
    """Valida os dados coletados."""
    if not data:
        return False
    config = LOTTERIES[lottery_type]
    min_num, max_num = config["num_range"]
    expected_count = config["numbers_per_draw"]

    numbers = data.get("numbers", [])
    if len(numbers) != expected_count:
        print(f"Validacao falhou: esperado {expected_count} numeros, recebido {len(numbers)}")
        return False

    for n in numbers:
        if n < min_num or n > max_num:
            print(f"Validacao falhou: numero {n} fora do range [{min_num}, {max_num}]")
            return False

    if data.get("draw_number", 0) <= 0:
        print("Validacao falhou: numero do concurso invalido")
        return False

    return True


def save_to_supabase(data):
    """Salva dados no Supabase com verificacao de duplicata."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        print(f"Supabase nao configurado. Dados: {json.dumps(data)}")
        return False

    # Verificar duplicata
    check_url = (f"{SUPABASE_URL}/rest/v1/lottery_data"
                 f"?lottery_type=eq.{data['lottery_type']}"
                 f"&draw_number=eq.{data['draw_number']}"
                 f"&select=id")
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    try:
        check_resp = requests.get(check_url, headers=headers, timeout=10)
        if check_resp.status_code == 200 and len(check_resp.json()) > 0:
            return False  # Duplicata, pular silenciosamente
    except Exception:
        pass

    # Inserir dados
    insert_url = f"{SUPABASE_URL}/rest/v1/lottery_data"
    headers["Prefer"] = "return=minimal"
    payload = {
        "lottery_type": data["lottery_type"],
        "draw_number": data["draw_number"],
        "draw_date": data["draw_date"] if data["draw_date"] else None,
        "numbers": data["numbers"],
        "metadata": {
            "accumulated_prize": data.get("accumulated_prize", 0),
            "is_accumulated": data.get("is_accumulated", False),
            "collected_at": datetime.now().isoformat()
        }
    }
    try:
        resp = requests.post(insert_url, headers=headers, json=payload, timeout=10)
        if resp.status_code == 201:
            return True
        else:
            print(f"Erro ao inserir: {resp.status_code} - {resp.text}")
    except Exception as e:
        print(f"Erro ao salvar no Supabase: {e}")
    return False


def collect_recent_results(lottery_type, num_draws=50):
    """Coleta os ultimos resultados de uma loteria."""
    config = LOTTERIES[lottery_type]
    collected = 0
    errors = 0

    # Primeiro, buscar o ultimo resultado para saber o numero do concurso atual
    latest = fetch_latest_from_caixa(lottery_type)
    if not latest:
        latest = fetch_from_fallback(lottery_type)

    if not latest:
        log_to_supabase(f"Nao foi possivel obter o ultimo resultado de {config['name']}", "ERROR")
        return 0, 1

    latest_draw = latest["draw_number"]
    print(f"Ultimo concurso de {config['name']}: {latest_draw}")

    # Salvar o ultimo resultado
    if validate_data(latest, lottery_type):
        if save_to_supabase(latest):
            collected += 1

    # Coletar resultados anteriores
    for i in range(1, min(num_draws, 100)):
        concurso = latest_draw - i
        if concurso <= 0:
            break

        data = fetch_from_caixa(lottery_type, concurso)
        if not data:
            data = fetch_from_fallback(lottery_type, concurso)

        if data and validate_data(data, lottery_type):
            if save_to_supabase(data):
                collected += 1
        else:
            errors += 1

        # Rate limiting - 1 request por segundo
        time.sleep(1)

        # Progresso a cada 10 concursos
        if i % 10 == 0:
            print(f"  Progresso {config['name']}: {i}/{num_draws} ({collected} coletados, {errors} erros)")

    return collected, errors


def collect_all_lotteries(num_draws=30):
    """Coleta dados de todas as loterias."""
    total_collected = 0
    total_errors = 0
    results = {}

    log_to_supabase("Iniciando coleta de dados de todas as loterias.")

    for lottery_type in LOTTERIES:
        print(f"\n=== Coletando {LOTTERIES[lottery_type]['name']} ===")
        collected, errors = collect_recent_results(lottery_type, num_draws)
        total_collected += collected
        total_errors += errors
        results[lottery_type] = {"collected": collected, "errors": errors}
        print(f"  Resultado: {collected} coletados, {errors} erros")
        time.sleep(2)  # Pausa entre loterias

    summary = (f"Coleta finalizada. Total: {total_collected} registros coletados, "
               f"{total_errors} erros. Detalhes: {json.dumps(results)}")
    print(f"\n{summary}")
    log_to_supabase(summary)

    return results


if __name__ == "__main__":
    # Quando executado diretamente, coletar os ultimos 30 resultados de cada loteria
    collect_all_lotteries(30)
