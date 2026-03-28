"""
SIAOL-PRO v9.0 - MOTOR DE AUTO-EVOLUCAO
"O Organismo" - Sistema que se auto-modifica, testa e evolui

Ciclo Evolutivo:
  1. AVALIAR -> Roda backtest do codigo atual (baseline)
  2. MUTAR   -> IA sugere uma modificacao especifica nos pesos/parametros
  3. TESTAR  -> Aplica mutacao e roda backtest
  4. SELECIONAR -> Se melhorou: ACEITA (commit) | Se piorou: DESCARTA
  5. REPETIR -> Ate N geracoes ou convergencia

Inspirado em: Algoritmos Geneticos + MiroFish (Swarm Intelligence) + Meta-Learning
"""
import os
import sys
import json
import copy
import random
import time
import math
import traceback
import subprocess
from datetime import datetime
from collections import Counter, defaultdict
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# CONFIGURACAO DO ORGANISMO
# ============================================================

EVOLUTION_CONFIG = {
    "max_generations": 5,          # Tentativas por ciclo
    "min_improvement": 0.01,       # Melhoria minima para aceitar (1%)
    "backtest_size": 30,           # Sorteios para testar
    "backtest_games": 30,          # Jogos por teste
    "target_lottery": "lotofacil", # Foco principal
    "mutation_types": [
        "weights",           # Mutacao nos pesos do ensemble
        "sharpening",        # Mutacao no expoente de sharpening
        "core_size",         # Mutacao no tamanho do nucleo Top-K
        "window_config",     # Mutacao nas janelas deslizantes
        "filter_params",     # Mutacao nos filtros (soma, par/impar)
        "markov_weight",     # Peso do Markov vs outros
        "pair_boost",        # Intensidade do boost de pares
        "new_technique",     # IA sugere tecnica completamente nova
    ],
}

LOTTERY_CONFIG = {
    "megasena": {"name": "Mega-Sena", "range": (1, 60), "pick": 6},
    "lotofacil": {"name": "Lotofacil", "range": (1, 25), "pick": 15},
    "quina": {"name": "Quina", "range": (1, 80), "pick": 5},
    "lotomania": {"name": "Lotomania", "range": (0, 99), "pick": 20},
}


# ============================================================
# GENOMA: Parametros Mutaveis do Algoritmo
# ============================================================

DEFAULT_GENOME = {
    "version": "9.0.0",
    "generation": 0,
    "weights": {
        "freq": 0.12,
        "gap": 0.10,
        "markov": 0.22,
        "window": 0.18,
        "cycle": 0.08,
        "trend": 0.15,
        "pair": 0.15,
    },
    "sharp_exp": 2.5,
    "core_pct": 0.70,
    "pool_mult": 1.3,
    "pair_boost_factor": 0.5,
    "windows": [
        {"size": 5, "weight": 8.0},
        {"size": 10, "weight": 5.0},
        {"size": 20, "weight": 3.0},
        {"size": 50, "weight": 2.0},
        {"size": 100, "weight": 1.5},
        {"size": 200, "weight": 1.0},
    ],
    "filter": {
        "sum_sigma": 0.8,
        "even_sigma": 1.0,
        "consec_sigma_low": 1.0,
        "consec_sigma_high": 1.5,
        "require_all_quadrants": True,
    },
    "fitness_history": [],
}


def load_genome():
    """Carrega genoma salvo ou cria um novo."""
    genome_path = os.path.join(os.path.dirname(__file__), "genome.json")
    if os.path.exists(genome_path):
        with open(genome_path, "r") as f:
            return json.load(f)
    return copy.deepcopy(DEFAULT_GENOME)


def save_genome(genome):
    """Salva genoma no disco."""
    genome_path = os.path.join(os.path.dirname(__file__), "genome.json")
    with open(genome_path, "w") as f:
        json.dump(genome, f, indent=2)


# ============================================================
# MOTOR ML PARAMETRIZADO (usa genoma para tudo)
# ============================================================

