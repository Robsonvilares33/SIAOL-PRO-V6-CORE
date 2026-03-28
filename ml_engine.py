"""
SIAOL-PRO v6.0 - Motor de Machine Learning e Analise Estatistica
Analisa dados historicos das loterias e gera predicoes baseadas em
frequencia, gaps, clusters e padroes estatisticos.
Funciona 100% offline sem necessidade de API de IA paga.
"""
import os
import json
import math
import random
import requests
from datetime import datetime
from collections import Counter
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Configuracao das loterias
LOTTERY_CONFIG = {
    "megasena": {"name": "Mega-Sena", "range": (1, 60), "pick": 6},
    "lotofacil": {"name": "Lotofacil", "range": (1, 25), "pick": 15},
    "quina": {"name": "Quina", "range": (1, 80), "pick": 5},
    "lotomania": {"name": "Lotomania", "range": (0, 99), "pick": 20}
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
        "metadata": {"source": "ml_engine", "timestamp": datetime.now().isoformat()}
    }
    try:
        requests.post(url, headers=headers, json=data, timeout=10)
    except Exception:
        pass


def fetch_historical_data(lottery_type, limit=100):
    """Busca dados historicos do Supabase."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return []
    url = (f"{SUPABASE_URL}/rest/v1/lottery_data"
           f"?lottery_type=eq.{lottery_type}"
           f"&order=draw_number.desc"
           f"&limit={limit}"
           f"&select=draw_number,draw_date,numbers")
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"Erro ao buscar dados: {e}")
    return []


def analyze_frequency(draws, num_range):
    """Analise de frequencia dos numeros."""
    min_n, max_n = num_range
    freq = Counter()
    for draw in draws:
        for n in draw.get("numbers", []):
            freq[n] += 1

    total_draws = len(draws)
    if total_draws == 0:
        return {}

    analysis = {}
    for n in range(min_n, max_n + 1):
        count = freq.get(n, 0)
        expected = total_draws * 1.0 / (max_n - min_n + 1)
        analysis[n] = {
            "count": count,
            "frequency": round(count / total_draws, 4),
            "deviation": round((count - expected) / max(expected, 1), 4),
            "is_hot": count > expected * 1.2,
            "is_cold": count < expected * 0.8
        }
    return analysis


def analyze_gaps(draws, num_range):
    """Analise de gaps - quantos sorteios desde a ultima aparicao."""
    min_n, max_n = num_range
    gaps = {}
    for n in range(min_n, max_n + 1):
        gap = 0
        for draw in draws:
            if n in draw.get("numbers", []):
                break
            gap += 1
        gaps[n] = gap
    return gaps


def analyze_pairs(draws):
    """Analise de pares frequentes."""
    pair_freq = Counter()
    for draw in draws:
        numbers = draw.get("numbers", [])
        for i in range(len(numbers)):
            for j in range(i + 1, len(numbers)):
                pair = (numbers[i], numbers[j])
                pair_freq[pair] += 1
    return pair_freq.most_common(20)


def analyze_sum_distribution(draws):
    """Analise da distribuicao de somas."""
    sums = [sum(d.get("numbers", [])) for d in draws]
    if not sums:
        return {"mean": 0, "std": 0, "min": 0, "max": 0}
    mean = sum(sums) / len(sums)
    variance = sum((s - mean) ** 2 for s in sums) / len(sums)
    std = math.sqrt(variance)
    return {
        "mean": round(mean, 2),
        "std": round(std, 2),
        "min": min(sums),
        "max": max(sums),
        "target_range": (round(mean - std), round(mean + std))
    }


def analyze_even_odd(draws):
    """Analise de distribuicao par/impar."""
    distributions = []
    for draw in draws:
        numbers = draw.get("numbers", [])
        evens = sum(1 for n in numbers if n % 2 == 0)
        odds = len(numbers) - evens
        distributions.append((evens, odds))

    if not distributions:
        return {"most_common": (0, 0)}

    dist_counter = Counter(distributions)
    return {
        "most_common": dist_counter.most_common(3),
        "distributions": dict(dist_counter)
    }


def generate_prediction(lottery_type, draws, num_games=5):
    """Gera predicoes baseadas em analise estatistica."""
    config = LOTTERY_CONFIG[lottery_type]
    num_range = config["range"]
    pick = config["pick"]
    min_n, max_n = num_range

    if len(draws) < 5:
        log_to_supabase(f"Dados insuficientes para {config['name']}. Necessario pelo menos 5 sorteios.", "WARN")
        return []

    # Analises
    freq_analysis = analyze_frequency(draws, num_range)
    gap_analysis = analyze_gaps(draws, num_range)
    sum_dist = analyze_sum_distribution(draws)
    even_odd = analyze_even_odd(draws)

    # Calcular score para cada numero
    scores = {}
    for n in range(min_n, max_n + 1):
        freq_score = freq_analysis.get(n, {}).get("frequency", 0) * 40
        gap_score = min(gap_analysis.get(n, 0) / max(len(draws), 1), 1) * 30
        deviation = freq_analysis.get(n, {}).get("deviation", 0)
        balance_score = (1 - abs(deviation)) * 30
        scores[n] = freq_score + gap_score + balance_score

    # Gerar jogos
    predictions = []
    for game_idx in range(num_games):
        game_numbers = []
        available = list(range(min_n, max_n + 1))

        # Selecionar numeros baseado nos scores com aleatoriedade controlada
        weights = [scores.get(n, 0) + random.uniform(0, 10) for n in available]

        for _ in range(pick):
            if not available:
                break
            # Selecao ponderada
            total_weight = sum(weights)
            if total_weight == 0:
                idx = random.randint(0, len(available) - 1)
            else:
                r = random.uniform(0, total_weight)
                cumulative = 0
                idx = 0
                for i, w in enumerate(weights):
                    cumulative += w
                    if cumulative >= r:
                        idx = i
                        break

            game_numbers.append(available[idx])
            available.pop(idx)
            weights.pop(idx)

        game_numbers.sort()

        # Verificar se a soma esta dentro do range esperado
        game_sum = sum(game_numbers)
        target_min, target_max = sum_dist.get("target_range", (0, 9999))

        predictions.append({
            "game_number": game_idx + 1,
            "numbers": game_numbers,
            "sum": game_sum,
            "sum_in_range": target_min <= game_sum <= target_max,
            "even_count": sum(1 for n in game_numbers if n % 2 == 0),
            "odd_count": sum(1 for n in game_numbers if n % 2 != 0)
        })

    return predictions


def save_predictions(lottery_type, predictions):
    """Salva predicoes no Supabase."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return False

    url = f"{SUPABASE_URL}/rest/v1/lottery_predictions"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }

    for pred in predictions:
        payload = {
            "lottery_type": lottery_type,
            "predicted_numbers": pred["numbers"],
            "confidence": 0.5,  # Score base, sera ajustado com autopsia semantica
            "metadata": {
                "game_number": pred["game_number"],
                "sum": pred["sum"],
                "sum_in_range": pred["sum_in_range"],
                "even_odd": f"{pred['even_count']}P/{pred['odd_count']}I",
                "generated_at": datetime.now().isoformat(),
                "engine": "SIAOL-PRO-v6-ML"
            }
        }
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=10)
            if resp.status_code != 201:
                print(f"Erro ao salvar predicao: {resp.status_code}")
        except Exception as e:
            print(f"Erro ao salvar predicao: {e}")

    return True


