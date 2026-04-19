#!/usr/bin/env python3
"""
SIAOL-PRO v13.0 - SYMBIOSIS ORCHESTRATOR
=========================================
Orquestrador central que conecta múltiplas IAs em simbiose:
- Manus (este terminal) - Coordenador Principal
- MiniMax Agent (nuvem) - Executor Paralelo
- Groq Cloud (Llama-3.3-70B) - Motor de IA Primário
- Ollama Local (Qwen2.5:3b) - Motor de IA Secundário
- Supabase - Hub Central de Dados e Comunicação

Comunicação via tabela ai_symbiosis no Supabase (persistente)
"""

import os
import sys
import json
import time
import random
import hashlib
import requests
import numpy as np
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# CONFIGURAÇÕES
# ============================================================
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://ynfcmmwxfabdkqstsqkr.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "5096280712")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")

LOTTERY_CONFIGS = {
    "megasena": {"name": "Mega-Sena", "pick": 6, "range": 60, "api": "megasena"},
    "lotofacil": {"name": "Lotofácil", "pick": 15, "range": 25, "api": "lotofacil"},
    "quina": {"name": "Quina", "pick": 5, "range": 80, "api": "quina"},
    "lotomania": {"name": "Lotomania", "pick": 50, "range": 100, "api": "lotomania"},
}

def log(msg, level="INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [{level}] {msg}")

# ============================================================
# SUPABASE - HUB CENTRAL DE COMUNICAÇÃO
# ============================================================
def supabase_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

def supabase_post(table, data):
    try:
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers=supabase_headers(),
            json=data,
            timeout=15
        )
        return r.status_code < 300
    except Exception as e:
        log(f"Supabase POST erro: {e}", "WARN")
        return False

def supabase_get(table, params=""):
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/{table}?{params}",
            headers=supabase_headers(),
            timeout=15
        )
        if r.status_code < 300:
            return r.json()
    except Exception as e:
        log(f"Supabase GET erro: {e}", "WARN")
    return []

def broadcast_to_ais(channel, sender, msg_type, content):
    """Envia mensagem para todas as IAs via Supabase"""
    data = {
        "channel": channel,
        "sender": sender,
        "msg_type": msg_type,
        "content": json.dumps(content) if isinstance(content, dict) else str(content),
        "created_at": datetime.utcnow().isoformat()
    }
    ok = supabase_post("ai_symbiosis", data)
    if ok:
        log(f"📡 Broadcast [{channel}] de {sender}: {msg_type}")
    return ok

def read_ai_messages(channel=None, limit=20):
    """Lê mensagens das outras IAs"""
    params = f"order=created_at.desc&limit={limit}"
    if channel:
        params += f"&channel=eq.{channel}"
    return supabase_get("ai_symbiosis", params)

# ============================================================
# GROQ AI - MOTOR PRIMÁRIO (70B PARÂMETROS)
# ============================================================
def ask_groq(prompt, temperature=0.7):
    """Consulta o Groq Cloud com Llama-3.3-70B"""
    if not GROQ_API_KEY:
        return None
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": "Você é um analista estatístico especializado em análise de padrões numéricos e séries temporais. Responda sempre em português brasileiro. Seja preciso, direto e baseado em dados."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": temperature,
                "max_tokens": 2000
            },
            timeout=60
        )
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"]
        else:
            log(f"Groq erro {r.status_code}: {r.text[:200]}", "WARN")
    except Exception as e:
        log(f"Groq exceção: {e}", "WARN")
    return None

def ask_ollama(prompt):
    """Consulta o Ollama local como fallback"""
    try:
        r = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=120
        )
        if r.status_code == 200:
            return r.json().get("response", "")
    except:
        pass
    return None

def ask_ai(prompt, temperature=0.7):
    """Tenta Groq primeiro, depois Ollama, depois fallback"""
    log("🧠 Consultando Groq (Llama-3.3-70B)...")
    resp = ask_groq(prompt, temperature)
    if resp:
        log("✅ Groq respondeu com sucesso")
        return resp, "groq"
    
    log("🔄 Groq falhou, tentando Ollama local...")
    resp = ask_ollama(prompt)
    if resp:
        log("✅ Ollama respondeu")
        return resp, "ollama"
    
    log("⚠️ Nenhuma IA disponível, usando fallback estatístico", "WARN")
    return None, "fallback"

