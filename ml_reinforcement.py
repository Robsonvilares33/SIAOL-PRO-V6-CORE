"""
SIAOL-PRO v10.0 - REINFORCEMENT LEARNING ENGINE
Motor de Aprendizado por Reforço para Otimização Contínua
Ajusta automaticamente os pesos do modelo baseado em resultados reais vs. preditos.
"""
import os
import json
import numpy as np
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

class ReinforcementLearningEngine:
    """Motor de RL para otimização contínua do modelo de predição."""

    def __init__(self):
        self.session_id = datetime.now().isoformat()
        self.learning_rate = 0.01  # Taxa de aprendizado
        self.discount_factor = 0.95  # Fator de desconto
        self.epsilon = 0.1  # Exploração vs. Exploração
        
        # Pesos iniciais (podem ser ajustados)
        self.weights = {
            "frequency": 0.25,
            "gaps": 0.20,
            "sum_average": 0.15,
            "even_odd_ratio": 0.15,
            "recency": 0.15,
            "gematria": 0.10
        }
        
        print(f"[RL-ENGINE] Sessão iniciada: {self.session_id}")
        print(f"[RL-ENGINE] Pesos iniciais: {self.weights}")

    def calculate_prediction_accuracy(self, predicted_numbers, actual_numbers):
        """Calcula a acurácia da predição."""
        if not predicted_numbers or not actual_numbers:
            return 0.0
        
        matches = len(set(predicted_numbers) & set(actual_numbers))
        total = len(actual_numbers)
        accuracy = (matches / total) * 100
        
        return accuracy

    def calculate_reward(self, accuracy, confidence):
        """Calcula a recompensa baseada na acurácia e confiança."""
        # Recompensa é maior se a predição foi precisa E confiante
        reward = (accuracy / 100) * confidence
        return reward

    def update_weights(self, reward, predicted_numbers, actual_numbers, features):
        """Atualiza os pesos do modelo baseado na recompensa."""
        accuracy = self.calculate_prediction_accuracy(predicted_numbers, actual_numbers)
        
        # Calcular o erro
        error = 1.0 - (accuracy / 100)
        
        # Atualizar cada peso proporcionalmente à sua contribuição
        for feature_name, feature_value in features.items():
            if feature_name in self.weights:
                # Gradiente descendente
                gradient = error * feature_value
                self.weights[feature_name] -= self.learning_rate * gradient
                
                # Manter pesos entre 0 e 1
                self.weights[feature_name] = max(0.0, min(1.0, self.weights[feature_name]))
        
        # Normalizar pesos para que somem 1.0
        total_weight = sum(self.weights.values())
        if total_weight > 0:
            for key in self.weights:
                self.weights[key] /= total_weight
        
        return self.weights

    def evaluate_prediction_quality(self, lottery_type, prediction_id):
        """Avalia a qualidade de uma predição após o sorteio ocorrer."""
        import requests
        
        print(f"[RL] Avaliando predição {prediction_id} de {lottery_type}...")
        
        # Buscar a predição no Supabase
        url = f"{SUPABASE_URL}/rest/v1/lottery_predictions"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}"
        }
        
        try:
            response = requests.get(
                f"{url}?id=eq.{prediction_id}",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                predictions = response.json()
                if predictions:
                    prediction = predictions[0]
                    predicted_numbers = prediction.get("predicted_numbers", [])
                    
                    # Buscar o resultado real do sorteio
                    draw_number = prediction.get("draw_number")
                    lottery_response = requests.get(
                        f"{SUPABASE_URL}/rest/v1/lottery_data?lottery_type=eq.{lottery_type}&draw_number=eq.{draw_number}",
                        headers=headers,
                        timeout=10
                    )
                    
                    if lottery_response.status_code == 200:
                        lottery_data = lottery_response.json()
                        if lottery_data:
                            actual_numbers = lottery_data[0].get("numbers", [])
                            
                            # Calcular acurácia
                            accuracy = self.calculate_prediction_accuracy(predicted_numbers, actual_numbers)
                            confidence = prediction.get("confidence", 0)
                            reward = self.calculate_reward(accuracy, confidence)
                            
                            print(f"[RL] Acurácia: {accuracy:.1f}% | Confiança: {confidence:.1f}% | Recompensa: {reward:.3f}")
                            
                            return {
                                "prediction_id": prediction_id,
                                "lottery_type": lottery_type,
                                "accuracy": accuracy,
                                "confidence": confidence,
                                "reward": reward,
                                "predicted": predicted_numbers,
                                "actual": actual_numbers
                            }
        except Exception as e:
            print(f"[ERRO] Falha ao avaliar predição: {e}")
        
        return None

    def batch_evaluate_predictions(self, lottery_type, days_back=7):
        """Avalia um lote de predições dos últimos N dias."""
        import requests
        
        print(f"[RL] Avaliando predições de {lottery_type} dos últimos {days_back} dias...")
        
        url = f"{SUPABASE_URL}/rest/v1/lottery_predictions"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}"
        }
        
        cutoff_date = (datetime.now() - timedelta(days=days_back)).isoformat()
        
        try:
            response = requests.get(
                f"{url}?lottery_type=eq.{lottery_type}&created_at=gte.{cutoff_date}&order=created_at.desc",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                predictions = response.json()
                print(f"[RL] Encontradas {len(predictions)} predições para avaliar")
                
                results = []
                for prediction in predictions:
                    result = self.evaluate_prediction_quality(lottery_type, prediction.get("id"))
                    if result:
                        results.append(result)
                
                return results
        except Exception as e:
            print(f"[ERRO] Falha ao avaliar lote: {e}")
        
        return []

    def optimize_weights(self, lottery_type, evaluation_results):
        """Otimiza os pesos baseado nos resultados de avaliação."""
        if not evaluation_results:
            print("[RL] Sem resultados para otimizar")
            return
        
        print(f"[RL] Otimizando pesos baseado em {len(evaluation_results)} avaliações...")
        
        total_reward = 0
        for result in evaluation_results:
            accuracy = result.get("accuracy", 0)
            confidence = result.get("confidence", 0)
            reward = self.calculate_reward(accuracy, confidence)
            total_reward += reward
            
            # Atualizar pesos (simplificado)
            features = {
                "frequency": accuracy / 100,
                "gaps": 0.5,
                "sum_average": 0.5,
                "even_odd_ratio": 0.5,
                "recency": accuracy / 100,
                "gematria": 0.5
            }
            
            self.update_weights(reward, result.get("predicted"), result.get("actual"), features)
        
        avg_reward = total_reward / len(evaluation_results) if evaluation_results else 0
        print(f"[RL] Recompensa média: {avg_reward:.3f}")
        print(f"[RL] Novos pesos: {self.weights}")
        
        return self.weights

    def save_weights_to_supabase(self, lottery_type):
        """Salva os pesos otimizados no Supabase para persistência."""
        import requests
        
        url = f"{SUPABASE_URL}/rest/v1/system_logs"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }
        
        data = {
            "message": f"Pesos RL otimizados para {lottery_type}",
            "log_level": "RL_OPTIMIZATION",
            "metadata": {
                "source": "ml_reinforcement",
                "lottery_type": lottery_type,
                "weights": self.weights,
                "timestamp": datetime.now().isoformat()
            }
        }
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=10)
            if response.status_code in [201, 200]:
                print(f"[OK] Pesos salvos no Supabase")
                return True
        except Exception as e:
            print(f"[ERRO] Falha ao salvar pesos: {e}")
        
        return False

    def run_full_optimization_cycle(self, lottery_type, days_back=7):
        """Executa um ciclo completo de otimização."""
        print("\n" + "=" * 60)
        print(f"  CICLO DE OTIMIZAÇÃO RL - {lottery_type.upper()}")
        print("=" * 60)
        
        # Fase 1: Avaliar predições antigas
        evaluation_results = self.batch_evaluate_predictions(lottery_type, days_back)
        
        if evaluation_results:
            # Fase 2: Otimizar pesos
            self.optimize_weights(lottery_type, evaluation_results)
            
            # Fase 3: Salvar pesos
            self.save_weights_to_supabase(lottery_type)
            
            print(f"[OK] Ciclo de otimização concluído para {lottery_type}")
        else:
            print(f"[AVISO] Nenhuma predição para otimizar em {lottery_type}")

def main():
    """Teste do motor RL."""
    print("=" * 60)
    print("  SIAOL-PRO v10.0 - REINFORCEMENT LEARNING ENGINE")
    print("=" * 60)
    
    engine = ReinforcementLearningEngine()
    
    # Executar ciclo de otimização para cada loteria
    lotteries = ["lotofacil", "quina", "megasena"]
    
    for lottery in lotteries:
        engine.run_full_optimization_cycle(lottery, days_back=7)
    
    print("\n" + "=" * 60)
    print("  [CONCLUÍDO] Ciclo de RL finalizado")
    print("=" * 60)

if __name__ == "__main__":
    main()
