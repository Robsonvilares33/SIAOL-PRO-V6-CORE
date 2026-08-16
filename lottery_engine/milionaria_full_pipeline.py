import subprocess
import sys
import os

def run_script(script_path):
    print(f"--- Executando {os.path.basename(script_path)} ---")
    try:
        result = subprocess.run([sys.executable, script_path], capture_output=True, text=True, check=True)
        print(result.stdout)
        if result.stderr:
            print(f"Alertas/Erros:\n{result.stderr}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Erro ao executar {script_path}: {e}")
        print(f"Saída padrão: {e.stdout}")
        print(f"Saída de erro: {e.stderr}")
        return False

if __name__ == "__main__":
    print("====================================================")
    print("INICIANDO PIPELINE COMPLETO DA +MILIONÁRIA")
    print("====================================================")
    
    steps = [
        ("/home/ubuntu/update_milionaria_results.py", "Atualização de Resultados via Web"),
        ("/home/ubuntu/train_neural_factory_4.py", "Treinamento do Modelo XGBoost"),
        ("/home/ubuntu/analyze_historical_patterns.py", "Análise de Padrões Históricos"),
        ("/home/ubuntu/backtesting_framework.py", "Execução de Backtesting"),
        ("/home/ubuntu/analyze_backtest_results.py", "Análise de Resultados do Backtest"),
        ("/home/ubuntu/game_generation_strategy.py", "Geração de Jogos Estratégicos")
    ]
    
    success = True
    for script, description in steps:
        if not run_script(script):
            print(f"FALHA na etapa: {description}")
            success = False
            break
        print(f"SUCESSO na etapa: {description}\n")
    
    if success:
        print("====================================================")
        print("PIPELINE FINALIZADO COM SUCESSO")
        print("====================================================")
    else:
        print("====================================================")
        print("PIPELINE INTERROMPIDO DEVIDO A ERROS")
        print("====================================================")
