"""
SIAOL-PRO v7.0 - Motor de Machine Learning e Analise Estatistica Avancada
Analisa dados historicos das loterias e gera predicoes baseadas em
frequencia, gaps, clusters, sequencias, quadrantes e padroes estatisticos.
Integrado com ai_brain.py para analise por IA Multi-Cerebro.
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
        "metadata": {"source": "ml_engine_v7", "timestamp": datetime.now().isoformat()}
    }
    try:
        requests.post(url, headers=headers, json=data, timeout=10)
    except Exception:
        pass


def fetch_historical_data(lottery_type, limit=200):
    """Busca dados historicos do Supabase COM PAGINACAO para superar o limite de 1000 linhas."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return []
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    all_data = []
    page_size = 1000
    offset = 0
    while len(all_data) < limit:
        batch_limit = min(page_size, limit - len(all_data))
        url = (f"{SUPABASE_URL}/rest/v1/lottery_data"
               f"?lottery_type=eq.{lottery_type}"
               f"&order=draw_number.desc"
               f"&limit={batch_limit}"
               f"&offset={offset}"
               f"&select=draw_number,draw_date,numbers")
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            if resp.status_code == 200:
                batch = resp.json()
                if not batch:
                    break
                all_data.extend(batch)
                if len(batch) < batch_limit:
                    break
                offset += len(batch)
            else:
                break
        except Exception as e:
            print(f"Erro ao buscar dados (offset {offset}): {e}")
            break
    return all_data


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


# ============================================================
# NOVAS ANALISES v7
# ============================================================

def analyze_sequences(draws, num_range):
    """Detecta padroes de numeros consecutivos nos sorteios."""
    min_n, max_n = num_range
    seq_counts = {2: 0, 3: 0, 4: 0}  # Pares, trios, quartetos consecutivos
    total = len(draws)

    for draw in draws:
        numbers = sorted(draw.get("numbers", []))
        current_seq = 1
        for i in range(1, len(numbers)):
            if numbers[i] == numbers[i-1] + 1:
                current_seq += 1
            else:
                if current_seq >= 2:
                    key = min(current_seq, 4)
                    seq_counts[key] = seq_counts.get(key, 0) + 1
                current_seq = 1
        if current_seq >= 2:
            key = min(current_seq, 4)
            seq_counts[key] = seq_counts.get(key, 0) + 1

    return {
        "consecutive_pairs_pct": round(seq_counts.get(2, 0) / max(total, 1) * 100, 1),
        "consecutive_trios_pct": round(seq_counts.get(3, 0) / max(total, 1) * 100, 1),
        "consecutive_quads_pct": round(seq_counts.get(4, 0) / max(total, 1) * 100, 1),
        "raw_counts": seq_counts
    }


def analyze_quadrants(draws, num_range):
    """Divide o range em 4 quadrantes e analisa distribuicao."""
    min_n, max_n = num_range
    total_range = max_n - min_n + 1
    q_size = total_range // 4

    quadrants = {
        "Q1": (min_n, min_n + q_size - 1),
        "Q2": (min_n + q_size, min_n + 2 * q_size - 1),
        "Q3": (min_n + 2 * q_size, min_n + 3 * q_size - 1),
        "Q4": (min_n + 3 * q_size, max_n),
    }

    q_counts = {"Q1": 0, "Q2": 0, "Q3": 0, "Q4": 0}
    total_numbers = 0

    for draw in draws:
        for n in draw.get("numbers", []):
            total_numbers += 1
            for q_name, (q_min, q_max) in quadrants.items():
                if q_min <= n <= q_max:
                    q_counts[q_name] += 1
                    break

    # Percentuais
    q_pcts = {}
    for q_name in q_counts:
        q_pcts[q_name] = round(q_counts[q_name] / max(total_numbers, 1) * 100, 1)

    return {
        "quadrant_ranges": {k: list(v) for k, v in quadrants.items()},
        "distribution_pct": q_pcts,
        "ideal_pct": 25.0,  # Distribuicao equilibrada seria 25% cada
        "most_active": max(q_pcts, key=q_pcts.get),
        "least_active": min(q_pcts, key=q_pcts.get),
    }


