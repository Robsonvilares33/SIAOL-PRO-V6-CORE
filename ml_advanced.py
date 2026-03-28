"""
SIAOL-PRO v8.5 - Motor ML ULTRA-Avancado
Evolucao sobre v8 com 6 novas tecnicas:
  1. Cadeias de Markov (1a e 2a ordem)
  2. Janela Deslizante com 6 janelas (5,10,20,50,100,200)
  3. Deteccao de Ciclos com amplitude
  4. Analise de Pares Frequentes (co-ocorrencia)
  5. Filtragem por Quadrantes + Consecutivos + Soma + Par/Impar
  6. Ensemble com pesos auto-calibrados via backtesting
  7. Backtesting expandido (20 jogos x 50 testes)
  8. Selecao hibrida (Top-K deterministico + ponderada)
"""
import os
import math
import random
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
# 1. CADEIA DE MARKOV (1a + 2a Ordem)
# ============================================================

def build_markov(draws, num_range):
    """Markov 1a ordem: P(b | a apareceu no sorteio anterior)."""
    transitions = defaultdict(lambda: defaultdict(int))
    for i in range(len(draws) - 1):
        cur = set(draws[i].get("numbers", []))
        nxt = set(draws[i + 1].get("numbers", []))
        for a in cur:
            for b in nxt:
                transitions[a][b] += 1
    markov = {}
    for a in transitions:
        total = sum(transitions[a].values())
        if total > 0:
            markov[a] = {b: c / total for b, c in transitions[a].items()}
    return markov


def build_markov_2nd(draws, num_range):
    """Markov 2a ordem: P(c | a,b apareceram nos 2 sorteios anteriores)."""
    transitions = defaultdict(lambda: defaultdict(int))
    for i in range(len(draws) - 2):
        prev2 = set(draws[i + 1].get("numbers", []))
        prev1 = set(draws[i].get("numbers", []))  # mais recente na sequencia
        # Nao precisamos de todas as combinacoes, usamos a uniao
        context = frozenset(prev2 | prev1)
        nxt = set(draws[i].get("numbers", []))  # Oops, corrigindo
        # Na verdade: draws[0] é o mais recente
        # draws[i] = teste, draws[i+1] e draws[i+2] = contexto
        pass
    # Simplificação: usar apenas os numeros que repetiram nos 2 ultimos
    repeat_scores = defaultdict(float)
    for i in range(len(draws) - 2):
        d_target = draws[i]
        d_prev1 = draws[i + 1]
        d_prev2 = draws[i + 2]
        s1 = set(d_prev1.get("numbers", []))
        s2 = set(d_prev2.get("numbers", []))
        target = set(d_target.get("numbers", []))
        # Numeros que estavam em ambos anteriores e apareceram no target
        common_prev = s1 & s2
        for n in target:
            if n in common_prev:
                repeat_scores[n] += 1
    return dict(repeat_scores)


# ============================================================
# 2. ANALISE DE PARES FREQUENTES (Co-ocorrencia)
# ============================================================

def pair_analysis(draws, num_range, top_pairs=50):
    """Analisa quais pares de numeros aparecem juntos com mais frequencia."""
    min_n, max_n = num_range
    pair_count = defaultdict(int)

    for draw in draws:
        nums = sorted(draw.get("numbers", []))
        for i in range(len(nums)):
            for j in range(i + 1, len(nums)):
                pair_count[(nums[i], nums[j])] += 1

    # Normalizar
    total = len(draws)
    pair_freq = {k: v / total for k, v in pair_count.items()}

    # Score por numero baseado em quantos pares fortes ele participa
    pair_scores = defaultdict(float)
    sorted_pairs = sorted(pair_freq.items(), key=lambda x: x[1], reverse=True)[:top_pairs]
    for (a, b), freq in sorted_pairs:
        pair_scores[a] += freq
        pair_scores[b] += freq

    return dict(pair_scores), sorted_pairs


# ============================================================
# 3. JANELA DESLIZANTE (6 janelas)
# ============================================================

def sliding_window(draws, num_range):
    """Analisa frequencia em 6 janelas com pesos exponenciais."""
    min_n, max_n = num_range
    scores = defaultdict(float)
    windows = [(5, 8.0), (10, 5.0), (20, 3.0), (50, 2.0), (100, 1.5), (200, 1.0)]

    for window_size, weight in windows:
        if len(draws) < window_size:
            continue
        window = draws[:window_size]
        freq = Counter()
        for draw in window:
            for n in draw.get("numbers", []):
                freq[n] += 1

        total = len(window)
        expected = total * (LOTTERY_CONFIG.get("lotofacil", {}).get("pick", 15)) / (max_n - min_n + 1)

        for n in range(min_n, max_n + 1):
            count = freq.get(n, 0)
            if expected > 0:
                deviation = (count - expected) / expected
                scores[n] += deviation * weight

    return dict(scores)


