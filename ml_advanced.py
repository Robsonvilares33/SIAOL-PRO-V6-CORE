"""
SIAOL-PRO v8 - Motor de Machine Learning Avancado
Tecnicas implementadas:
  1. Cadeias de Markov (probabilidade condicional entre numeros)
  2. Janela Deslizante Ponderada (pesos maiores para sorteios recentes)
  3. Deteccao de Ciclos (padroes que se repetem a cada N sorteios)
  4. Ensemble Ponderado (combina todas as analises com pesos calibrados)
  5. Filtragem Inteligente (soma, par/impar, quadrantes dentro do ideal)
  6. Backtesting (valida predicoes contra dados reais)

REQUER: 500+ registros historicos para resultados otimos.
"""
import os
import json
import math
import random
from datetime import datetime
from collections import Counter, defaultdict
from dotenv import load_dotenv

load_dotenv()

LOTTERY_CONFIG = {
    "megasena": {"name": "Mega-Sena", "range": (1, 60), "pick": 6},
    "lotofacil": {"name": "Lotofacil", "range": (1, 25), "pick": 15},
    "quina": {"name": "Quina", "range": (1, 80), "pick": 5},
    "lotomania": {"name": "Lotomania", "range": (0, 99), "pick": 20},
}


# ============================================================
# 1. CADEIA DE MARKOV
# ============================================================

def build_markov_matrix(draws, num_range):
    """Constroi matriz de transicao de Markov entre numeros."""
    min_n, max_n = num_range
    total_nums = max_n - min_n + 1
    # transitions[a][b] = quantas vezes b apareceu no sorteio SEGUINTE ao que a apareceu
    transitions = defaultdict(lambda: defaultdict(int))

    for i in range(len(draws) - 1):
        current_nums = set(draws[i].get("numbers", []))
        next_nums = set(draws[i + 1].get("numbers", []))

        for a in current_nums:
            for b in next_nums:
                transitions[a][b] += 1

    # Normalizar para probabilidades
    markov = {}
    for a in transitions:
        total = sum(transitions[a].values())
        if total > 0:
            markov[a] = {b: count / total for b, count in transitions[a].items()}

    return markov


def markov_predict(markov, last_draw_numbers, num_range, top_n=30):
    """Usa Markov para prever numeros mais provaveis baseado no ultimo sorteio."""
    min_n, max_n = num_range
    scores = defaultdict(float)

    for num in last_draw_numbers:
        if num in markov:
            for next_num, prob in markov[num].items():
                if min_n <= next_num <= max_n:
                    scores[next_num] += prob

    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return sorted_scores[:top_n]


# ============================================================
# 2. JANELA DESLIZANTE PONDERADA
# ============================================================

def sliding_window_analysis(draws, num_range, windows=[10, 20, 50, 100]):
    """Analisa frequencia em multiplas janelas com pesos decrescentes."""
    min_n, max_n = num_range
    scores = defaultdict(float)

    # Pesos: janela menor = peso maior (sorteios recentes importam mais)
    weight_map = {10: 4.0, 20: 3.0, 50: 2.0, 100: 1.0}

    for window_size in windows:
        if len(draws) < window_size:
            continue

        window_draws = draws[:window_size]
        weight = weight_map.get(window_size, 1.0)

        freq = Counter()
        for draw in window_draws:
            for n in draw.get("numbers", []):
                freq[n] += 1

        total = len(window_draws)
        for n in range(min_n, max_n + 1):
            count = freq.get(n, 0)
            expected = total / (max_n - min_n + 1)
            # Score = desvio relativo ponderado
            if expected > 0:
                deviation = (count - expected) / expected
                scores[n] += deviation * weight

    return dict(scores)


# ============================================================
# 3. DETECCAO DE CICLOS
# ============================================================