def analyze_trends(draws, num_range, window=10):
    """Analisa tendencia de cada numero nos ultimos N sorteios vs historico."""
    min_n, max_n = num_range
    if len(draws) < window * 2:
        return {}

    recent = draws[:window]
    older = draws[window:window*2]

    trends = {}
    for n in range(min_n, max_n + 1):
        recent_count = sum(1 for d in recent if n in d.get("numbers", []))
        older_count = sum(1 for d in older if n in d.get("numbers", []))

        if older_count == 0 and recent_count > 0:
            trend = "RISING"
        elif recent_count == 0 and older_count > 0:
            trend = "FALLING"
        elif recent_count > older_count:
            trend = "RISING"
        elif recent_count < older_count:
            trend = "FALLING"
        else:
            trend = "STABLE"

        trends[n] = {
            "recent": recent_count,
            "older": older_count,
            "trend": trend
        }

    return trends


# ============================================================
# GERADOR DE PREDICOES (ATUALIZADO v7)
# ============================================================

def generate_prediction(lottery_type, draws, num_games=5):
    """Gera predicoes baseadas em analise estatistica avancada."""
    config = LOTTERY_CONFIG[lottery_type]
    num_range = config["range"]
    pick = config["pick"]
    min_n, max_n = num_range

    if len(draws) < 5:
        log_to_supabase(f"Dados insuficientes para {config['name']}.", "WARN")
        return []

    # Analises completas
    freq_analysis = analyze_frequency(draws, num_range)
    gap_analysis = analyze_gaps(draws, num_range)
    sum_dist = analyze_sum_distribution(draws)
    seq_analysis = analyze_sequences(draws, num_range)
    quad_analysis = analyze_quadrants(draws, num_range)
    trend_analysis = analyze_trends(draws, num_range)

    # Score composto: frequencia + gaps + tendencia + quadrantes
    scores = {}
    for n in range(min_n, max_n + 1):
        freq_score = freq_analysis.get(n, {}).get("frequency", 0) * 35
        gap_score = min(gap_analysis.get(n, 0) / max(len(draws), 1), 1) * 25
        deviation = freq_analysis.get(n, {}).get("deviation", 0)
        balance_score = (1 - abs(deviation)) * 20

        # Bonus de tendencia
        trend_info = trend_analysis.get(n, {})
        trend_bonus = 0
        if trend_info.get("trend") == "RISING":
            trend_bonus = 10
        elif trend_info.get("trend") == "FALLING":
            trend_bonus = -5

        # Bonus de quadrante (numeros do quadrante menos ativo ganham bonus)
        quad_bonus = 0
        least_active_q = quad_analysis.get("least_active", "Q1")
        q_ranges = quad_analysis.get("quadrant_ranges", {})
        if least_active_q in q_ranges:
            q_min, q_max = q_ranges[least_active_q]
            if q_min <= n <= q_max:
                quad_bonus = 10

        even_bonus = 15 if n % 2 == 0 else 0  # Bonus para numeros pares
        scores[n] = max(0, freq_score + gap_score + balance_score + trend_bonus + quad_bonus + even_bonus)

    # Gerar jogos
    predictions = []
    for game_idx in range(num_games):
        game_numbers = []
        available = list(range(min_n, max_n + 1))
        weights = [scores.get(n, 0) + random.uniform(0, 8) for n in available]

        for _ in range(pick):
            if not available:
                break
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


def save_predictions(lottery_type, predictions, engine="SIAOL-PRO-v7-MultiAI"):
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
        confidence = 0.5
        if pred.get("ai_enhanced"):
            consensus_count = pred.get("consensus_count", 0)
            confidence = min(0.5 + (consensus_count * 0.05), 0.95)

        payload = {
            "lottery_type": lottery_type,
            "predicted_numbers": pred["numbers"],
            "confidence": confidence,
            "metadata": {
                "game_number": pred.get("game_number", 0),
                "sum": pred.get("sum", 0),
                "sum_in_range": pred.get("sum_in_range", False),
                "even_odd": f"{pred.get('even_count', 0)}P/{pred.get('odd_count', 0)}I",
                "consensus_count": pred.get("consensus_count", 0),
                "ai_enhanced": pred.get("ai_enhanced", False),
                "generated_at": datetime.now().isoformat(),
                "engine": engine
            }
        }
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=10)
            if resp.status_code != 201:
                print(f"Erro ao salvar predicao: {resp.status_code}")
        except Exception as e:
            print(f"Erro ao salvar predicao: {e}")

    return True