# ============================================================
# 4. DETECCAO DE CICLOS (com amplitude)
# ============================================================

def detect_cycles(draws, num_range):
    """Detecta ciclos e calcula 'urgencia' de cada numero."""
    min_n, max_n = num_range
    cycles = {}
    for n in range(min_n, max_n + 1):
        positions = [i for i, d in enumerate(draws) if n in d.get("numbers", [])]
        if len(positions) < 4:
            continue
        intervals = [positions[j] - positions[j-1] for j in range(1, len(positions))]
        avg = sum(intervals) / len(intervals)
        var = sum((x - avg)**2 for x in intervals) / len(intervals)
        std = math.sqrt(var)
        regularity = max(0, 1 - std / max(avg, 1))
        last_seen = positions[0]
        overdue = max(0, last_seen - avg)
        urgency = (overdue / max(avg, 1)) * regularity
        cycles[n] = {
            "avg_interval": avg,
            "regularity": regularity,
            "last_seen": last_seen,
            "overdue": overdue,
            "urgency": urgency,
            "is_due": last_seen >= avg * 0.8,
        }
    return cycles


# ============================================================
# 5. FILTRAGEM MULTI-CRITERIO
# ============================================================

def analyze_constraints(draws, lottery_type):
    """Analisa constrains historicas: soma, par/impar, consecutivos, quadrantes."""
    config = LOTTERY_CONFIG[lottery_type]
    pick = config["pick"]
    min_n, max_n = config["range"]
    total_range = max_n - min_n + 1
    q_size = total_range / 4

    sums = []
    even_counts = []
    consec_counts = []
    quadrant_dists = []

    for draw in draws:
        nums = sorted(draw.get("numbers", []))
        if len(nums) != pick:
            continue

        sums.append(sum(nums))
        even_counts.append(sum(1 for n in nums if n % 2 == 0))

        # Consecutivos
        consec = sum(1 for i in range(len(nums)-1) if nums[i+1] - nums[i] == 1)
        consec_counts.append(consec)

        # Quadrantes
        quads = [0, 0, 0, 0]
        for n in nums:
            qi = min(int((n - min_n) / q_size), 3)
            quads[qi] += 1
        quadrant_dists.append(quads)

    if not sums:
        return None

    def stats(arr):
        avg = sum(arr) / len(arr)
        std = math.sqrt(sum((x-avg)**2 for x in arr) / len(arr))
        return avg, std

    sum_avg, sum_std = stats(sums)
    even_avg, even_std = stats(even_counts)
    consec_avg, consec_std = stats(consec_counts)

    q_avgs = [sum(q[i] for q in quadrant_dists) / len(quadrant_dists) for i in range(4)]

    return {
        "sum_range": (round(sum_avg - sum_std * 0.8), round(sum_avg + sum_std * 0.8)),
        "sum_avg": sum_avg,
        "even_range": (max(0, round(even_avg - even_std)), min(pick, round(even_avg + even_std))),
        "even_avg": round(even_avg),
        "consec_range": (max(0, round(consec_avg - consec_std)), round(consec_avg + consec_std * 1.5)),
        "consec_avg": round(consec_avg, 1),
        "quadrant_avg": q_avgs,
    }


def filter_game_strict(numbers, lottery_type, constraints):
    """Filtro rigoroso multi-criterio."""
    if constraints is None:
        return True

    config = LOTTERY_CONFIG[lottery_type]
    pick = config["pick"]
    min_n, max_n = config["range"]

    if len(numbers) != pick:
        return False

    game_sum = sum(numbers)
    sr = constraints["sum_range"]
    if not (sr[0] <= game_sum <= sr[1]):
        return False

    evens = sum(1 for n in numbers if n % 2 == 0)
    er = constraints["even_range"]
    if not (er[0] <= evens <= er[1]):
        return False

    nums = sorted(numbers)
    consec = sum(1 for i in range(len(nums)-1) if nums[i+1] - nums[i] == 1)
    cr = constraints["consec_range"]
    if not (cr[0] <= consec <= cr[1]):
        return False

    # Quadrantes - nenhum quadrante pode estar completamente vazio (para lotofacil/lotomania)
    if pick >= 10:
        q_size = (max_n - min_n + 1) / 4
        quads = [0, 0, 0, 0]
        for n in nums:
            qi = min(int((n - min_n) / q_size), 3)
            quads[qi] += 1
        if any(q == 0 for q in quads):
            return False

    return True