def detect_cycles(draws, num_range, max_cycle=30):
    """Detecta padroes ciclicos na aparicao de cada numero."""
    min_n, max_n = num_range
    cycles = {}

    for n in range(min_n, max_n + 1):
        appearances = []
        for i, draw in enumerate(draws):
            if n in draw.get("numbers", []):
                appearances.append(i)

        if len(appearances) < 3:
            continue

        # Calcular intervalos entre aparicoes
        intervals = []
        for j in range(1, len(appearances)):
            intervals.append(appearances[j] - appearances[j-1])

        if not intervals:
            continue

        avg_interval = sum(intervals) / len(intervals)
        # Desvio padrao dos intervalos
        variance = sum((i - avg_interval) ** 2 for i in intervals) / len(intervals)
        std_interval = math.sqrt(variance)

        # Um numero tem ciclo se o desvio padrao e baixo (intervalos regulares)
        regularity = 1 - min(std_interval / max(avg_interval, 1), 1)

        # Proximo aparecimento estimado
        last_seen = appearances[0]  # posicao no array (0 = mais recente)
        expected_next = avg_interval - last_seen

        cycles[n] = {
            "avg_interval": round(avg_interval, 2),
            "std_interval": round(std_interval, 2),
            "regularity": round(regularity, 4),
            "last_seen_ago": last_seen,
            "expected_in": round(expected_next, 1),
            "is_due": expected_next <= 1,  # "Deveria" aparecer no proximo sorteio
        }

    return cycles


# ============================================================
# 4. ENSEMBLE PONDERADO
# ============================================================

def ensemble_score(num, freq_score, gap_score, markov_score, window_score,
                   cycle_info, trend_score, weights=None):
    """Combina todas as analises com pesos calibrados."""
    if weights is None:
        weights = {
            "frequency": 0.20,
            "gaps": 0.15,
            "markov": 0.20,
            "window": 0.20,
            "cycle": 0.10,
            "trend": 0.15,
        }

    score = 0
    score += freq_score * weights["frequency"]
    score += gap_score * weights["gaps"]
    score += markov_score * weights["markov"]
    score += window_score * weights["window"]

    if cycle_info:
        cycle_bonus = cycle_info.get("regularity", 0)
        if cycle_info.get("is_due", False):
            cycle_bonus *= 2  # Dobra se esta "devido"
        score += cycle_bonus * weights["cycle"]

    score += trend_score * weights["trend"]

    return score


# ============================================================
# 5. FILTRAGEM INTELIGENTE
# ============================================================

def filter_game(numbers, lottery_type, sum_stats, even_odd_ideal):
    """Verifica se um jogo atende aos criterios de qualidade."""
    config = LOTTERY_CONFIG[lottery_type]
    pick = config["pick"]

    if len(numbers) != pick:
        return False

    game_sum = sum(numbers)
    target_min = sum_stats.get("target_range", (0, 99999))[0]
    target_max = sum_stats.get("target_range", (0, 99999))[1]

    # Verificar soma
    if not (target_min <= game_sum <= target_max):
        return False

    # Verificar par/impar
    evens = sum(1 for n in numbers if n % 2 == 0)
    odds = pick - evens
    ideal_even, ideal_odd = even_odd_ideal
    if abs(evens - ideal_even) > 2:
        return False

    return True


# ============================================================
# 6. GERADOR DE PREDICOES v8
# ============================================================