def build_markov(draws, num_range):
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


def pair_analysis(draws, num_range, top_pairs=50):
    pair_count = defaultdict(int)
    for draw in draws:
        nums = sorted(draw.get("numbers", []))
        for i in range(len(nums)):
            for j in range(i + 1, len(nums)):
                pair_count[(nums[i], nums[j])] += 1
    total = len(draws)
    pair_freq = {k: v / total for k, v in pair_count.items()}
    pair_scores = defaultdict(float)
    sorted_pairs = sorted(pair_freq.items(), key=lambda x: x[1], reverse=True)[:top_pairs]
    for (a, b), freq in sorted_pairs:
        pair_scores[a] += freq
        pair_scores[b] += freq
    return dict(pair_scores), sorted_pairs


def compute_scores_with_genome(draws, lottery_type, genome):
    """Ensemble PARAMETRIZADO pelo genoma."""
    config = LOTTERY_CONFIG[lottery_type]
    num_range = config["range"]
    min_n, max_n = num_range
    pick = config["pick"]
    total_draws = len(draws)
    W = genome["weights"]

    # Frequencia
    freq = Counter()
    for d in draws:
        for n in d.get("numbers", []):
            freq[n] += 1
    expected_freq = total_draws * pick / (max_n - min_n + 1)
    freq_scores = {n: freq.get(n, 0) / max(expected_freq, 1) for n in range(min_n, max_n + 1)}

    # Gaps
    gap_scores = {}
    for n in range(min_n, max_n + 1):
        gap = 0
        for d in draws:
            if n in d.get("numbers", []):
                break
            gap += 1
        avg_gap = total_draws / max(freq.get(n, 1), 1)
        gap_scores[n] = min(gap / max(avg_gap, 1), 2.0)

    # Markov
    markov = build_markov(draws, num_range)
    last_nums = draws[0].get("numbers", []) if draws else []
    m_scores = defaultdict(float)
    for num in last_nums:
        if num in markov:
            for nxt, prob in markov[num].items():
                m_scores[nxt] += prob
    max_m = max(m_scores.values()) if m_scores else 1
    markov_scores = {n: m_scores.get(n, 0) / max(max_m, 0.001) for n in range(min_n, max_n + 1)}

    # Janela Deslizante (parametrizada)
    w_scores = defaultdict(float)
    for win in genome.get("windows", []):
        ws = win["size"]
        ww = win["weight"]
        if len(draws) < ws:
            continue
        window = draws[:ws]
        wf = Counter()
        for d in window:
            for n in d.get("numbers", []):
                wf[n] += 1
        exp = len(window) * pick / (max_n - min_n + 1)
        for n in range(min_n, max_n + 1):
            deviation = (wf.get(n, 0) - exp) / max(exp, 1)
            w_scores[n] += deviation * ww
    max_ws = max(abs(v) for v in w_scores.values()) if w_scores else 1
    window_scores = {n: (w_scores.get(n, 0) / max(max_ws, 0.001) + 1) / 2 for n in range(min_n, max_n + 1)}

    # Ciclos
    cycle_scores = {}
    for n in range(min_n, max_n + 1):
        positions = [i for i, d in enumerate(draws) if n in d.get("numbers", [])]
        if len(positions) < 4:
            cycle_scores[n] = 0
            continue
        intervals = [positions[j] - positions[j-1] for j in range(1, len(positions))]
        avg = sum(intervals) / len(intervals)
        var = sum((x - avg)**2 for x in intervals) / len(intervals)
        std = math.sqrt(var)
        regularity = max(0, 1 - std / max(avg, 1))
        last_seen = positions[0]
        overdue = max(0, last_seen - avg)
        urgency = (overdue / max(avg, 1)) * regularity
        is_due = last_seen >= avg * 0.8
        cycle_scores[n] = urgency + (0.3 if is_due else 0)

    # Tendencia
    trend_scores = {}
    if len(draws) >= 30:
        for n in range(min_n, max_n + 1):
            c5 = sum(1 for d in draws[:5] if n in d.get("numbers", []))
            c10 = sum(1 for d in draws[:10] if n in d.get("numbers", []))
            c30 = sum(1 for d in draws[:30] if n in d.get("numbers", []))
            trend_scores[n] = (c5 / 5 * 3 + c10 / 10 * 2 + c30 / 30) / 6
        max_t = max(trend_scores.values()) if trend_scores else 1
        trend_scores = {n: v / max(max_t, 0.001) for n, v in trend_scores.items()}
    else:
        trend_scores = {n: 0.5 for n in range(min_n, max_n + 1)}

    # Pares
    pair_dict, top_pairs = pair_analysis(draws, num_range)
    max_p = max(pair_dict.values()) if pair_dict else 1
    pair_scores = {n: pair_dict.get(n, 0) / max(max_p, 0.001) for n in range(min_n, max_n + 1)}

    # ENSEMBLE com pesos do genoma
    raw = {}
    for n in range(min_n, max_n + 1):
        raw[n] = (
            freq_scores.get(n, 0) * W.get("freq", 0.12) +
            gap_scores.get(n, 0) * W.get("gap", 0.10) +
            markov_scores.get(n, 0) * W.get("markov", 0.22) +
            window_scores.get(n, 0) * W.get("window", 0.18) +
            cycle_scores.get(n, 0) * W.get("cycle", 0.08) +
            trend_scores.get(n, 0) * W.get("trend", 0.15) +
            pair_scores.get(n, 0) * W.get("pair", 0.15)
        )

    # Sharpening parametrizado
    sharp_exp = genome.get("sharp_exp", 2.5)
    values = list(raw.values())
    if values:
        min_v = min(values)
        max_v = max(values)
        rng = max(max_v - min_v, 0.001)
        final = {n: ((v - min_v) / rng) ** sharp_exp for n, v in raw.items()}
    else:
        final = raw

    return final, top_pairs