# ============================================================
# COLETA DE DADOS REAIS
# ============================================================
def fetch_lottery_data(lottery_type, num_contests=60):
    """Coleta dados reais - API Heroku (primária) + API Caixa (fallback)"""
    config = LOTTERY_CONFIGS[lottery_type]
    api_name = config["api"]
    
    # APIs disponíveis (ordem de prioridade)
    apis = [
        {"name": "Heroku", "base": f"https://loteriascaixa-api.herokuapp.com/api/{api_name}", "latest_suffix": "/latest", "history_fmt": "/{num}", "num_key": "concurso", "nums_key": "dezenas", "date_key": "data"},
        {"name": "Caixa", "base": f"https://servicebus2.caixa.gov.br/portaldeloterias/api/{api_name}", "latest_suffix": "", "history_fmt": "/{num}", "num_key": "numero", "nums_key": "listaDezenas", "date_key": "dataApuracao"},
    ]
    
    log(f"📊 Coletando dados da {config['name']}...")
    
    latest = None
    latest_num = 0
    active_api = None
    
    # Tentar cada API
    for api in apis:
        try:
            url = api["base"] + api["latest_suffix"]
            r = requests.get(url, timeout=15)
            if r.status_code == 200:
                latest = r.json()
                latest_num = latest.get(api["num_key"], 0)
                raw_nums = latest.get(api["nums_key"], latest.get("dezenasSorteadasOrdemSorteio", []))
                latest_numbers = sorted([int(n) for n in raw_nums])
                log(f"✅ API {api['name']}: Concurso #{latest_num} - {latest_numbers}")
                active_api = api
                break
            else:
                log(f"API {api['name']} retornou {r.status_code}", "WARN")
        except Exception as e:
            log(f"API {api['name']} falhou: {e}", "WARN")
    
    if not active_api:
        log("❌ Todas as APIs falharam", "ERROR")
        return [], None
    
    # Coletar histórico
    contests = []
    for i in range(num_contests):
        contest_num = latest_num - i
        if contest_num < 1:
            break
        try:
            url = active_api["base"] + active_api["history_fmt"].format(num=contest_num)
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                data = r.json()
                raw_nums = data.get(active_api["nums_key"], data.get("dezenasSorteadasOrdemSorteio", []))
                nums = sorted([int(n) for n in raw_nums])
                if nums:
                    contests.append({
                        "number": contest_num,
                        "date": data.get(active_api["date_key"], ""),
                        "numbers": nums
                    })
            time.sleep(0.15)
        except:
            continue
    
    log(f"✅ {len(contests)} concursos coletados via {active_api['name']}")
    return contests, latest

# ============================================================
# ANÁLISE ESTATÍSTICA PURA (SEM RANDOM)
# ============================================================
def pure_statistical_analysis(contests, config):
    """Análise 100% baseada em dados reais"""
    if not contests:
        return {}
    
    num_range = config["range"]
    pick = config["pick"]
    
    # Frequência absoluta
    freq = {}
    for i in range(1, num_range + 1):
        freq[i] = sum(1 for c in contests if i in c["numbers"])
    
    total = len(contests)
    
    # Gap analysis (atraso)
    gaps = {}
    for n in range(1, num_range + 1):
        last_seen = -1
        for idx, c in enumerate(contests):
            if n in c["numbers"]:
                last_seen = idx
                break
        gaps[n] = last_seen if last_seen >= 0 else total
    
    # Pares vs ímpares
    even_counts = []
    for c in contests:
        evens = sum(1 for n in c["numbers"] if n % 2 == 0)
        even_counts.append(evens)
    avg_evens = np.mean(even_counts) if even_counts else pick / 2
    
    # Soma média
    sums = [sum(c["numbers"]) for c in contests]
    avg_sum = np.mean(sums)
    std_sum = np.std(sums)
    
    # Consecutivos
    consec_counts = []
    for c in contests:
        nums = sorted(c["numbers"])
        consec = sum(1 for i in range(len(nums)-1) if nums[i+1] - nums[i] == 1)
        consec_counts.append(consec)
    avg_consec = np.mean(consec_counts)
    
    # Score composto por número
    scores = {}
    for n in range(1, num_range + 1):
        freq_score = freq[n] / total
        gap_score = gaps[n] / total  # maior gap = mais "atrasado"
        even_bonus = 0.05 if n % 2 == 0 else 0
        scores[n] = freq_score * 0.4 + gap_score * 0.4 + even_bonus + 0.15
    
    return {
        "frequency": freq,
        "gaps": gaps,
        "scores": scores,
        "avg_evens": float(avg_evens),
        "avg_sum": float(avg_sum),
        "std_sum": float(std_sum),
        "avg_consec": float(avg_consec),
        "total_contests": total
    }