def get_stat_summary(draws, num_range):
    """Retorna resumo estatistico para enviar ao ai_brain."""
    freq = analyze_frequency(draws, num_range)
    gaps = analyze_gaps(draws, num_range)
    sum_dist = analyze_sum_distribution(draws)

    hot = sorted(freq.items(), key=lambda x: x[1]["count"], reverse=True)[:10]
    cold = sorted(freq.items(), key=lambda x: x[1]["count"])[:10]
    high_gaps = sorted(gaps.items(), key=lambda x: x[1], reverse=True)[:10]

    return {
        "hot_numbers": [n for n, _ in hot],
        "cold_numbers": [n for n, _ in cold],
        "sum_mean": sum_dist.get("mean", 0),
        "sum_std": sum_dist.get("std", 0),
        "sum_target_range": list(sum_dist.get("target_range", (0, 0))),
        "high_gaps": [{"number": n, "gap": g} for n, g in high_gaps],
    }


def run_analysis(lottery_type):
    """Executa analise completa para uma loteria (estatistica pura)."""
    config = LOTTERY_CONFIG[lottery_type]
    print(f"\n=== Analise Estatistica {config['name']} ===")

    draws = fetch_historical_data(lottery_type, 200)
    if len(draws) < 5:
        print(f"  Dados insuficientes ({len(draws)} sorteios). Pulando.")
        return None

    print(f"  {len(draws)} sorteios carregados.")

    # Analises completas
    freq = analyze_frequency(draws, config["range"])
    gaps = analyze_gaps(draws, config["range"])
    sum_dist = analyze_sum_distribution(draws)
    even_odd = analyze_even_odd(draws)
    sequences = analyze_sequences(draws, config["range"])
    quadrants = analyze_quadrants(draws, config["range"])
    trends = analyze_trends(draws, config["range"])

    # Top numeros
    hot_numbers = sorted(freq.items(), key=lambda x: x[1]["count"], reverse=True)[:10]
    cold_numbers = sorted(freq.items(), key=lambda x: x[1]["count"])[:10]
    high_gap = sorted(gaps.items(), key=lambda x: x[1], reverse=True)[:10]

    # Numeros em tendencia de alta
    rising = [n for n, info in trends.items() if info.get("trend") == "RISING"]

    print(f"  Numeros quentes: {[n for n, _ in hot_numbers]}")
    print(f"  Numeros frios: {[n for n, _ in cold_numbers]}")
    print(f"  Maior gap: {[f'{n}({g})' for n, g in high_gap[:5]]}")
    print(f"  Soma media: {sum_dist['mean']} (range: {sum_dist.get('target_range', 'N/A')})")
    print(f"  Consecutivos: {sequences['consecutive_pairs_pct']}% pares, {sequences['consecutive_trios_pct']}% trios")
    print(f"  Quadrante mais ativo: {quadrants['most_active']} ({quadrants['distribution_pct']})")
    print(f"  Numeros em ALTA: {rising[:10]}")

    # Gerar predicoes
    predictions = generate_prediction(lottery_type, draws, num_games=5)
    if predictions:
        save_predictions(lottery_type, predictions, engine="SIAOL-PRO-v7-Stats")
        print(f"  {len(predictions)} predicoes estatisticas geradas e salvas.")
        for p in predictions:
            print(f"    Jogo {p['game_number']}: {p['numbers']} (soma={p['sum']}, {p['even_count']}P/{p['odd_count']}I)")

    return {
        "lottery": config["name"],
        "draws_analyzed": len(draws),
        "draws": draws,
        "hot_numbers": [n for n, _ in hot_numbers],
        "cold_numbers": [n for n, _ in cold_numbers],
        "sum_stats": sum_dist,
        "predictions": predictions,
        "stat_summary": get_stat_summary(draws, config["range"]),
    }


def run_all_analyses():
    """Executa analise para todas as loterias."""
    log_to_supabase("Iniciando ciclo de analise ML v7 para todas as loterias.")
    results = {}

    for lottery_type in LOTTERY_CONFIG:
        result = run_analysis(lottery_type)
        if result:
            results[lottery_type] = result

    summary = f"Analise ML v7 concluida. Loterias analisadas: {len(results)}"
    print(f"\n{summary}")
    log_to_supabase(summary)
    return results


if __name__ == "__main__":
    run_all_analyses()
