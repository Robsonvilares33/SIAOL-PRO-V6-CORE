import json
import os
import pandas as pd
from datetime import datetime
from game_generation_strategy import load_model, load_training_log, load_historical_data_for_fe, generate_games, get_historical_patterns, load_historical_data

def check_hits(game_dezenas, game_trevos, draw_dezenas, draw_trevos):
    dezenas_hit = len(set(game_dezenas).intersection(draw_dezenas))
    trevos_hit = len(set(game_trevos).intersection(draw_trevos))
    return dezenas_hit, trevos_hit

def run_backtest(num_games_to_generate=10):
    print("Iniciando backtest...")

    model = load_model()
    training_log = load_training_log()
    historical_raw_df = load_historical_data()
    historical_patterns = get_historical_patterns(historical_raw_df)

    if model is None or training_log is None or historical_raw_df.empty or historical_patterns is None:
        print("Erro: Não foi possível carregar o modelo, log de treinamento, dados históricos ou padrões históricos para o backtest.")
        return

    features = training_log["features_used"]
    historical_df_for_fe = load_historical_data_for_fe()

    if historical_df_for_fe.empty:
        print("Erro: DataFrame histórico para feature engineering está vazio.")
        return

    # Gerar jogos estratégicos usando o modelo e padrões históricos
    generated_games_data = generate_games(num_games=num_games_to_generate, model=model, features_used=features, historical_df=historical_df_for_fe, historical_patterns=historical_patterns)
    
    if not generated_games_data:
        print("Nenhum jogo foi gerado para o backtest.")
        return

    backtest_results = []

    # Iterar sobre cada jogo gerado e verificar acertos em todos os sorteios históricos
    for game_id, game in generated_games_data.items():
        game_dezenas = game["dezenas"]
        game_trevos = game["trevos"]
        
        hits_summary = {
            "game_id": game_id,
            "dezenas": game_dezenas,
            "trevos": game_trevos,
            "hits_6_2": 0, "hits_6_1": 0, "hits_6_0": 0,
            "hits_5_2": 0, "hits_5_1": 0, "hits_5_0": 0,
            "hits_4_2": 0, "hits_4_1": 0,
            "hits_3_2": 0, "hits_3_1": 0,
            "hits_2_2": 0, "hits_2_1": 0
        }

        for _, draw in historical_raw_df.iterrows():
            draw_dezenas = draw["dezenas"]
            draw_trevos = draw["trevos"]

            dezenas_hit, trevos_hit = check_hits(game_dezenas, game_trevos, draw_dezenas, draw_trevos)

            if dezenas_hit == 6 and trevos_hit == 2: hits_summary["hits_6_2"] += 1
            elif dezenas_hit == 6 and trevos_hit == 1: hits_summary["hits_6_1"] += 1
            elif dezenas_hit == 6 and trevos_hit == 0: hits_summary["hits_6_0"] += 1
            elif dezenas_hit == 5 and trevos_hit == 2: hits_summary["hits_5_2"] += 1
            elif dezenas_hit == 5 and trevos_hit == 1: hits_summary["hits_5_1"] += 1
            elif dezenas_hit == 5 and trevos_hit == 0: hits_summary["hits_5_0"] += 1
            elif dezenas_hit == 4 and trevos_hit == 2: hits_summary["hits_4_2"] += 1
            elif dezenas_hit == 4 and trevos_hit == 1: hits_summary["hits_4_1"] += 1
            elif dezenas_hit == 3 and trevos_hit == 2: hits_summary["hits_3_2"] += 1
            elif dezenas_hit == 3 and trevos_hit == 1: hits_summary["hits_3_1"] += 1
            elif dezenas_hit == 2 and trevos_hit == 2: hits_summary["hits_2_2"] += 1
            elif dezenas_hit == 2 and trevos_hit == 1: hits_summary["hits_2_1"] += 1
        
        backtest_results.append(hits_summary)

    # Salvar resultados na base de conhecimento
    knowledge_base_path = "/home/ubuntu/knowledge_base.json"
    if os.path.exists(knowledge_base_path):
        with open(knowledge_base_path, "r", encoding="utf-8") as f:
            kb = json.load(f)
    else:
        kb = {"observations": [], "metrics": [], "strategic_insights": []}

    kb["metrics"].append({
        "timestamp": datetime.now().isoformat(),
        "type": "backtest_run",
        "results": backtest_results
    })

    with open(knowledge_base_path, "w", encoding="utf-8") as f:
        json.dump(kb, f, indent=4, ensure_ascii=False)

    print("Backtest concluído.")
    print("Resultados do backtest salvos na base de conhecimento.")

if __name__ == "__main__":
    run_backtest(num_games_to_generate=10) # Gerar 10 jogos para o backtest