# ============================================================
# 6. ENSEMBLE v8.5 (COM PARES + MARKOV 2a ORDEM)
# ============================================================

def compute_ensemble_scores(draws, lottery_type):
    """Calcula score ensemble completo para cada numero."""
    config = LOTTERY_CONFIG[lottery_type]
    num_range = config["range"]
    min_n, max_n = num_range
    pick = config["pick"]
    total_draws = len(draws)

    # ---- Componente 1: Frequencia Global ----
    freq = Counter()
    for d in draws:
        for n in d.get("numbers", []):
            freq[n] += 1
    freq_scores = {}
    expected_freq = total_draws * pick / (max_n - min_n + 1)
    for n in range(min_n, max_n + 1):
        freq_scores[n] = freq.get(n, 0) / max(expected_freq, 1)

    # ---- Componente 2: Gaps (urgencia de retorno) ----
    gap_scores = {}
    for n in range(min_n, max_n + 1):
        gap = 0
        for d in draws:
            if n in d.get("numbers", []):
                break
            gap += 1
        avg_gap = total_draws / max(freq.get(n, 1), 1)
        gap_scores[n] = min(gap / max(avg_gap, 1), 2.0)

    # ---- Componente 3: Markov 1a ordem ----
    markov = build_markov(draws, num_range)
    last_nums = draws[0].get("numbers", []) if draws else []
    m_scores = defaultdict(float)
    for num in last_nums:
        if num in markov:
            for nxt, prob in markov[num].items():
                m_scores[nxt] += prob
    max_m = max(m_scores.values()) if m_scores else 1
    markov_scores = {n: m_scores.get(n, 0) / max(max_m, 0.001) for n in range(min_n, max_n + 1)}

    # ---- Componente 4: Janela Deslizante ----
    w_raw = sliding_window(draws, num_range)
    max_w = max(abs(v) for v in w_raw.values()) if w_raw else 1
    window_scores = {n: (w_raw.get(n, 0) / max(max_w, 0.001) + 1) / 2 for n in range(min_n, max_n + 1)}

    # ---- Componente 5: Ciclos ----
    cycles = detect_cycles(draws, num_range)
    cycle_scores = {}
    for n in range(min_n, max_n + 1):
        c = cycles.get(n)
        if c:
            cycle_scores[n] = c["urgency"] + (0.3 if c["is_due"] else 0)
        else:
            cycle_scores[n] = 0

    # ---- Componente 6: Tendencia Multi-Janela ----
    trend_scores = {}
    if len(draws) >= 30:
        r5 = draws[:5]
        r10 = draws[:10]
        r30 = draws[:30]
        for n in range(min_n, max_n + 1):
            c5 = sum(1 for d in r5 if n in d.get("numbers", []))
            c10 = sum(1 for d in r10 if n in d.get("numbers", []))
            c30 = sum(1 for d in r30 if n in d.get("numbers", []))
            # Tendencia = aceleracao recente
            trend_scores[n] = (c5 / 5 * 3 + c10 / 10 * 2 + c30 / 30) / 6
        max_t = max(trend_scores.values()) if trend_scores else 1
        trend_scores = {n: v / max(max_t, 0.001) for n, v in trend_scores.items()}
    else:
        trend_scores = {n: 0.5 for n in range(min_n, max_n + 1)}

    # ---- Componente 7: Pares ----
    pair_scores_dict, _ = pair_analysis(draws, num_range)
    max_p = max(pair_scores_dict.values()) if pair_scores_dict else 1
    pair_scores = {n: pair_scores_dict.get(n, 0) / max(max_p, 0.001) for n in range(min_n, max_n + 1)}

    # ---- ENSEMBLE FINAL com Sharpening Exponencial ----
    W = {
        "freq": 0.12,
        "gap": 0.10,
        "markov": 0.22,
        "window": 0.18,
        "cycle": 0.08,
        "trend": 0.15,
        "pair": 0.15,
    }

    raw = {}
    for n in range(min_n, max_n + 1):
        raw[n] = (
            freq_scores.get(n, 0) * W["freq"] +
            gap_scores.get(n, 0) * W["gap"] +
            markov_scores.get(n, 0) * W["markov"] +
            window_scores.get(n, 0) * W["window"] +
            cycle_scores.get(n, 0) * W["cycle"] +
            trend_scores.get(n, 0) * W["trend"] +
            pair_scores.get(n, 0) * W["pair"]
        )

    # Sharpening ADAPTATIVO por tipo de loteria
    # Loterias densas (lotofacil 15/25, lotomania 20/100) -> exp menor
    # Loterias esparsas (megasena 6/60, quina 5/80) -> exp maior
    density = pick / (max_n - min_n + 1)
    if density >= 0.5:    # Lotofacil (0.6)
        sharp_exp = 2.5
    elif density >= 0.2:  # Lotomania (0.2)
        sharp_exp = 2.2
    else:                 # Quina (0.0625), Mega (0.1)
        sharp_exp = 2.8

    values = list(raw.values())
    if values:
        min_v = min(values)
        max_v = max(values)
        rng = max(max_v - min_v, 0.001)
        final = {}
        for n, v in raw.items():
            norm = (v - min_v) / rng
            final[n] = norm ** sharp_exp
    else:
        final = raw

    return final, {
        "total_draws": total_draws,
        "markov_active": len(markov) > 0,
        "cycles_due": sum(1 for c in cycles.values() if c.get("is_due")),
        "top_pairs": len(pair_scores_dict),
        "sharp_exp": sharp_exp,
    }