def generate_advanced_predictions(lottery_type, draws, num_games=5):
    """Gera predicoes usando ensemble de todas as tecnicas."""
    config = LOTTERY_CONFIG[lottery_type]
    num_range = config["range"]
    pick = config["pick"]
    min_n, max_n = num_range

    if len(draws) < 10:
        return [], {}

    # === Executar TODAS as analises ===

    # 1. Frequencia basica
    freq = Counter()
    for draw in draws:
        for n in draw.get("numbers", []):
            freq[n] += 1
    total_draws = len(draws)

    # 2. Gaps
    gaps = {}
    for n in range(min_n, max_n + 1):
        gap = 0
        for draw in draws:
            if n in draw.get("numbers", []):
                break
            gap += 1
        gaps[n] = gap

    # 3. Markov
    markov = build_markov_matrix(draws, num_range)
    last_numbers = draws[0].get("numbers", []) if draws else []
    markov_predictions = markov_predict(markov, last_numbers, num_range, 40)
    markov_scores = {n: s for n, s in markov_predictions}
    max_markov = max(markov_scores.values()) if markov_scores else 1

    # 4. Janela Deslizante
    window_scores = sliding_window_analysis(draws, num_range)
    max_window = max(abs(v) for v in window_scores.values()) if window_scores else 1

    # 5. Ciclos
    cycles = detect_cycles(draws, num_range)

    # 6. Tendencias (ultimos 10 vs anteriores 10)
    trend_scores = {}
    if len(draws) >= 20:
        recent = draws[:10]
        older = draws[10:20]
        for n in range(min_n, max_n + 1):
            r_count = sum(1 for d in recent if n in d.get("numbers", []))
            o_count = sum(1 for d in older if n in d.get("numbers", []))
            trend_scores[n] = (r_count - o_count) / max(o_count, 1)

    # 7. Distribuicao de soma
    sums = [sum(d.get("numbers", [])) for d in draws]
    mean_sum = sum(sums) / len(sums) if sums else 0
    std_sum = math.sqrt(sum((s - mean_sum)**2 for s in sums) / len(sums)) if sums else 0
    sum_stats = {"target_range": (round(mean_sum - std_sum), round(mean_sum + std_sum))}

    # 8. Par/Impar ideal
    even_odd_counts = []
    for draw in draws:
        nums = draw.get("numbers", [])
        evens = sum(1 for n in nums if n % 2 == 0)
        even_odd_counts.append(evens)
    ideal_even = round(sum(even_odd_counts) / len(even_odd_counts)) if even_odd_counts else pick // 2
    ideal_odd = pick - ideal_even

    # === CALCULAR SCORE ENSEMBLE PARA CADA NUMERO ===
    final_scores = {}
    for n in range(min_n, max_n + 1):
        f_score = freq.get(n, 0) / max(total_draws, 1)
        g_score = min(gaps.get(n, 0) / max(total_draws * 0.1, 1), 1)
        m_score = markov_scores.get(n, 0) / max(max_markov, 0.001)
        w_score = (window_scores.get(n, 0) / max(max_window, 0.001) + 1) / 2  # Normalizar 0-1
        c_info = cycles.get(n, None)
        t_score = (trend_scores.get(n, 0) + 1) / 2  # Normalizar 0-1

        final_scores[n] = ensemble_score(n, f_score, g_score, m_score, w_score, c_info, t_score)

    # === GERAR JOGOS ===
    predictions = []
    max_attempts = num_games * 20  # Tentativas para encontrar jogos validos
    attempts = 0

    while len(predictions) < num_games and attempts < max_attempts:
        attempts += 1

        # Selecao ponderada
        available = list(range(min_n, max_n + 1))
        weights = [max(final_scores.get(n, 0), 0.01) + random.uniform(0, 0.05) for n in available]

        selected = []
        for _ in range(pick):
            if not available:
                break
            total_w = sum(weights)
            if total_w == 0:
                idx = random.randint(0, len(available) - 1)
            else:
                r = random.uniform(0, total_w)
                cumul = 0
                idx = 0
                for i, w in enumerate(weights):
                    cumul += w
                    if cumul >= r:
                        idx = i
                        break

            selected.append(available[idx])
            available.pop(idx)
            weights.pop(idx)

        selected.sort()

        # Filtrar jogos de baixa qualidade
        if filter_game(selected, lottery_type, sum_stats, (ideal_even, ideal_odd)):
            game_sum = sum(selected)
            predictions.append({
                "game_number": len(predictions) + 1,
                "numbers": selected,
                "sum": game_sum,
                "even_count": sum(1 for n in selected if n % 2 == 0),
                "odd_count": sum(1 for n in selected if n % 2 != 0),
            })

    analysis_meta = {
        "total_draws_analyzed": total_draws,
        "markov_built": len(markov) > 0,
        "cycles_detected": sum(1 for c in cycles.values() if c.get("is_due")),
        "sum_range": sum_stats["target_range"],
        "ideal_even_odd": (ideal_even, ideal_odd),
        "top_ensemble_numbers": sorted(final_scores.items(), key=lambda x: x[1], reverse=True)[:15],
    }

    return predictions, analysis_meta


# ============================================================
# 7. BACKTESTING
# ============================================================

