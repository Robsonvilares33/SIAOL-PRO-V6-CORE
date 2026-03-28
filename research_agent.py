"""
SIAOL-PRO v9.0 - AGENTE DE PESQUISA (The Researcher)
Varre o codigo, busca novas tecnicas e propoe mutacoes estruturais.
"""
import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

def get_research_suggestions(current_genome):
    """Consulta a IA para novas tecnicas baseado no genoma atual."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None
    
    from groq import Groq
    client = Groq(api_key=api_key)
    
    prompt = f"""Voce e um pesquisador senior de IA especializado em algoritmos preditivos.
O sistema SIAOL-PRO v9 esta usando o seguinte genoma de pesos e parametros:
{json.dumps(current_genome, indent=2)}

Sua tarefa:
1. Pesquise mentalmente tecnicas de Machine Learning para series temporais numericas.
2. Identifique UMA tecnica que ainda nao parece estar sendo explorada (estamos usando Markov, Janelas, Ciclos, Pares, Tendencia).
3. Sugira como integrar essa tecnica como um novo 'peso' ou modificacao estrutural.

Responda em JSON:
{{
  "technique_name": "Nome da tecnica",
  "reasoning": "Por que isso ajudaria na Lotofacil?",
  "proposed_mutation": "descricao para o Agente Engenheiro"
}}"""

    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": "Voce e um pesquisador de IA."}, {"role": "user", "content": prompt}],
            temperature=0.5,
            response_format={"type": "json_object"}
        )
        return json.loads(completion.choices[0].message.content)
    except Exception as e:
        print(f"Erro na pesquisa: {e}")
        return None

if __name__ == "__main__":
    from auto_evolve import load_genome
    genome = load_genome()
    suggestion = get_research_suggestions(genome)
    if suggestion:
        print(json.dumps(suggestion, indent=2))