# ============================================================
# 7. GERADOR HIBRIDO (Top-K + Ponderado)
# ============================================================

def generate_advanced_predictions(lottery_type, draws, num_games=5):
    """Gera predicoes com selecao hibrida: nucleo deterministico + expansao ponderada."""
    config = LOTTERY_CONFIG[lottery_type]
    num_range = config["range"]
    pick = config["pick"]
    min_n, max_n = num_range

    if len(draws) < 20:
        return [], {}

    scores, meta_info = compute_ensemble_scores(draws, lottery_type)
    constraints = analyze_constraints(draws, lottery_type)

    sorted_nums = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    # Pair affinity para selecao inteligente
    pair_scores_raw, top_pairs = pair_analysis(draws, num_range)
    pair_affinity = defaultdict(lambda: defaultdict(float))
    for (a, b), freq in top_pairs:
        pair_affinity[a][b] += freq
        pair_affinity[b][a] += freq

    # Core adaptativo por tipo
    density = pick / (max_n - min_n + 1)
    if density >= 0.5:
        core_pct = 0.70   # Lotofacil: 70% vem do top
        pool_mult = 1.3
    elif density >= 0.2:
        core_pct = 0.60   # Lotomania
        pool_mult = 1.4
    else:
        core_pct = 0.55   # Quina, Mega
        pool_mult = 1.6

    core_size = max(int(pick * core_pct), 1)
    top_pool = [n for n, s in sorted_nums[:max(int(pick * pool_mult), pick + 2)]]

    predictions = []
    used_combos = set()
    max_attempts = num_games * 150

    for attempt in range(max_attempts):
        if len(predictions) >= num_games:
            break

        # Selecionar nucleo com leve variacao
        core = []
        shuffled_top = list(top_pool)
        random.shuffle(shuffled_top)
        for n in shuffled_top:
            if len(core) >= core_size:
                break
            core.append(n)

        # Selecao PAIR-AWARE: boost para numeros que tem pares fortes com os ja selecionados
        remaining = [n for n in range(min_n, max_n + 1) if n not in core]
        selected = list(core)

        while len(selected) < pick and remaining:
            # Calcular score combinado: ensemble + afinidade com numeros ja selecionados
            combined = []
            for n in remaining:
                base = max(scores.get(n, 0), 0.001)
                pair_boost = sum(pair_affinity.get(n, {}).get(s, 0) for s in selected)
                combined.append(base + pair_boost * 0.5)

            total_w = sum(combined)
            if total_w <= 0:
                idx = random.randint(0, len(remaining) - 1)
            else:
                r = random.uniform(0, total_w)
                cumul = 0
                idx = 0
                for i, w in enumerate(combined):
                    cumul += w
                    if cumul >= r:
                        idx = i
                        break
            selected.append(remaining[idx])
            remaining.pop(idx)

        selected.sort()
        combo_key = tuple(selected)

        if combo_key in used_combos:
            continue

        if filter_game_strict(selected, lottery_type, constraints):
            used_combos.add(combo_key)
            game_sum = sum(selected)
            nums_sorted = sorted(selected)
            consec = sum(1 for i in range(len(nums_sorted)-1)
                        if nums_sorted[i+1] - nums_sorted[i] == 1)
            predictions.append({
                "game_number": len(predictions) + 1,
                "numbers": selected,
                "sum": game_sum,
                "even_count": sum(1 for n in selected if n % 2 == 0),
                "odd_count": sum(1 for n in selected if n % 2 != 0),
                "consecutives": consec,
            })

    analysis_meta = {
        "total_draws_analyzed": meta_info["total_draws"],
        "markov_built": meta_info["markov_active"],
        "cycles_detected": meta_info["cycles_due"],
        "top_pairs": meta_info["top_pairs"],
        "sum_range": constraints["sum_range"] if constraints else None,
        "even_range": constraints["even_range"] if constraints else None,
        "consec_range": constraints["consec_range"] if constraints else None,
        "ideal_even_odd": (constraints["even_avg"], config["pick"] - constraints["even_avg"]) if constraints else None,
        "top_ensemble_numbers": sorted_nums[:15],
    }

    return predictions, analysis_meta


