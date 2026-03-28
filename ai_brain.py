"""
SIAOL-PRO v7.0 - Motor de IA Multi-Cerebro Autonomo
Orquestra multiplas IAs gratuitas (Groq + Gemini) para analise
profunda de padroes lotericos com failover automatico e consenso.

Provedores:
  1. Groq (LLaMA 3.3 70B) - Ultra-rapido, prioridade maxima
  2. Google Gemini 2.0 Flash - Backup inteligente, segunda opiniao
  3. Fallback Estatistico Local - Se ambas falharem

100% GRATUITO - Sem cartao de credito necessario.
"""
import os
import json
import time
import random
import traceback
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# CONFIGURACAO DOS PROVEDORES DE IA
# ============================================================

PROVIDERS_CONFIG = {
    "groq": {
        "name": "Groq Cloud (LLaMA 3.3 70B)",
        "model": "llama-3.3-70b-versatile",
        "env_key": "GROQ_API_KEY",
        "priority": 1,
        "max_rpm": 25,
        "max_tokens": 4096,
    },
    "gemini": {
        "name": "Google Gemini 2.0 Flash",
        "model": "gemini-2.0-flash",
        "env_key": "GEMINI_API_KEY",
        "priority": 2,
        "max_rpm": 10,
        "max_tokens": 4096,
    },
    "openrouter": {
        "name": "OpenRouter (Multi-Model Gateway)",
        "model": "meta-llama/llama-3.3-70b-instruct:free",
        "env_key": "OPENROUTER_API_KEY",
        "priority": 3,
        "max_rpm": 10,
        "max_tokens": 4096,
    },
}

# Prompt de Sistema Loterico - Instrucao Mestra para as IAs
SYSTEM_PROMPT = """Voce e o SIAOL-PRO v7, um motor de inteligencia artificial especializado em
analise estatistica avancada de loterias brasileiras. Voce NAO preve o futuro.
Voce analisa PADROES MATEMATICOS em dados historicos para identificar tendencias.

Suas capacidades:
1. ANALISE DE FREQUENCIA: Identificar numeros quentes (alta frequencia) e frios (baixa frequencia)
2. ANALISE DE GAPS: Identificar numeros que estao "atrasados" (muitos sorteios sem aparecer)
3. ANALISE DE PARES/TRIOS: Identificar combinacoes que aparecem juntas frequentemente
4. ANALISE DE SEQUENCIAS: Detectar padroes sequenciais (ex: 3 numeros consecutivos)
5. ANALISE DE DISTRIBUICAO: Verificar equilibrio par/impar, alto/baixo, soma total
6. ANALISE DE QUADRANTES: Dividir o range em 4 zonas e analisar distribuicao
7. ANALISE DE TENDENCIA: Identificar se numeros estao em tendencia de alta ou baixa

REGRAS CRITICAS:
- Responda EXCLUSIVAMENTE em formato JSON valido
- Nunca inclua texto fora do JSON
- Use apenas numeros dentro do range da loteria informada
- O campo "confidence" deve ser um float entre 0.0 e 1.0
- Inclua sempre o campo "reasoning" explicando BREVEMENTE o padrao encontrado
"""