def generate_with_genome(lottery_type, draws, genome, num_games=5):
    """Gera predicoes usando genoma parametrizado."""
    config = LOTTERY_CONFIG[lottery_type]
    num_range = config["range"]
    pick = config["pick"]
    min_n, max_n = num_range

    if len(draws) < 20:
        return []

    scores, top_pairs = compute_scores_with_genome(draws, lottery_type, genome)
    sorted_nums = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    # Pair affinity
    pair_affinity = defaultdict(lambda: defaultdict(float))
    for (a, b), freq in top_pairs:
        pair_affinity[a][b] += freq
        pair_affinity[b][a] += freq

    core_pct = genome.get("core_pct", 0.70)
    pool_mult = genome.get("pool_mult", 1.3)
    pair_boost = genome.get("pair_boost_factor", 0.5)
    core_size = max(int(pick * core_pct), 1)
    top_pool = [n for n, s in sorted_nums[:max(int(pick * pool_mult), pick + 2)]]

    # Analise de constraints
    sums, even_counts, consec_counts = [], [], []
    for draw in draws[:500]:
        nums = sorted(draw.get("numbers", []))
        if len(nums) != pick:
            continue
        sums.append(sum(nums))
        even_counts.append(sum(1 for n in nums if n % 2 == 0))
        consec_counts.append(sum(1 for i in range(len(nums)-1) if nums[i+1] - nums[i] == 1))

    if not sums:
        return []

    def stats(arr):
        avg = sum(arr) / len(arr)
        std = math.sqrt(sum((x-avg)**2 for x in arr) / len(arr))
        return avg, std

    sum_avg, sum_std = stats(sums)
    even_avg, even_std = stats(even_counts)
    consec_avg, consec_std = stats(consec_counts)

    filt = genome.get("filter", {})
    sum_range = (round(sum_avg - sum_std * filt.get("sum_sigma", 0.8)),
                 round(sum_avg + sum_std * filt.get("sum_sigma", 0.8)))
    even_range = (max(0, round(even_avg - even_std * filt.get("even_sigma", 1.0))),
                  min(pick, round(even_avg + even_std * filt.get("even_sigma", 1.0))))
    consec_range = (max(0, round(consec_avg - consec_std * filt.get("consec_sigma_low", 1.0))),
                    round(consec_avg + consec_std * filt.get("consec_sigma_high", 1.5)))

    predictions = []
    used_combos = set()

    for attempt in range(num_games * 150):
        if len(predictions) >= num_games:
            break

        core = []
        shuffled = list(top_pool)
        random.shuffle(shuffled)
        for n in shuffled:
            if len(core) >= core_size:
                break
            core.append(n)

        remaining = [n for n in range(min_n, max_n + 1) if n not in core]
        selected = list(core)

        while len(selected) < pick and remaining:
            combined = []
            for n in remaining:
                base = max(scores.get(n, 0), 0.001)
                pb = sum(pair_affinity.get(n, {}).get(s, 0) for s in selected)
                combined.append(base + pb * pair_boost)
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

        game_sum = sum(selected)
        if not (sum_range[0] <= game_sum <= sum_range[1]):
            continue
        evens = sum(1 for n in selected if n % 2 == 0)
        if not (even_range[0] <= evens <= even_range[1]):
            continue
        consec = sum(1 for i in range(len(selected)-1) if selected[i+1] - selected[i] == 1)
        if not (consec_range[0] <= consec <= consec_range[1]):
            continue
        if pick >= 10 and filt.get("require_all_quadrants", True):
            q_size = (max_n - min_n + 1) / 4
            quads = [0, 0, 0, 0]
            for n in selected:
                qi = min(int((n - min_n) / q_size), 3)
                quads[qi] += 1
            if any(q == 0 for q in quads):
                continue

        used_combos.add(combo_key)
        predictions.append({"numbers": selected})

    return predictions