# ============================================================
# MAPA DE CALOR DE TESES (100% DADOS)
# ============================================================
def thesis_heatmap(contests, config):
    """Avalia as 10 teses baseado em dados puros"""
    if not contests or len(contests) < 10:
        return {}
    
    num_range = config["range"]
    pick = config["pick"]
    
    # Frequência
    freq = {}
    for i in range(1, num_range + 1):
        freq[i] = sum(1 for c in contests if i in c["numbers"])
    total = len(contests)
    expected = (pick / num_range) * total
    
    # Tese 1: DNA Numérico (repetição de padrões)
    pattern_matches = 0
    for i in range(len(contests) - 1):
        common = len(set(contests[i]["numbers"]) & set(contests[i+1]["numbers"]))
        if common >= 2:
            pattern_matches += 1
    dna_score = pattern_matches / (len(contests) - 1) * 100
    
    # Tese 2: Vácuo Estatístico (números atrasados)
    max_gap = max(1, max(sum(1 for c in contests if n not in c["numbers"]) for n in range(1, num_range + 1)))
    vacuum_numbers = sum(1 for n in range(1, num_range + 1) 
                        if sum(1 for c in contests[:5] if n in c["numbers"]) == 0)
    vacuum_score = min(100, (vacuum_numbers / num_range) * 150)
    
    # Tese 3: Simetria (distribuição equilibrada)
    half = num_range // 2
    low_counts = [sum(1 for n in c["numbers"] if n <= half) for c in contests]
    balance = np.mean([abs(l - pick/2) for l in low_counts])
    symmetry_score = max(0, 100 - balance * 20)
    
    # Tese 4: Ciclo (periodicidade)
    cycle_matches = 0
    for i in range(len(contests) - 7):
        common = len(set(contests[i]["numbers"]) & set(contests[i+7]["numbers"]))
        if common >= 2:
            cycle_matches += 1
    cycle_score = min(100, (cycle_matches / max(1, len(contests) - 7)) * 200)
    
    # Tese 5: Quantum Collapse (concentração em faixas)
    thirds = [0, 0, 0]
    for c in contests[:10]:
        for n in c["numbers"]:
            if n <= num_range // 3:
                thirds[0] += 1
            elif n <= 2 * num_range // 3:
                thirds[1] += 1
            else:
                thirds[2] += 1
    total_thirds = sum(thirds)
    if total_thirds > 0:
        imbalance = max(thirds) / total_thirds - 1/3
        quantum_score = min(100, 100 - imbalance * 300)
    else:
        quantum_score = 50
    
    # Tese 6: Fibonacci (presença de números Fibonacci)
    fibs = [1, 2, 3, 5, 8, 13, 21, 34, 55, 89]
    fibs_in_range = [f for f in fibs if f <= num_range]
    fib_presence = sum(freq.get(f, 0) for f in fibs_in_range)
    fib_expected = len(fibs_in_range) * expected
    fib_score = min(100, (fib_presence / max(1, fib_expected)) * 100)
    
    # Tese 7: Primos (presença de números primos)
    def is_prime(n):
        if n < 2: return False
        for i in range(2, int(n**0.5) + 1):
            if n % i == 0: return False
        return True
    primes = [n for n in range(1, num_range + 1) if is_prime(n)]
    prime_presence = sum(freq.get(p, 0) for p in primes)
    prime_expected = len(primes) * expected
    prime_score = min(100, (prime_presence / max(1, prime_expected)) * 100)
    
    # Tese 8: Pares Dominantes
    even_ratios = []
    for c in contests:
        evens = sum(1 for n in c["numbers"] if n % 2 == 0)
        even_ratios.append(evens / pick)
    even_score = np.mean(even_ratios) * 100
    
    # Tese 9: Soma Áurea (soma próxima da média)
    sums = [sum(c["numbers"]) for c in contests]
    avg_sum = np.mean(sums)
    std_sum = np.std(sums)
    golden_matches = sum(1 for s in sums if abs(s - avg_sum) < std_sum * 0.5)
    golden_score = (golden_matches / total) * 100
    
    # Tese 10: Entropia (diversidade)
    unique_per_contest = [len(set(c["numbers"])) for c in contests]
    entropy_score = (np.mean(unique_per_contest) / pick) * 100
    
    heatmap = {
        "DNA Numérico": round(dna_score, 1),
        "Vácuo Estatístico": round(vacuum_score, 1),
        "Simetria": round(symmetry_score, 1),
        "Ciclo": round(cycle_score, 1),
        "Quantum Collapse": round(quantum_score, 1),
        "Fibonacci": round(fib_score, 1),
        "Primos": round(prime_score, 1),
        "Pares Dominantes": round(even_score, 1),
        "Soma Áurea": round(golden_score, 1),
        "Entropia": round(entropy_score, 1)
    }
    
    return heatmap