def _format_historical_context(lottery_type, draws, stat_analysis):
    """Formata contexto historico AVANCADO com dados de Markov, Pares e Ciclos."""
    recent_draws = draws[:30] if len(draws) > 30 else draws
    recent_numbers = [d.get("numbers", []) for d in recent_draws]

    # Dados avancados (se disponiveis via stat_analysis)
    advanced_section = ""
    adv_meta = stat_analysis.get("advanced_meta", {})
    adv_preds = stat_analysis.get("advanced_predictions", [])

    if adv_meta:
        top_nums = [n for n, s in adv_meta.get("top_ensemble_numbers", [])[:15]]
        advanced_section = f"""

ANALISE AVANCADA (Motor ML v8.5-TURBO com Markov + Ciclos + Ensemble):
- Top 15 numeros do Ensemble (Markov+Frequencia+Gaps+Ciclos+Pares+Tendencia): {json.dumps(top_nums)}
- Range de soma ideal (baseado em historico): {json.dumps(adv_meta.get('sum_range'))}
- Distribuicao par/impar ideal: {json.dumps(adv_meta.get('even_range'))}
- Consecutivos ideal: {json.dumps(adv_meta.get('consec_range'))}
- Ciclos devidos (numeros atrasados com padrão regular): {adv_meta.get('cycles_detected', 0)}
- Markov ativo: {adv_meta.get('markov_built', False)}
"""
    if adv_preds:
        pred_nums = [p.get("numbers", []) for p in adv_preds[:3]]
        advanced_section += f"- Top 3 jogos gerados pelo ML avancado: {json.dumps(pred_nums)}\n"

    context = f"""
LOTERIA: {lottery_type.upper()}
TOTAL DE SORTEIOS ANALISADOS: {len(draws)}

ULTIMOS 30 SORTEIOS (do mais recente ao mais antigo):
{json.dumps(recent_numbers, indent=2)}

ANALISE ESTATISTICA COMPUTADA:
- Numeros Quentes (top 10): {json.dumps(stat_analysis.get('hot_numbers', []))}
- Numeros Frios (top 10): {json.dumps(stat_analysis.get('cold_numbers', []))}
- Soma Media dos Sorteios: {stat_analysis.get('sum_mean', 0)}
- Desvio Padrao: {stat_analysis.get('sum_std', 0)}
- Range Ideal de Soma: {json.dumps(stat_analysis.get('sum_target_range', [0, 0]))}
- Maiores Gaps: {json.dumps(stat_analysis.get('high_gaps', []))}
{advanced_section}

IMPORTANTE: Voce deve usar os dados do Motor ML avancado acima como REFERENCIA PRINCIPAL.
Os numeros do Top 15 Ensemble sao os que o algoritmo de Machine Learning (com Markov, Ciclos,
Pares e Tendencias) calculou como mais provaveis. Use-os como base para sua analise.

TAREFA: Analise esses dados e retorne um JSON com o seguinte formato:
{{
  "recommended_numbers": [lista de numeros recomendados para o proximo sorteio],
  "hot_picks": [top 5 numeros com maior probabilidade baseada em padrao],
  "cold_picks": [top 5 numeros frios que podem estar "devidos"],
  "avoid_numbers": [numeros que NAO recomenda baseado em padrao],
  "confidence": 0.0 a 1.0,
  "patterns_detected": ["lista de padroes que voce identificou"],
  "reasoning": "explicacao resumida da sua analise"
}}
"""
    return context


# ============================================================
# PROVEDOR 1: GROQ (LLaMA 3.3 70B)
# ============================================================