def run_analysis(lottery_type):
    """Executa analise completa para uma loteria."""
    config = LOTTERY_CONFIG[lottery_type]
    print(f"\n=== Analise {config['name']} ===")

    draws = fetch_historical_data(lottery_type, 100)
    if len(draws) < 5:
        print(f"  Dados insuficientes ({len(draws)} sorteios). Pulando.")
        return None

    print(f"  {len(draws)} sorteios carregados.")

    # Analises
    freq = analyze_frequency(draws, config["range"])
    gaps = analyze_gaps(draws, config["range"])
    sum_dist = analyze_sum_distribution(draws)
    even_odd = analyze_even_odd(draws)

    # Top 10 numeros mais frequentes
    hot_numbers = sorted(freq.items(), key=lambda x: x[1]["count"], reverse=True)[:10]
    cold_numbers = sorted(freq.items(), key=lambda x: x[1]["count"])[:10]

    # Top 10 numeros com maior gap
    high_gap = sorted(gaps.items(), key=lambda x: x[1], reverse=True)[:10]

    print(f"  Numeros quentes: {[n for n, _ in hot_numbers]}")
    print(f"  Numeros frios: {[n for n, _ in cold_numbers]}")
    print(f"  Maior gap: {[f'{n}({g})' for n, g in high_gap[:5]]}")
    print(f"  Soma media: {sum_dist['mean']} (range: {sum_dist.get('target_range', 'N/A')})")

    # Gerar predicoes
    predictions = generate_prediction(lottery_type, draws, num_games=5)
    if predictions:
        save_predictions(lottery_type, predictions)
        print(f"  {len(predictions)} predicoes geradas e salvas.")
        for p in predictions:
            print(f"    Jogo {p['game_number']}: {p['numbers']} (soma={p['sum']}, {p['even_count']}P/{p['odd_count']}I)")

    return {
        "lottery": config["name"],
        "draws_analyzed": len(draws),
        "hot_numbers": [n for n, _ in hot_numbers],
        "cold_numbers": [n for n, _ in cold_numbers],
        "sum_stats": sum_dist,
        "predictions": predictions
    }


def run_all_analyses():
    """Executa analise para todas as loterias."""
    log_to_supabase("Iniciando ciclo de analise ML para todas as loterias.")
    results = {}

    for lottery_type in LOTTERY_CONFIG:
        result = run_analysis(lottery_type)
        if result:
            results[lottery_type] = result

    summary = f"Analise ML concluida. Loterias analisadas: {len(results)}"
    print(f"\n{summary}")
    log_to_supabase(summary)
    return results


if __name__ == "__main__":
    run_all_analyses()