def backtest(lottery_type, draws, test_size=50, num_games=10):
    """
    Testa o algoritmo contra dados historicos reais.
    Usa os primeiros N sorteios como treino e os ultimos test_size como teste.
    """
    if len(draws) < test_size + 50:
        return None

    config = LOTTERY_CONFIG[lottery_type]
    pick = config["pick"]

    results = []

    for t in range(test_size):
        # Dados de treino = tudo DEPOIS do sorteio de teste
        test_draw = draws[t]
        train_draws = draws[t + 1:]

        if len(train_draws) < 50:
            break

        # Gerar predicoes usando dados de treino
        predictions, _ = generate_advanced_predictions(lottery_type, train_draws, num_games)

        real_numbers = set(test_draw.get("numbers", []))

        # Melhor match
        best_match = 0
        for pred in predictions:
            pred_numbers = set(pred["numbers"])
            match = len(real_numbers & pred_numbers)
            best_match = max(best_match, match)

        accuracy = best_match / pick if pick > 0 else 0
        results.append({
            "draw_number": test_draw.get("draw_number", 0),
            "best_match": best_match,
            "total": pick,
            "accuracy": round(accuracy, 4),
        })

    if not results:
        return None

    avg_match = sum(r["best_match"] for r in results) / len(results)
    avg_accuracy = sum(r["accuracy"] for r in results) / len(results)
    best_ever = max(r["best_match"] for r in results)
    worst_ever = min(r["best_match"] for r in results)

    return {
        "lottery": config["name"],
        "test_size": len(results),
        "avg_match": round(avg_match, 2),
        "avg_accuracy_pct": round(avg_accuracy * 100, 1),
        "best_match": best_ever,
        "worst_match": worst_ever,
        "pick": pick,
    }


# ============================================================
# TESTE STANDALONE
# ============================================================

if __name__ == "__main__":
    import requests

    SUPABASE_URL_ENV = os.getenv("SUPABASE_URL")
    SUPABASE_KEY_ENV = os.getenv("SUPABASE_KEY")

    print("=" * 60)
    print("  SIAOL-PRO v8 - Motor ML Avancado - Teste")
    print("=" * 60)

    for lottery_type in LOTTERY_CONFIG:
        config = LOTTERY_CONFIG[lottery_type]
        print(f"\n--- {config['name']} ---")

        # Buscar dados
        url = (f"{SUPABASE_URL_ENV}/rest/v1/lottery_data"
               f"?lottery_type=eq.{lottery_type}"
               f"&order=draw_number.desc"
               f"&limit=2000"
               f"&select=draw_number,draw_date,numbers")
        headers = {
            "apikey": SUPABASE_KEY_ENV,
            "Authorization": f"Bearer {SUPABASE_KEY_ENV}"
        }
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code != 200:
            print(f"  Erro ao buscar dados: {resp.status_code}")
            continue

        draws = resp.json()
        print(f"  Registros disponiveis: {len(draws)}")

        if len(draws) < 10:
            print(f"  Dados insuficientes. Execute backfill_collector.py primeiro!")
            continue

        # Gerar predicoes
        predictions, meta = generate_advanced_predictions(lottery_type, draws, 5)
        print(f"  Predicoes geradas: {len(predictions)}")
        print(f"  Markov ativo: {meta.get('markov_built')}")
        print(f"  Ciclos devidos: {meta.get('cycles_detected')}")
        print(f"  Top nums ensemble: {[n for n, s in meta.get('top_ensemble_numbers', [])[:10]]}")

        for p in predictions:
            print(f"    Jogo {p['game_number']}: {p['numbers']} "
                  f"(soma={p['sum']}, {p['even_count']}P/{p['odd_count']}I)")

        # Backtesting
        if len(draws) >= 100:
            bt = backtest(lottery_type, draws, test_size=30, num_games=10)
            if bt:
                print(f"  BACKTEST: {bt['avg_match']:.1f}/{bt['pick']} media "
                      f"({bt['avg_accuracy_pct']:.1f}%) | Melhor: {bt['best_match']} | "
                      f"Pior: {bt['worst_match']}")

    print(f"\n{'='*60}")
    print("  TESTE CONCLUIDO")
    print(f"{'='*60}")