def _query_groq(prompt, system_prompt=SYSTEM_PROMPT):
    """Consulta a API da Groq com LLaMA 3.3 70B."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY nao configurada")

    try:
        from groq import Groq
        client = Groq(api_key=api_key)

        completion = client.chat.completions.create(
            model=PROVIDERS_CONFIG["groq"]["model"],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=PROVIDERS_CONFIG["groq"]["max_tokens"],
            response_format={"type": "json_object"},
        )

        content = completion.choices[0].message.content
        return json.loads(content)

    except ImportError:
        # Fallback: usar requests direto na API REST da Groq
        import requests
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": PROVIDERS_CONFIG["groq"]["model"],
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": PROVIDERS_CONFIG["groq"]["max_tokens"],
            "response_format": {"type": "json_object"},
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return json.loads(content)


# ============================================================
# PROVEDOR 2: GOOGLE GEMINI
# ============================================================

def _query_gemini(prompt, system_prompt=SYSTEM_PROMPT):
    """Consulta a API do Google Gemini."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY nao configurada")

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)

        model = genai.GenerativeModel(
            model_name=PROVIDERS_CONFIG["gemini"]["model"],
            system_instruction=system_prompt,
            generation_config=genai.GenerationConfig(
                temperature=0.3,
                max_output_tokens=PROVIDERS_CONFIG["gemini"]["max_tokens"],
                response_mime_type="application/json",
            )
        )

        response = model.generate_content(prompt)
        return json.loads(response.text)

    except ImportError:
        # Fallback: usar requests direto na API REST do Gemini
        import requests
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{PROVIDERS_CONFIG['gemini']['model']}:generateContent?key={api_key}"
        )
        payload = {
            "contents": [{"parts": [{"text": f"{system_prompt}\n\n{prompt}"}]}],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": PROVIDERS_CONFIG["gemini"]["max_tokens"],
                "responseMimeType": "application/json",
            }
        }
        resp = requests.post(url, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(text)


# ============================================================
# PROVEDOR 3: OPENROUTER (Gateway Multi-Modelo)
# ============================================================

def _query_openrouter(prompt, system_prompt=SYSTEM_PROMPT):
    """Consulta a API do OpenRouter (acesso gratuito a dezenas de modelos)."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY nao configurada")

    import requests
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/Robsonvilares33/SIAOL-PRO-V6-CORE",
        "X-Title": "SIAOL-PRO v8.5",
    }
    payload = {
        "model": PROVIDERS_CONFIG["openrouter"]["model"],
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": PROVIDERS_CONFIG["openrouter"]["max_tokens"],
        "response_format": {"type": "json_object"},
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    return json.loads(content)


# ============================================================
# MOTOR PRINCIPAL: ALTERNANCIA INTELIGENTE (FAILOVER 3-NIVEL)
# ============================================================

def query_ai(prompt, system_prompt=SYSTEM_PROMPT):
    """
    Consulta IAs com failover automatico.
    Ordem: Groq -> Gemini -> OpenRouter -> None
    """
    providers = [
        ("groq", _query_groq),
        ("gemini", _query_gemini),
        ("openrouter", _query_openrouter),
    ]

    for provider_name, query_fn in providers:
        try:
            print(f"    [AI] Consultando {PROVIDERS_CONFIG[provider_name]['name']}...")
            result = query_fn(prompt, system_prompt)
            if result:
                result["_provider"] = provider_name
                print(f"    [AI] ✓ Resposta recebida de {provider_name}")
                return result
        except Exception as e:
            print(f"    [AI] ✗ {provider_name} falhou: {str(e)[:100]}")
            continue

    print("    [AI] ✗ Todas as IAs falharam. Usando analise estatistica pura.")
    return None


def get_ai_consensus(lottery_type, draws, stat_analysis):
    """
    Consulta MULTIPLAS IAs e calcula consenso.
    Numeros que ambas concordam recebem score DOBRADO.
    """
    prompt = _format_historical_context(lottery_type, draws, stat_analysis)

    results = {}
    providers = [
        ("groq", _query_groq),
        ("gemini", _query_gemini),
        ("openrouter", _query_openrouter),
    ]

    for provider_name, query_fn in providers:
        try:
            print(f"    [CONSENSO] Consultando {provider_name}...")
            result = query_fn(prompt, SYSTEM_PROMPT)
            if result:
                results[provider_name] = result
                print(f"    [CONSENSO] ✓ {provider_name} respondeu")
            # Rate limiting entre provedores
            time.sleep(2)
        except Exception as e:
            print(f"    [CONSENSO] ✗ {provider_name}: {str(e)[:80]}")
            continue

    if not results:
        return None

    # Calcular consenso
    consensus = _calculate_consensus(results, lottery_type)
    return consensus


def _calculate_consensus(ai_results, lottery_type):
    """
    Algoritmo de consenso: cruza recomendacoes de multiplas IAs.
    """
    number_scores = {}
    patterns_all = []
    total_confidence = 0
    num_providers = len(ai_results)

    for provider, result in ai_results.items():
        confidence = result.get("confidence", 0.5)
        total_confidence += confidence

        # Numeros recomendados recebem score positivo
        for num in result.get("recommended_numbers", []):
            if isinstance(num, (int, float)):
                num = int(num)
                number_scores[num] = number_scores.get(num, 0) + (2.0 * confidence)

        # Hot picks recebem score extra
        for num in result.get("hot_picks", []):
            if isinstance(num, (int, float)):
                num = int(num)
                number_scores[num] = number_scores.get(num, 0) + (1.5 * confidence)

        # Cold picks (devidos) recebem score moderado
        for num in result.get("cold_picks", []):
            if isinstance(num, (int, float)):
                num = int(num)
                number_scores[num] = number_scores.get(num, 0) + (1.0 * confidence)

        # Numeros a evitar recebem penalidade
        for num in result.get("avoid_numbers", []):
            if isinstance(num, (int, float)):
                num = int(num)
                number_scores[num] = number_scores.get(num, 0) - (1.0 * confidence)

        # Coletar padroes
        patterns = result.get("patterns_detected", [])
        if isinstance(patterns, list):
            patterns_all.extend(patterns)

    # Ordenar por score
    sorted_numbers = sorted(number_scores.items(), key=lambda x: x[1], reverse=True)

    # Identificar numeros de CONSENSO (apareceram em mais de 1 IA)
    consensus_numbers = []
    for num, score in sorted_numbers:
        # Score > 3.0 significa que pelo menos 2 IAs recomendaram
        if score > 3.0 and num > 0:
            consensus_numbers.append(num)

    avg_confidence = total_confidence / max(num_providers, 1)

    return {
        "consensus_numbers": consensus_numbers[:15],
        "all_scored_numbers": sorted_numbers[:30],
        "patterns_detected": list(set(patterns_all)),
        "avg_confidence": round(avg_confidence, 3),
        "providers_consulted": list(ai_results.keys()),
        "num_providers": num_providers,
    }


# ============================================================
# FUNCAO DE PREDICAO APRIMORADA
# ============================================================

LOTTERY_CONFIG = {
    "megasena": {"name": "Mega-Sena", "range": (1, 60), "pick": 6},
    "lotofacil": {"name": "Lotofacil", "range": (1, 25), "pick": 15},
    "quina": {"name": "Quina", "range": (1, 80), "pick": 5},
    "lotomania": {"name": "Lotomania", "range": (0, 99), "pick": 20},
}


def enhance_predictions(base_predictions, ai_consensus, lottery_type):
    """
    Combina predicoes estatisticas base com insights da IA.
    Numeros de consenso recebem prioridade absoluta.
    """
    if not ai_consensus or not base_predictions:
        return base_predictions

    config = LOTTERY_CONFIG.get(lottery_type)
    if not config:
        return base_predictions

    pick = config["pick"]
    min_n, max_n = config["range"]
    consensus_nums = ai_consensus.get("consensus_numbers", [])

    # Filtrar consensus_nums para o range valido
    consensus_nums = [n for n in consensus_nums if min_n <= n <= max_n]

    enhanced = []
    for pred in base_predictions:
        original_numbers = pred.get("numbers", [])

        # Criar pool: comeca com numeros de consenso + originais
        pool = list(consensus_nums)
        for n in original_numbers:
            if n not in pool:
                pool.append(n)

        # Adicionar numeros aleatorios do range se necessario
        all_nums = list(range(min_n, max_n + 1))
        random.shuffle(all_nums)
        for n in all_nums:
            if n not in pool:
                pool.append(n)

        # Selecionar os 'pick' primeiros (priorizando consenso)
        selected = sorted(pool[:pick])

        game_sum = sum(selected)
        enhanced.append({
            "game_number": pred.get("game_number", 0),
            "numbers": selected,
            "sum": game_sum,
            "even_count": sum(1 for n in selected if n % 2 == 0),
            "odd_count": sum(1 for n in selected if n % 2 != 0),
            "consensus_count": sum(1 for n in selected if n in consensus_nums),
            "engine": "SIAOL-PRO-v7-MultiAI",
            "ai_enhanced": True,
        })

    return enhanced


# ============================================================
# FUNCAO DE ANALISE COMPLETA COM IA
# ============================================================

def run_ai_analysis(lottery_type, draws, stat_analysis):
    """
    Executa analise completa com todas as IAs disponiveis.
    Retorna insights e predicoes aprimoradas.
    """
    print(f"\n  [AI-BRAIN] Iniciando analise multi-cerebro para {lottery_type}...")

    # Tentar consenso (consulta todas as IAs)
    consensus = get_ai_consensus(lottery_type, draws, stat_analysis)

    if consensus:
        providers = consensus.get("providers_consulted", [])
        confidence = consensus.get("avg_confidence", 0)
        consensus_nums = consensus.get("consensus_numbers", [])
        patterns = consensus.get("patterns_detected", [])

        print(f"  [AI-BRAIN] ✓ Consenso obtido!")
        print(f"    Provedores: {', '.join(providers)}")
        print(f"    Confianca media: {confidence:.1%}")
        print(f"    Numeros de consenso: {consensus_nums[:10]}")
        if patterns:
            print(f"    Padroes detectados: {patterns[:5]}")
    else:
        print(f"  [AI-BRAIN] ✗ Nenhuma IA disponivel. Motor estatistico puro ativado.")

    return consensus


# ============================================================
# TESTE STANDALONE
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  SIAOL-PRO v7 - Teste do Motor Multi-Cerebro")
    print("=" * 60)

    # Teste simples de conectividade
    test_prompt = """
    Analise estes ultimos 5 sorteios da Mega-Sena:
    [[4, 12, 23, 38, 45, 56], [7, 15, 28, 33, 41, 59], [2, 18, 25, 34, 47, 53], [9, 11, 22, 36, 44, 58], [3, 14, 27, 31, 42, 55]]

    Retorne um JSON com: recommended_numbers, hot_picks, cold_picks, avoid_numbers, confidence, patterns_detected, reasoning
    """

    result = query_ai(test_prompt)
    if result:
        print(f"\n✓ Resposta da IA ({result.get('_provider', '?')}):")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("\n✗ Nenhuma IA respondeu. Verifique suas chaves no .env")