# ============================================================
# BACKTEST PARAMETRIZADO (FITNESS FUNCTION)
# ============================================================

def evaluate_fitness(lottery_type, draws, genome, test_size=30, num_games=30):
    """Funcao de fitness: retorna accuracy media do genoma."""
    if len(draws) < test_size + 100:
        return 0.0

    config = LOTTERY_CONFIG[lottery_type]
    pick = config["pick"]
    total_matches = 0
    total_tests = 0

    for t in range(test_size):
        test_draw = draws[t]
        train_draws = draws[t + 1:]
        if len(train_draws) < 100:
            break

        predictions = generate_with_genome(lottery_type, train_draws, genome, num_games)
        real_numbers = set(test_draw.get("numbers", []))

        best_match = 0
        for pred in predictions:
            match = len(real_numbers & set(pred["numbers"]))
            best_match = max(best_match, match)

        total_matches += best_match
        total_tests += 1

    if total_tests == 0:
        return 0.0

    return total_matches / total_tests


# ============================================================
# MUTACOES (Variacao Genetica)
# ============================================================

def mutate_weights(genome):
    """Mutacao aleatoria nos pesos do ensemble."""
    g = copy.deepcopy(genome)
    keys = list(g["weights"].keys())
    # Perturbar 2-3 pesos aleatorios
    num_mutations = random.randint(2, 3)
    for _ in range(num_mutations):
        key = random.choice(keys)
        delta = random.uniform(-0.05, 0.05)
        g["weights"][key] = max(0.01, g["weights"][key] + delta)
    # Normalizar para somar 1
    total = sum(g["weights"].values())
    g["weights"] = {k: round(v / total, 4) for k, v in g["weights"].items()}
    return g, f"Mutacao de pesos: {num_mutations} pesos alterados"


