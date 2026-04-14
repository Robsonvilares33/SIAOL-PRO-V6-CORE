"""
SIAOL-PRO v10.0 - LLAMA BRIDGE
Ponte de comunicação entre o sistema na nuvem e a IA local (Llama/Ollama) no terminal do usuário.
Permite processamento pesado de ML sem custos de API.
"""
import os
import json
import requests
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Configuração do Llama local (via Ollama)
LLAMA_LOCAL_URL = os.getenv("LLAMA_LOCAL_URL", "http://localhost:11434")
LLAMA_MODEL = os.getenv("LLAMA_MODEL", "llama2")

class LlamaBridge:
    """Ponte para comunicação com IA local."""

    def __init__(self):
        self.local_url = LLAMA_LOCAL_URL
        self.model = LLAMA_MODEL
        self.session_id = datetime.now().isoformat()
        print(f"[LLAMA-BRIDGE] Sessão iniciada: {self.session_id}")
        self.check_connection()

    def check_connection(self):
        """Verifica se o Llama local está disponível."""
        try:
            response = requests.get(f"{self.local_url}/api/tags", timeout=5)
            if response.status_code == 200:
                print(f"[OK] Llama local conectado em {self.local_url}")
                models = response.json().get("models", [])
                print(f"[INFO] Modelos disponíveis: {len(models)}")
                return True
            else:
                print(f"[AVISO] Llama local respondeu com status {response.status_code}")
                return False
        except Exception as e:
            print(f"[ERRO] Não foi possível conectar ao Llama local: {e}")
            print(f"[INSTRUÇÃO] Certifique-se de que o Ollama está rodando: ollama serve")
            return False

    def analyze_patterns(self, lottery_type, historical_data, num_predictions=5):
        """Usa IA local para analisar padrões nos dados históricos."""
        print(f"[ANALYZE] Analisando padrões de {lottery_type} com Llama...")

        prompt = f"""
        Você é um especialista em análise estatística de loterias brasileiras e um crítico rigoroso de suas próprias conclusões.
        Seu objetivo é realizar uma análise profunda e autocrítica para gerar as melhores predições possíveis.
        
        Tipo de Loteria: {lottery_type}
        Últimos 50 sorteios: {json.dumps(historical_data[-50:], indent=2)}
        
        Siga o processo de Cadeia de Pensamento (Chain of Thought) abaixo para chegar à sua conclusão:
        
        **Passo 1: Análise Inicial**
        Baseado nos dados históricos fornecidos, faça uma análise inicial para identificar:
        - Números mais frequentes (hot numbers)
        - Números menos frequentes (cold numbers)
        - Padrões de sequências consecutivas (se houver)
        - Distribuição par/ímpar
        - Uma primeira proposta de {num_predictions} jogos estratégicos.
        
        **Passo 2: Crítica Interna (Anti-Sycophancy)**
        Agora, atue como seu próprio "Advogado do Diabo". Questione as predições iniciais. Quais são as fraquezas estatísticas? Há algum viés óbvio? Considere:
        - Salto de Dezena (números muito agrupados ou muito espalhados)
        - Padrões de Vácuo (números de baixa frequência que não saem há muito tempo)
        - Simetria (distribuição dos números no volante)
        - Padrões de DNA (sequências ou repetições improváveis)
        
        **Passo 3: Refinamento e Predição Final**
        Com base na análise inicial e na crítica interna, refine suas predições. Qual é a melhor proposta de {num_predictions} jogos estratégicos agora? Justifique a escolha final, abordando as fraquezas identificadas e como elas foram mitigadas ou aceitas.
        
        Responda em JSON com a seguinte estrutura:
        {{
            "hot_numbers": [lista de números quentes],
            "cold_numbers": [lista de números frios],
            "sequences": [padrões detectados],
            "even_odd_ratio": razão par/ímpar,
            "initial_recommended_games": [lista de {num_predictions} jogos recomendados na análise inicial],
            "weaknesses_identified": [lista de fraquezas encontradas na crítica interna],
            "counter_arguments_to_weaknesses": [lista de contra-argumentos ou justificativas para as fraquezas],
            "final_recommended_games": [lista de {num_predictions} jogos recomendados após o refinamento],
            "confidence": score de confiança (0-100),
            "reasoning": explicação detalhada do processo de CoT, incluindo análise inicial, crítica e refinamento.
        }}
        """

        try:
            response = requests.post(
                f"{self.local_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "temperature": 0.7
                },
                timeout=60
            )

            if response.status_code == 200:
                result = response.json()
                response_text = result.get("response", "")
                
                # Tentar extrair JSON da resposta
                try:
                    # Procurar por JSON na resposta
                    start_idx = response_text.find("{")
                    end_idx = response_text.rfind("}") + 1
                    if start_idx != -1 and end_idx > start_idx:
                        json_str = response_text[start_idx:end_idx]
                        analysis = json.loads(json_str)
                        print(f"[OK] Análise concluída com confiança {analysis.get('confidence', 0)}%")
                        return analysis
                except json.JSONDecodeError:
                    print(f"[AVISO] Não foi possível extrair JSON da resposta")
                    return {"raw_response": response_text}
            else:
                print(f"[ERRO] Status {response.status_code} ao chamar Llama")
        except requests.exceptions.Timeout:
            print(f"[ERRO] Timeout ao conectar ao Llama (>60s)")
        except Exception as e:
            print(f"[ERRO] Falha na análise com Llama: {e}")

        return None

    def generate_prediction_explanation(self, lottery_type, predicted_numbers):
        """Gera uma explicação em linguagem natural para as predições."""
        print(f"[EXPLAIN] Gerando explicação para predição de {lottery_type}...")

        prompt = f"""
        Você é um especialista em loterias brasileiras.
        
        Loteria: {lottery_type}
        Números Preditos: {predicted_numbers}
        
        Gere uma explicação breve (máximo 3 linhas) sobre por que esses números foram selecionados,
        considerando padrões estatísticos, frequência histórica e tendências recentes.
        """

        try:
            response = requests.post(
                f"{self.local_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "temperature": 0.5
                },
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                explanation = result.get("response", "").strip()
                print(f"[OK] Explicação gerada")
                return explanation
        except Exception as e:
            print(f"[ERRO] Falha ao gerar explicação: {e}")

        return "Predição gerada com base em análise estatística avançada."

    def save_analysis_to_supabase(self, lottery_type, analysis):
        """Salva a análise do Llama no Supabase para auditoria."""
        if not SUPABASE_URL or not SUPABASE_KEY:
            return False

        url = f"{SUPABASE_URL}/rest/v1/system_logs"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }

        data = {
            "message": f"Análise Llama para {lottery_type}",
            "log_level": "LLAMA_ANALYSIS",
            "metadata": {
                "source": "llama_bridge",
                "lottery_type": lottery_type,
                "analysis": analysis,
                "timestamp": datetime.now().isoformat()
            }
        }

        try:
            response = requests.post(url, headers=headers, json=data, timeout=10)
            return response.status_code in [201, 200]
        except Exception as e:
            print(f"[ERRO] Falha ao salvar análise no Supabase: {e}")
            return False

def main():
    """Teste da ponte Llama."""
    bridge = LlamaBridge()

    if bridge.check_connection():
        # Dados de exemplo (últimos 10 sorteios da Lotofácil)
        sample_data = [
            {"draw_number": 3650, "numbers": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]},
            {"draw_number": 3651, "numbers": [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]},
        ]

        # Analisar padrões
        analysis = bridge.analyze_patterns("lotofacil", sample_data)
        if analysis:
            print(f"[RESULTADO] {json.dumps(analysis, indent=2, ensure_ascii=False)}")
            bridge.save_analysis_to_supabase("lotofacil", analysis)

        # Gerar explicação
        explanation = bridge.generate_prediction_explanation("lotofacil", [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15])
        print(f"[EXPLICAÇÃO] {explanation}")
    else:
        print("[INSTRUÇÃO] Para usar o Llama local:")
        print("  1. Instale o Ollama: https://ollama.ai")
        print("  2. Execute: ollama pull llama2")
        print("  3. Inicie o servidor: ollama serve")
        print("  4. Configure as variáveis de ambiente:")
        print("     export LLAMA_LOCAL_URL=http://localhost:11434")
        print("     export LLAMA_MODEL=llama2")

if __name__ == "__main__":
    main()