# ============================================================
# ALGORITMO GENÉTICO
# ============================================================
def genetic_algorithm(stats, config, pop_size=200, generations=100):
    """Gera jogos otimizados via algoritmo genético"""
    num_range = config["range"]
    pick = config["pick"]
    scores = stats.get("scores", {})
    avg_sum = stats.get("avg_sum", 0)
    std_sum = stats.get("std_sum", 1)
    avg_evens = stats.get("avg_evens", pick / 2)
    
    def fitness(game):
        score = 0
        # Score baseado em frequência/gap
        for n in game:
            score += scores.get(n, 0.5)
        # Penalizar soma fora do range
        game_sum = sum(game)
        if avg_sum > 0 and std_sum > 0:
            z = abs(game_sum - avg_sum) / std_sum
            score -= z * 2
        # Bonus para pares próximo da média
        evens = sum(1 for n in game if n % 2 == 0)
        score -= abs(evens - avg_evens) * 0.5
        # Penalizar consecutivos excessivos
        sorted_game = sorted(game)
        consec = sum(1 for i in range(len(sorted_game)-1) if sorted_game[i+1] - sorted_game[i] == 1)
        if pick <= 15:
            score -= max(0, consec - 3) * 1.0
        return score
    
    # População inicial
    population = []
    all_numbers = list(range(1, num_range + 1))
    weights = [scores.get(n, 0.5) for n in all_numbers]
    total_w = sum(weights)
    probs = [w / total_w for w in weights]
    
    for _ in range(pop_size):
        game = sorted(np.random.choice(all_numbers, size=pick, replace=False, p=probs))
        population.append(list(game))
    
    # Evolução
    for gen in range(generations):
        scored = [(fitness(g), g) for g in population]
        scored.sort(key=lambda x: -x[0])
        
        # Elitismo
        elite_size = max(2, pop_size // 10)
        new_pop = [g for _, g in scored[:elite_size]]
        
        while len(new_pop) < pop_size:
            # Seleção por torneio
            p1 = max(random.sample(scored[:pop_size//2], 3), key=lambda x: x[0])[1]
            p2 = max(random.sample(scored[:pop_size//2], 3), key=lambda x: x[0])[1]
            
            # Crossover
            combined = list(set(p1) | set(p2))
            if len(combined) >= pick:
                child = sorted(random.sample(combined, pick))
            else:
                child = sorted(random.sample(all_numbers, pick))
            
            # Mutação (10%)
            if random.random() < 0.1:
                idx = random.randint(0, pick - 1)
                new_num = random.choice([n for n in all_numbers if n not in child])
                child[idx] = new_num
                child = sorted(child)
            
            new_pop.append(child)
        
        population = new_pop[:pop_size]
    
    # Retornar os melhores
    final_scored = [(fitness(g), g) for g in population]
    final_scored.sort(key=lambda x: -x[0])
    
    best_fitness = final_scored[0][0]
    log(f"🧬 AG: Melhor fitness={best_fitness:.1f} após {generations} gerações")
    
    return final_scored, best_fitness

# ============================================================
# BACKTESTING
# ============================================================
def backtest(games, contests, pick):
    """Testa jogos contra concursos reais"""
    if not contests or not games:
        return {}
    
    test_contests = contests[:min(20, len(contests))]
    hits = []
    
    for contest in test_contests:
        real = set(contest["numbers"])
        best_hit = 0
        for game in games:
            hit = len(set(game) & real)
            best_hit = max(best_hit, hit)
        hits.append(best_hit)
    
    distribution = {}
    for h in hits:
        distribution[h] = distribution.get(h, 0) + 1
    
    return {
        "avg_hits": round(np.mean(hits), 2),
        "max_hits": max(hits),
        "min_hits": min(hits),
        "distribution": distribution,
        "total_tests": len(test_contests)
    }

# ============================================================
# TELEGRAM
# ============================================================
def send_telegram(text):
    """Envia mensagem ao Telegram"""
    if not TELEGRAM_TOKEN:
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "HTML"
            },
            timeout=15
        )
        return r.status_code == 200
    except:
        return False

# ============================================================
# CICLO PRINCIPAL DE SIMBIOSE
# ============================================================
def run_symbiosis_cycle(lottery_type, num_games=10):
    """Executa o ciclo completo de simbiose entre IAs"""
    config = LOTTERY_CONFIGS[lottery_type]
    start_time = time.time()
    
    log(f"{'='*60}")
    log(f"🌐 SIAOL-PRO v13.0 - SYMBIOSIS CYCLE")
    log(f"🎯 Loteria: {config['name']}")
    log(f"🤖 IAs: Groq (70B) + Ollama (3B) + MiniMax + Supabase Hub")
    log(f"{'='*60}")
    
    # Notificar início via Telegram
    send_telegram(f"🌐 <b>SIAOL-PRO v13.0 SYMBIOSIS</b>\n\n🎯 Iniciando ciclo para <b>{config['name']}</b>\n🤖 IAs em simbiose: Groq + Ollama + MiniMax\n⏰ {datetime.now().strftime('%H:%M:%S')}")
    
    # FASE 1: Ler insights das outras IAs
    log("\n[FASE 1/8] 📡 Lendo insights das outras IAs...")
    messages = read_ai_messages("knowledge_sharing", 10)
    insights = []
    for msg in messages:
        if msg.get("sender") != "manus_orchestrator":
            insights.append(f"{msg.get('sender', 'unknown')}: {msg.get('content', '')[:200]}")
    if insights:
        log(f"📥 {len(insights)} insights recebidos de outras IAs")
    else:
        log("📭 Nenhum insight de outras IAs ainda")
    
    # FASE 2: Coleta de dados reais
    log("\n[FASE 2/8] 📊 Coletando dados reais da Caixa...")
    contests, latest = fetch_lottery_data(lottery_type, 60)
    if not contests:
        log("❌ Falha na coleta de dados", "ERROR")
        return None
    
    # FASE 3: Análise estatística pura
    log("\n[FASE 3/8] 📈 Análise estatística pura...")
    stats = pure_statistical_analysis(contests, config)
    log(f"Pares médios: {stats.get('avg_evens', 0):.1f}/{config['pick']}")
    log(f"Soma média: {stats.get('avg_sum', 0):.0f} ± {stats.get('std_sum', 0):.0f}")
    
    # FASE 4: Mapa de Calor de Teses
    log("\n[FASE 4/8] 🔥 Mapa de Calor de Teses...")
    heatmap = thesis_heatmap(contests, config)
    if heatmap:
        dominant = max(heatmap, key=heatmap.get)
        log(f"Tese dominante: {dominant} ({heatmap[dominant]}%)")
        for tese, score in sorted(heatmap.items(), key=lambda x: -x[1])[:5]:
            log(f"  {tese}: {score}%")
    
    # FASE 5: Consultar IA (Groq 70B)
    log("\n[FASE 5/8] 🧠 Consultando IA (Groq Llama-3.3-70B)...")
    
    top_numbers = sorted(stats.get("scores", {}).items(), key=lambda x: -x[1])[:20]
    top_nums_str = ", ".join([str(n) for n, _ in top_numbers])
    
    ai_prompt = f"""Analise estes dados estatísticos da {config['name']} (últimos {len(contests)} concursos):

NÚMEROS COM MAIOR SCORE: {top_nums_str}
PARES MÉDIOS: {stats.get('avg_evens', 0):.1f}/{config['pick']}
SOMA MÉDIA: {stats.get('avg_sum', 0):.0f} ± {stats.get('std_sum', 0):.0f}
CONSECUTIVOS MÉDIOS: {stats.get('avg_consec', 0):.1f}

MAPA DE CALOR DE TESES:
{json.dumps(heatmap, indent=2, ensure_ascii=False)}

{'INSIGHTS DE OUTRAS IAs:' + chr(10) + chr(10).join(insights) if insights else 'Nenhum insight de outras IAs disponível.'}

Com base nestes dados, forneça:
1. Sua análise dos padrões mais fortes
2. Quais números priorizar (liste 20 números)
3. Qual tese seguir como estratégia principal
4. Nível de confiança (0-100%)

Responda de forma objetiva e baseada nos dados."""

    ai_response, ai_source = ask_ai(ai_prompt)
    if ai_response:
        log(f"✅ IA ({ai_source}) respondeu")
        log(f"Resposta: {ai_response[:300]}...")
    
    # FASE 6: Algoritmo Genético
    log(f"\n[FASE 6/8] 🧬 Algoritmo Genético (pop=200, gens=100)...")
    scored_games, best_fitness = genetic_algorithm(stats, config, 200, 100)
    
    # Selecionar os melhores jogos (converter numpy int64 para int nativo)
    games = []
    seen = set()
    for _, game in scored_games:
        game = [int(n) for n in game]  # Converter numpy int64 para int
        key = tuple(game)
        if key not in seen:
            seen.add(key)
            games.append(game)
        if len(games) >= num_games:
            break
    
    log(f"✅ {len(games)} jogos únicos gerados")
    
    # FASE 7: Backtesting
    log(f"\n[FASE 7/8] 🔬 Backtesting contra concursos reais...")
    bt = backtest(games, contests, config["pick"])
    if bt:
        log(f"Média de acertos: {bt['avg_hits']}/{config['pick']}")
        log(f"Máximo: {bt['max_hits']}/{config['pick']}")
        log(f"Distribuição: {bt['distribution']}")
    
    # FASE 8: Anti-Sycophancy + Envio
    log(f"\n[FASE 8/8] 🛡️ Anti-Sycophancy + Envio...")
    
    anti_prompt = f"""Avalie criticamente estes {len(games)} jogos da {config['name']}:

{json.dumps(games[:5], indent=2)}

Backtesting: {bt.get('avg_hits', 0)}/{config['pick']} média, máx {bt.get('max_hits', 0)}

Identifique:
1. Pontos fracos (padrões repetitivos, distribuição ruim)
2. Nota de qualidade (0-100)
3. Sugestões de melhoria

Seja CRÍTICO e HONESTO."""

    anti_response, anti_source = ask_ai(anti_prompt, 0.3)
    quality_score = 50
    if anti_response:
        import re
        numbers = re.findall(r'\b(\d{1,3})\b', anti_response)
        for n in numbers:
            if 0 <= int(n) <= 100:
                quality_score = int(n)
                break
        log(f"🛡️ Anti-Sycophancy ({anti_source}): Qualidade {quality_score}/100")
    
    # Montar resultado
    elapsed = time.time() - start_time
    result = {
        "version": "v13.0-symbiosis",
        "lottery": config["name"],
        "lottery_type": lottery_type,
        "timestamp": datetime.now().isoformat(),
        "contests_analyzed": len(contests),
        "latest_contest": contests[0]["number"] if contests else 0,
        "ai_engines": {
            "primary": f"Groq ({GROQ_MODEL})" if GROQ_API_KEY else "N/A",
            "secondary": f"Ollama ({OLLAMA_MODEL})",
            "ai_used": ai_source
        },
        "statistics": {
            "avg_evens": stats.get("avg_evens", 0),
            "avg_sum": stats.get("avg_sum", 0),
            "std_sum": stats.get("std_sum", 0)
        },
        "thesis_heatmap": heatmap,
        "backtesting": bt,
        "quality_score": quality_score,
        "games": games,
        "elapsed_seconds": round(elapsed, 1)
    }
    
    # Salvar output
    os.makedirs("output", exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    output_file = f"output/symbiosis_{lottery_type}_{ts}.json"
    with open(output_file, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    log(f"💾 Salvo: {output_file}")
    
    # Enviar ao Telegram
    games_text = ""
    for i, game in enumerate(games):
        pares = sum(1 for n in game if n % 2 == 0)
        games_text += f"J{i+1}: {game} ({pares}P)\n"
    
    tg_msg = f"""🌐 <b>SIAOL-PRO v13.0 SYMBIOSIS</b>
🎯 <b>{config['name']}</b> | Concurso #{contests[0]['number'] if contests else '?'}

📊 <b>Análise:</b>
• Concursos: {len(contests)}
• Pares médios: {stats.get('avg_evens', 0):.1f}/{config['pick']}
• Soma média: {stats.get('avg_sum', 0):.0f}

🔥 <b>Tese Dominante:</b> {dominant if heatmap else 'N/A'}

🧠 <b>Motor IA:</b> {ai_source.upper()} ({GROQ_MODEL if ai_source == 'groq' else OLLAMA_MODEL})

🔬 <b>Backtesting:</b> {bt.get('avg_hits', 0)}/{config['pick']} média (máx {bt.get('max_hits', 0)})

🛡️ <b>Qualidade:</b> {quality_score}/100

🎰 <b>JOGOS ({len(games)}):</b>
<code>{games_text}</code>

⏱️ Tempo: {elapsed:.0f}s"""

    if send_telegram(tg_msg):
        log("📱 Telegram: Enviado!")
    
    # Salvar no Supabase
    for game in games:
        supabase_post("lottery_predictions", {
            "lottery_type": lottery_type,
            "predicted_numbers": game,
            "metadata": json.dumps({
                "version": "v13.0-symbiosis",
                "ai_source": ai_source,
                "quality": quality_score,
                "backtesting_avg": bt.get("avg_hits", 0)
            })
        })
    log("☁️ Supabase: Predições salvas!")
    
    # Broadcast para outras IAs
    broadcast_to_ais("knowledge_sharing", "manus_orchestrator", "prediction", {
        "lottery": lottery_type,
        "games_count": len(games),
        "backtesting_avg": bt.get("avg_hits", 0),
        "quality_score": quality_score,
        "dominant_thesis": dominant if heatmap else "N/A",
        "ai_engine": ai_source,
        "timestamp": datetime.now().isoformat()
    })
    
    log(f"\n{'='*60}")
    log(f"✅ CICLO SYMBIOSIS CONCLUÍDO em {elapsed:.0f}s")
    log(f"{'='*60}")
    
    return result

# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    lottery = sys.argv[1] if len(sys.argv) > 1 else "megasena"
    num_games = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    
    if lottery == "all":
        for lt in ["megasena", "lotofacil", "quina", "lotomania"]:
            ng = 20 if lt == "lotomania" else 10
            run_symbiosis_cycle(lt, ng)
            time.sleep(5)
    else:
        if lottery not in LOTTERY_CONFIGS:
            print(f"Loteria inválida: {lottery}")
            print(f"Opções: {', '.join(LOTTERY_CONFIGS.keys())}, all")
            sys.exit(1)
        run_symbiosis_cycle(lottery, num_games)