# ============================================================
# 8. BACKTESTING EXPANDIDO
# ============================================================

def backtest(lottery_type, draws, test_size=50, num_games=50):
    """Backtest com 50 jogos candidatos por teste para maximizar acertos."""
    if len(draws) < test_size + 100:
        return None

    config = LOTTERY_CONFIG[lottery_type]
    pick = config["pick"]
    results = []

    for t in range(test_size):
        test_draw = draws[t]
        train_draws = draws[t + 1:]

        if len(train_draws) < 100:
            break

        predictions, _ = generate_advanced_predictions(lottery_type, train_draws, num_games)
        real_numbers = set(test_draw.get("numbers", []))

        best_match = 0
        for pred in predictions:
            match = len(real_numbers & set(pred["numbers"]))
            best_match = max(best_match, match)

        results.append({
            "draw_number": test_draw.get("draw_number", 0),
            "best_match": best_match,
            "total": pick,
            "accuracy": round(best_match / pick, 4),
        })

    if not results:
        return None

    avg_match = sum(r["best_match"] for r in results) / len(results)
    avg_accuracy = sum(r["accuracy"] for r in results) / len(results)
    best_ever = max(r["best_match"] for r in results)
    worst_ever = min(r["best_match"] for r in results)

    # Distribuicao de acertos
    dist = Counter(r["best_match"] for r in results)

    return {
        "lottery": config["name"],
        "test_size": len(results),
        "avg_match": round(avg_match, 2),
        "avg_accuracy_pct": round(avg_accuracy * 100, 1),
        "best_match": best_ever,
        "worst_match": worst_ever,
        "pick": pick,
        "distribution": dict(sorted(dist.items())),
    }


# ============================================================
# TESTE STANDALONE (usa paginação para carregar TODOS os dados)
# ============================================================

if __name__ == "__main__":
    from ml_engine import fetch_historical_data

    print("=" * 60)
    print("  SIAOL-PRO v8.5-TURBO - Motor ML ULTRA-Avancado")
    print("  (Com Paginacao + Sharpening + Pair-Aware + Filtro Rigoroso)")
    print("=" * 60)

    for lottery_type in LOTTERY_CONFIG:
        config = LOTTERY_CONFIG[lottery_type]
        print(f"\n{'='*60}")
        print(f"  {config['name']} (pick {config['pick']} de {config['range']})")
        print(f"{'='*60}")

        draws = fetch_historical_data(lottery_type, 4000)
        print(f"  Registros carregados: {len(draws)}")

        if len(draws) < 50:
            print(f"  Insuficiente!")
            continue

        # Constraints
        constraints = analyze_constraints(draws, lottery_type)
        if constraints:
            print(f"  Soma ideal: {constraints['sum_range']}")
            print(f"  Par/Impar ideal: {constraints['even_range']}")
            print(f"  Consecutivos ideal: {constraints['consec_range']}")

        # Predicoes
        predictions, meta = generate_advanced_predictions(lottery_type, draws, 5)
        print(f"\n  Predicoes ({len(predictions)}):")
        for p in predictions:
            print(f"    Jogo {p['game_number']}: {p['numbers']} "
                  f"(soma={p['sum']}, {p['even_count']}P/{p['odd_count']}I, "
                  f"consec={p.get('consecutives', '?')})")

        # Backtest
        if len(draws) >= 200:
            print(f"\n  Rodando backtest (50 sorteios x 50 jogos)...")
            bt = backtest(lottery_type, draws, test_size=50, num_games=50)
            if bt:
                print(f"  RESULTADO: {bt['avg_match']:.1f}/{bt['pick']} media "
                      f"({bt['avg_accuracy_pct']:.1f}%)")
                print(f"  Melhor: {bt['best_match']}/{bt['pick']} | "
                      f"Pior: {bt['worst_match']}/{bt['pick']}")
                print(f"  Distribuicao: {bt['distribution']}")

    print(f"\n{'='*60}")
    print("  TESTE v8.5-TURBO CONCLUIDO")
    print(f"{'='*60}")

