"""
SIAOL-PRO v11.0 - ANTI-SYCOPHANCY ENGINE
Motor de Combate ao Viés de Concordância
Desafia as predições do motor de ML para identificar fraquezas e otimizar a precisão.
"""
import os
import json
import numpy as np
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

class AntiSycophancyEngine:
    """Desafia as predições do motor de ML para identificar fraquezas e otimizar a precisão."""

    def __init__(self):
        self.session_id = datetime.now().isoformat()
        print(f"[ANTI-SYC] Sessão iniciada: {self.session_id}")

    def analyze_prediction_weaknesses(self, lottery_type, predicted_numbers, historical_data):
        """Analisa as fraquezas de uma predição baseada em dados históricos."""
        print(f"[ANTI-SYC] Analisando fraquezas para {lottery_type} com predição: {predicted_numbers}")
        
        weaknesses = []
        sorted_numbers = sorted(predicted_numbers)
        
        # Regra 1: Verificar se a predição é muito agrupada demais (Salto de Dezena)
        # Para Mega-Sena e Quina, adicionar o critério de 'Salto de Dezena' (distância máxima entre números sorteados)
        # para evitar jogos muito agrupados ou muito espalhados.
        if lottery_type in ["megasena", "quina"]:
            max_jump = 0
            for i in range(len(sorted_numbers) - 1):
                jump = sorted_numbers[i+1] - sorted_numbers[i]
                if jump > max_jump:
                    max_jump = jump
            
            # Limite arbitrário para salto de dezena (pode ser ajustado)
            if max_jump > 15: 
                weaknesses.append("Salto de Dezena muito alto: números muito espalhados.")
            if max_jump < 3 and len(predicted_numbers) > 3: # Evitar agrupamentos extremos
                weaknesses.append("Salto de Dezena muito baixo: números muito agrupados.")

        # Regra 2: Verificar padrões de vácuo (números que não saem há muito tempo)
        # Se a predição inclui muitos números em 'vácuo' que historicamente não saem juntos
        # Esta é uma simplificação, idealmente precisaria de análise mais profunda de frequência
        for num in predicted_numbers:
            frequency = sum(1 for draw in historical_data if num in draw['numbers'])
            if frequency < (len(historical_data) * 0.05): # Se o número saiu em menos de 5% dos sorteios
                weaknesses.append(f"Número {num} tem baixa frequência histórica.")

        # Regra 3: Verificar simetria (distribuição dos números no volante)
        # Uma predição com todos os números em um canto do volante pode ser uma fraqueza
        # Esta é uma regra heurística e depende do layout do volante de cada loteria
        # Exemplo simplificado: verificar se todos os números estão na primeira metade
        max_number = 60 if lottery_type == "megasena" else 80 if lottery_type == "lotomania" else 25 if lottery_type == "lotofacil" else 80 # Ajustar conforme loteria
        first_half_count = sum(1 for num in predicted_numbers if num <= max_number / 2)
        if first_half_count == len(predicted_numbers):
            weaknesses.append("Todos os números estão na primeira metade do volante (falta de simetria).")
        elif first_half_count == 0:
            weaknesses.append("Todos os números estão na segunda metade do volante (falta de simetria).")

        # Regra 4: Padrões de DNA (sequências ou repetições improváveis)
        # Se a predição contiver sequências muito longas ou repetições de padrões improváveis
        # Exemplo: 1, 2, 3, 4, 5, 6
        for i in range(len(sorted_numbers) - 2):
            if sorted_numbers[i+1] == sorted_numbers[i] + 1 and sorted_numbers[i+2] == sorted_numbers[i+1] + 1:
                weaknesses.append("Sequência de 3 ou mais números consecutivos detectada.")

        if not weaknesses:
            weaknesses.append("Nenhuma fraqueza estatística óbvia detectada.")

        return weaknesses

    def provide_counter_arguments(self, weaknesses):
        """Gera contra-argumentos para as fraquezas identificadas."""
        counter_arguments = []
        if "Salto de Dezena muito alto: números muito espalhados." in weaknesses:
            counter_arguments.append("Embora os números estejam espalhados, sorteios com grandes saltos ocorrem e podem surpreender.")
        if "Salto de Dezena muito baixo: números muito agrupados." in weaknesses:
            counter_arguments.append("Números agrupados podem ser uma estratégia de 'bolão' e já ocorreram em sorteios passados.")
        if "falta de simetria" in str(weaknesses):
            counter_arguments.append("A simetria é uma heurística, e sorteios assimétricos são comuns.")
        if "baixa frequência histórica" in str(weaknesses):
            counter_arguments.append("Números de baixa frequência podem estar 'maduros' para sair, seguindo a lei dos grandes números.")
        if "Sequência de 3 ou mais números consecutivos detectada." in weaknesses:
            counter_arguments.append("Sequências são raras, mas não impossíveis, e podem ser uma aposta de alto risco/recompensa.")
        if not counter_arguments:
            counter_arguments.append("A predição parece robusta, sem contra-argumentos fortes.")
        return counter_arguments

    def run_anti_sycophancy_check(self, lottery_type, predicted_numbers, historical_data):
        """Executa o ciclo completo de combate ao viés de concordância."""
        print("\n" + "=" * 60)
        print(f"  ANTI-SYCOPHANCY CHECK - {lottery_type.upper()}")
        print("=" * 60)
        
        weaknesses = self.analyze_prediction_weaknesses(lottery_type, predicted_numbers, historical_data)
        counter_arguments = self.provide_counter_arguments(weaknesses)
        
        print("\n[ANTI-SYC] Fraquezas Identificadas:")
        for w in weaknesses:
            print(f"  - {w}")
            
        print("\n[ANTI-SYC] Contra-Argumentos:")
        for ca in counter_arguments:
            print(f"  - {ca}")
            
        return {
            "weaknesses": weaknesses,
            "counter_arguments": counter_arguments
        }

def main():
    """Teste do motor Anti-Sycophancy."""
    print("=" * 60)
    print("  SIAOL-PRO v11.0 - ANTI-SYCOPHANCY ENGINE")
    print("=" * 60)
    
    # Exemplo de uso
    lottery_type = "megasena"
    predicted_numbers = [5, 10, 15, 20, 25, 30] # Exemplo de predição
    
    # Dados históricos simulados (em um cenário real, viriam do Supabase)
    historical_data = [
        {'numbers': [1, 2, 3, 4, 5, 6]},
        {'numbers': [7, 8, 9, 10, 11, 12]},
        {'numbers': [1, 10, 20, 30, 40, 50]},
        {'numbers': [5, 15, 25, 35, 45, 55]},
        {'numbers': [1, 12, 23, 34, 45, 56]},
        {'numbers': [2, 4, 6, 8, 10, 12]},
        {'numbers': [1, 3, 5, 7, 9, 11]},
        {'numbers': [10, 11, 12, 20, 21, 22]},
        {'numbers': [1, 2, 3, 10, 11, 12]},
        {'numbers': [5, 10, 15, 20, 25, 30]}, # Duplicata para testar frequência
    ]
    
    engine = AntiSycophancyEngine()
    result = engine.run_anti_sycophancy_check(lottery_type, predicted_numbers, historical_data)
    
    print("\n" + "=" * 60)
    print("  [CONCLUÍDO] Teste Anti-Sycophancy finalizado")
    print("=" * 60)

if __name__ == "__main__":
    main()