def mutate_sharpening(genome):
    """Mutacao no expoente de sharpening."""
    g = copy.deepcopy(genome)
    delta = random.uniform(-0.4, 0.4)
    g["sharp_exp"] = max(1.0, min(4.0, g["sharp_exp"] + delta))
    g["sharp_exp"] = round(g["sharp_exp"], 2)
    return g, f"Sharpening: {genome['sharp_exp']} -> {g['sharp_exp']}"


def mutate_core_size(genome):
    """Mutacao no tamanho do nucleo."""
    g = copy.deepcopy(genome)
    delta = random.uniform(-0.08, 0.08)
    g["core_pct"] = max(0.45, min(0.85, g["core_pct"] + delta))
    g["core_pct"] = round(g["core_pct"], 3)
    return g, f"Core: {genome['core_pct']} -> {g['core_pct']}"


def mutate_pair_boost(genome):
    """Mutacao no fator de boost de pares."""
    g = copy.deepcopy(genome)
    delta = random.uniform(-0.2, 0.2)
    g["pair_boost_factor"] = max(0.1, min(1.5, g["pair_boost_factor"] + delta))
    g["pair_boost_factor"] = round(g["pair_boost_factor"], 3)
    return g, f"Pair boost: {genome['pair_boost_factor']} -> {g['pair_boost_factor']}"


def mutate_filter(genome):
    """Mutacao nos parametros de filtro."""
    g = copy.deepcopy(genome)
    param = random.choice(["sum_sigma", "even_sigma", "consec_sigma_low", "consec_sigma_high"])
    delta = random.uniform(-0.2, 0.2)
    g["filter"][param] = max(0.3, min(2.0, g["filter"][param] + delta))
    g["filter"][param] = round(g["filter"][param], 3)
    return g, f"Filtro {param}: {genome['filter'][param]} -> {g['filter'][param]}"


def mutate_windows(genome):
    """Mutacao nos pesos das janelas deslizantes."""
    g = copy.deepcopy(genome)
    idx = random.randint(0, len(g["windows"]) - 1)
    delta = random.uniform(-1.5, 1.5)
    old_w = g["windows"][idx]["weight"]
    g["windows"][idx]["weight"] = max(0.5, round(old_w + delta, 2))
    return g, f"Window {g['windows'][idx]['size']}: {old_w} -> {g['windows'][idx]['weight']}"


def mutate_ai_guided(genome, current_fitness, draws_count):
    """Mutacao GUIADA POR IA - o cerebro sugere a mutacao."""
    try:
        from groq import Groq
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            return mutate_weights(genome)

        client = Groq(api_key=api_key)
        prompt = f"""Voce e um engenheiro de ML otimizando um algoritmo de previsao de loteria.

ESTADO ATUAL DO GENOMA:
- Fitness (accuracy media Lotofacil): {current_fitness:.2f}/15
- Pesos ensemble: {json.dumps(genome['weights'])}
- Sharpening exponent: {genome['sharp_exp']}
- Core size: {genome['core_pct']}
- Pair boost: {genome['pair_boost_factor']}
- Dados historicos: {draws_count} sorteios

HISTORICO DE FITNESS: {json.dumps(genome.get('fitness_history', [])[-10:])}

Sugira UMA mutacao especifica para melhorar a accuracy. Responda em JSON:
{{
  "parameter": "nome_do_parametro (weights/sharp_exp/core_pct/pair_boost_factor)",
  "action": "descricao da mutacao",
  "new_values": {{}}
}}"""

        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "Voce e um otimizador de hiperparametros. Responda APENAS em JSON valido."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=500,
            response_format={"type": "json_object"},
        )

        suggestion = json.loads(completion.choices[0].message.content)
        g = copy.deepcopy(genome)

        param = suggestion.get("parameter", "weights")
        new_vals = suggestion.get("new_values", {})

        if param == "weights" and isinstance(new_vals, dict):
            for k, v in new_vals.items():
                if k in g["weights"] and isinstance(v, (int, float)):
                    g["weights"][k] = max(0.01, min(0.5, float(v)))
            total = sum(g["weights"].values())
            g["weights"] = {k: round(v / total, 4) for k, v in g["weights"].items()}
        elif param == "sharp_exp" and "sharp_exp" in new_vals:
            g["sharp_exp"] = max(1.0, min(4.0, float(new_vals["sharp_exp"])))
        elif param == "core_pct" and "core_pct" in new_vals:
            g["core_pct"] = max(0.45, min(0.85, float(new_vals["core_pct"])))
        elif param == "pair_boost_factor" and "pair_boost_factor" in new_vals:
            g["pair_boost_factor"] = max(0.1, min(1.5, float(new_vals["pair_boost_factor"])))

        desc = f"AI-Guided: {suggestion.get('action', 'mutacao sugerida pela IA')}"
        return g, desc

    except Exception as e:
        print(f"    [AI-MUTACAO] Fallback para mutacao aleatoria: {str(e)[:60]}")
        return mutate_weights(genome)


