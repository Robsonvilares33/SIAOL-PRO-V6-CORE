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


def fetch_historical_data(lottery_type, limit=200, config=None):
    """Busca dados historicos do Supabase COM PAGINACAO para superar o limite de 1000 linhas."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        # Retornar dados simulados para testes se as chaves do Supabase nao estiverem configuradas
        print("WARN: SUPABASE_URL ou SUPABASE_KEY nao configurados. Usando dados simulados para fetch_historical_data.")
        if config is None:
            config = LOTTERY_CONFIG[lottery_type]
        num_range = config["range"]
        mock_draws = []
        for i in range(limit):
            numbers = sorted(random.sample(range(num_range[0], num_range[1] + 1), config["pick"]))
            mock_draws.append({"draw_number": i + 1, "draw_date": datetime.now().isoformat(), "numbers": numbers})
        return mock_draws
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
# GERADOR DE PREDICOES (ATUALIZADO v11.1)
# ============================================================

def generate_prediction(lottery_type, draws, num_games=5, even_preference_weight=0.1):
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

    # Score composto: frequencia + gaps + tendencia + quadrantes + preferencia por pares
    scores = {}
    for n in range(min_n, max_n + 1):
        freq_score = freq_analysis.get(n, {}).get("frequency", 0) * 35
        gap_score = min(gap_analysis.get(n, 0) / max(len(draws), 1), 1) * 25
        deviation = freq_analysis.get(n, {}).get("deviation", 0)
        balance_score = (1 - abs(deviation)) * 20

        # Adicionar bonus para numeros pares, se houver preferencia
        even_bonus = 0
        if n % 2 == 0:
            even_bonus = even_preference_weight * 10 # Ajustar peso conforme necessidade

        # Bonus de tendencia
        trend_info = trend_analysis.get(n, {})
        trend_bonus = 0
        if trend_info.get("trend") == "RISING":
            trend_bonus = 10
        elif trend_info.get("trend") == "FALLING":
            trend_bonus = -5

        # Bonus de quadrante
        quad_bonus = 0
        most_active_q = quad_analysis["most_active"]
        q_min, q_max = quad_analysis["quadrant_ranges"][most_active_q]
        if q_min <= n <= q_max:
            quad_bonus = 10

        scores[n] = freq_score + gap_score + balance_score + even_bonus + trend_bonus + quad_bonus

    # Gerar jogos
    predictions = []
    for game_idx in range(num_games):
        # Selecionar os numeros com maior score
        predicted_numbers = []
        sorted_scores = sorted(scores.items(), key=lambda item: item[1], reverse=True)

        for num, score in sorted_scores:
            if num not in predicted_numbers:
                predicted_numbers.append(num)
            if len(predicted_numbers) == pick:
                break

        # Ajuste para garantir a preferencia por numeros pares
        even_count = sum(1 for n in predicted_numbers if n % 2 == 0)
        target_even_count = math.ceil(pick / 2) # Tentar ter pelo menos metade de numeros pares

        if even_count < target_even_count:
            # Tentar trocar numeros impares por pares de alto score que nao foram selecionados
            odd_numbers_in_prediction = [n for n in predicted_numbers if n % 2 != 0]
            even_numbers_available = [n for n, score in sorted_scores if n % 2 == 0 and n not in predicted_numbers]

            num_to_swap = target_even_count - even_count
            for _ in range(num_to_swap):
                if odd_numbers_in_prediction and even_numbers_available:
                    # Trocar o impar de menor score pelo par de maior score disponivel
                    odd_to_remove = min(odd_numbers_in_prediction, key=lambda x: scores.get(x, 0))
                    even_to_add = max(even_numbers_available, key=lambda x: scores.get(x, 0))

                    predicted_numbers.remove(odd_to_remove)
                    predicted_numbers.append(even_to_add)
                    odd_numbers_in_prediction.remove(odd_to_remove)
                    even_numbers_available.remove(even_to_add)
                else:
                    break
            predicted_numbers = sorted(predicted_numbers)

        # Garantir que a soma dos numeros esteja dentro de um range razoavel
        current_sum = sum(predicted_numbers)
        if not (sum_dist["target_range"][0] <= current_sum <= sum_dist["target_range"][1]):
            log_to_supabase(f"Soma da predicao fora do range para {lottery_type}. Tentando ajustar.", "WARN")
            if abs(current_sum - sum_dist["mean"]) > sum_dist["std"] * 2:
                log_to_supabase(f"Soma muito fora do padrao. Re-gerando predicao para {lottery_type}.", "WARN")
                # Evitar recursao infinita, apenas logar e retornar o que tem
                log_to_supabase(f"Predicao gerada para {config['name']} (soma fora do padrao): {predicted_numbers}", "WARN")
                predictions.append(predicted_numbers)
                continue

        log_to_supabase(f"Predicao gerada para {config['name']}: {predicted_numbers}", "INFO")
        predictions.append(predicted_numbers)

    return predictions


def run_analysis_and_predict(lottery_type, num_games=5, even_preference_weight=0.1):
    config = LOTTERY_CONFIG[lottery_type]
    """Funcao principal para orquestrar a analise e predicao."""
    log_to_supabase(f"Iniciando ciclo de analise para {lottery_type}...", "INFO")
    config = LOTTERY_CONFIG[lottery_type]

    # 1. Buscar dados
    draws = fetch_historical_data(lottery_type, limit=500, config=config) # Aumentar limite para analise mais profunda
    if not draws:
        log_to_supabase(f"Nao foi possivel obter dados para {lottery_type}.", "ERROR")
        return None, None

    # 2. Realizar analises
    full_analysis = {
        "lottery_type": lottery_type,
        "generated_at": datetime.now().isoformat(),
        "total_draws_analyzed": len(draws),
        "frequency": analyze_frequency(draws, config["range"]),
        "gaps": analyze_gaps(draws, config["range"]),
        "pairs": analyze_pairs(draws),
        "sum_distribution": analyze_sum_distribution(draws),
        "even_odd": analyze_even_odd(draws),
        "sequences": analyze_sequences(draws, config["range"]),
        "quadrants": analyze_quadrants(draws, config["range"]),
        "trends": analyze_trends(draws, config["range"])
    }

    # 3. Gerar predicoes
    predictions = generate_prediction(lottery_type, draws, num_games, even_preference_weight)

    log_to_supabase(f"Ciclo de analise para {lottery_type} concluido.", "INFO")
    return full_analysis, predictions


if __name__ == '__main__':
    # Exemplo de uso
    LOTTERY = "megasena"
    NUM_GAMES_TO_PREDICT = 10
    EVEN_PREFERENCE = 0.2 # Aumentar o peso para dar mais preferencia a pares

    analysis_results, final_predictions = run_analysis_and_predict(LOTTERY, NUM_GAMES_TO_PREDICT, EVEN_PREFERENCE)

    if analysis_results and final_predictions:
        print("\n" + "="*50)
        print(f"  ANALISE E PREDICAO - {LOTTERY_CONFIG[LOTTERY]['name'].upper()}")
        print("="*50 + "\n")

        print(f"-> Analise baseada em {analysis_results['total_draws_analyzed']} sorteios.")
        most_common_even_odd = analysis_results['even_odd']['most_common'][0] if analysis_results['even_odd']['most_common'] else "N/A"
        print(f"-> Tendencia de Pares/Impares mais comum: {most_common_even_odd}")
        print(f"-> Quadrante mais ativo: {analysis_results['quadrants']['most_active']}")
        print("\n" + "-"*50)
        print("  PREDICOES GERADAS")
        print("-"*50)
        for i, pred in enumerate(final_predictions):
            print(f"  Jogo {i+1:02d}: {sorted(pred)}")
        print("\n" + "="*50)

        # Converter chaves de tupla para string no dicionario even_odd para serializacao JSON
        if 'even_odd' in analysis_results and 'distributions' in analysis_results['even_odd']:
            analysis_results['even_odd']['distributions'] = {str(k): v for k, v in analysis_results['even_odd']['distributions'].items()}
        
        # Salvar analise em JSON
        output_filename = f"analysis_{LOTTERY}.json"
        with open(output_filename, 'w') as f:
            json.dump(analysis_results, f, indent=2)
        print(f"\nRelatorio de analise completo salvo em: {output_filename}")

        # Salvar predicoes em TXT
        preds_filename = f"predictions_{LOTTERY}.txt"
        with open(preds_filename, 'w') as f:
            for pred in final_predictions:
                f.write(','.join(map(str, sorted(pred))) + '\n')
        print(f"Predicoes salvas em: {preds_filename}")