MUTATION_FUNCTIONS = [
    mutate_weights,
    mutate_sharpening,
    mutate_core_size,
    mutate_pair_boost,
    mutate_filter,
    mutate_windows,
]


# ============================================================
# LOG NO SUPABASE
# ============================================================

def log_evolution(generation, mutation_desc, before, after, accepted, genome):
    """Registra evolucao no Supabase."""
    import requests
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        return

    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }

    data = {
        "message": f"GEN-{generation}: {mutation_desc} | {before:.2f} -> {after:.2f} | {'ACEITO' if accepted else 'REJEITADO'}",
        "log_level": "EVOLUTION",
        "metadata": {
            "generation": generation,
            "mutation": mutation_desc,
            "before_fitness": round(before, 4),
            "after_fitness": round(after, 4),
            "accepted": accepted,
            "genome_version": genome.get("version", "?"),
            "weights": genome.get("weights", {}),
        }
    }

    try:
        requests.post(f"{url}/rest/v1/system_logs", headers=headers, json=data, timeout=10)
    except Exception:
        pass


# ============================================================
# CICLO EVOLUTIVO PRINCIPAL
# ============================================================

def run_evolution_cycle(lottery_type="lotofacil"):
    """Executa um ciclo completo de evolucao."""
    from ml_engine import fetch_historical_data

    print("=" * 60)
    print("  SIAOL-PRO v9.0 - MOTOR DE AUTO-EVOLUCAO")
    print("  'O Organismo' - Evolucao Autonoma por Selecao Natural")
    print("=" * 60)

    # 1. Carregar dados
    print(f"\n  [DADOS] Carregando historico de {lottery_type}...")
    draws = fetch_historical_data(lottery_type, 4000)
    print(f"  [DADOS] {len(draws)} registros carregados")

    if len(draws) < 200:
        print("  [ERRO] Dados insuficientes para evolucao!")
        return None

    # 2. Carregar genoma atual
    genome = load_genome()
    gen_start = genome.get("generation", 0)
    print(f"\n  [GENOMA] Geracao atual: {gen_start}")
    print(f"  [GENOMA] Pesos: {genome['weights']}")
    print(f"  [GENOMA] Sharp: {genome['sharp_exp']} | Core: {genome['core_pct']} | Pair: {genome['pair_boost_factor']}")

    # 3. Avaliar fitness atual (baseline)
    print(f"\n  [BASELINE] Avaliando fitness do genoma atual...")
    cfg = EVOLUTION_CONFIG
    baseline_fitness = evaluate_fitness(
        lottery_type, draws, genome,
        test_size=cfg["backtest_size"],
        num_games=cfg["backtest_games"]
    )
    print(f"  [BASELINE] Fitness atual: {baseline_fitness:.2f}/{LOTTERY_CONFIG[lottery_type]['pick']}")

    best_fitness = baseline_fitness
    best_genome = copy.deepcopy(genome)
    improvements = []

    # 4. Ciclo de mutacoes
    for gen in range(cfg["max_generations"]):
        generation = gen_start + gen + 1
        print(f"\n  {'='*50}")
        print(f"  GERACAO {generation}")
        print(f"  {'='*50}")

        # Escolher tipo de mutacao
        if gen == 0 or gen == cfg["max_generations"] - 1:
            # Primeira e ultima: usar IA
            mutant, desc = mutate_ai_guided(genome, best_fitness, len(draws))
        else:
            # Meio: mutacao aleatoria
            mutate_fn = random.choice(MUTATION_FUNCTIONS)
            mutant, desc = mutate_fn(best_genome)

        mutant["generation"] = generation
        print(f"  [MUTACAO] {desc}")

        # Avaliar mutante
        print(f"  [TESTE] Avaliando mutante...")
        mutant_fitness = evaluate_fitness(
            lottery_type, draws, mutant,
            test_size=cfg["backtest_size"],
            num_games=cfg["backtest_games"]
        )
        print(f"  [TESTE] Fitness mutante: {mutant_fitness:.2f}/{LOTTERY_CONFIG[lottery_type]['pick']}")

        improvement = mutant_fitness - best_fitness
        accepted = improvement >= cfg["min_improvement"]

        if accepted:
            print(f"  [SELECAO] ✓ ACEITO! Melhoria: +{improvement:.3f}")
            best_fitness = mutant_fitness
            best_genome = copy.deepcopy(mutant)
            improvements.append({
                "generation": generation,
                "mutation": desc,
                "improvement": round(improvement, 4),
                "fitness": round(mutant_fitness, 4),
            })
        else:
            if improvement > 0:
                print(f"  [SELECAO] ~ Melhoria minima (+{improvement:.3f} < {cfg['min_improvement']}), rejeitado")
            else:
                print(f"  [SELECAO] ✗ REJEITADO. Delta: {improvement:.3f}")

        # Log
        log_evolution(generation, desc, baseline_fitness if gen == 0 else best_fitness - improvement,
                     mutant_fitness, accepted, mutant)

    # 5. Salvar melhor genoma
    if best_fitness > baseline_fitness:
        best_genome["fitness_history"] = genome.get("fitness_history", []) + [{
            "gen": best_genome["generation"],
            "fitness": round(best_fitness, 4),
            "timestamp": datetime.now().isoformat(),
        }]
        # Incrementar versao
        parts = best_genome.get("version", "9.0.0").split(".")
        parts[-1] = str(int(parts[-1]) + 1)
        best_genome["version"] = ".".join(parts)

        save_genome(best_genome)
        total_improvement = best_fitness - baseline_fitness
        print(f"\n  {'='*50}")
        print(f"  EVOLUCAO CONCLUIDA!")
        print(f"  {'='*50}")
        print(f"  Fitness: {baseline_fitness:.2f} -> {best_fitness:.2f} (+{total_improvement:.3f})")
        print(f"  Versao: {best_genome['version']}")
        print(f"  Melhorias aceitas: {len(improvements)}")
        for imp in improvements:
            print(f"    GEN-{imp['generation']}: {imp['mutation']} (+{imp['improvement']})")
    else:
        print(f"\n  [RESULTADO] Nenhuma melhoria encontrada neste ciclo.")
        print(f"  O genoma atual ja esta otimo para os dados disponiveis.")
        # Salvar genoma com geracao atualizada
        genome["generation"] = gen_start + cfg["max_generations"]
        save_genome(genome)

    return {
        "baseline": round(baseline_fitness, 4),
        "best": round(best_fitness, 4),
        "improvement": round(best_fitness - baseline_fitness, 4),
        "generations": cfg["max_generations"],
        "improvements_accepted": len(improvements),
    }


# ============================================================
# EXECUCAO STANDALONE
# ============================================================

if __name__ == "__main__":
    result = run_evolution_cycle("lotofacil")
    if result:
        print(f"\n  RESULTADO FINAL: {json.dumps(result, indent=2)}")
