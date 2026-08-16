import random
import json
import os
import joblib
import pandas as pd
import numpy as np
from feature_engineering import apply_feature_engineering
from collections import Counter
from anomaly_detector import detect_anomalies

def load_model(model_path="/home/ubuntu/milionaria_model.joblib"):
    if not os.path.exists(model_path):
        return None
    return joblib.load(model_path)

def load_training_log(log_path="/home/ubuntu/training_log_v4.json"):
    if not os.path.exists(log_path):
        return None
    with open(log_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def load_historical_data(file_path="/home/ubuntu/milionaria_results.json"):
    if not os.path.exists(file_path):
        return pd.DataFrame()
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return pd.DataFrame(data)

def get_historical_patterns(historical_df):
    all_dezenas = []
    all_trevos = []
    all_sums = []
    all_dezena_pairs = []
    all_dezena_triplets = []
    all_trevo_pairs = []

    for _, row in historical_df.iterrows():
        dezenas = sorted(row['dezenas'])
        trevos = sorted(row['trevos'])

        all_dezenas.extend(dezenas)
        all_trevos.extend(trevos)
        all_sums.append(sum(dezenas))

        for i in range(len(dezenas)):
            for j in range(i + 1, len(dezenas)):
                all_dezena_pairs.append(tuple(sorted((dezenas[i], dezenas[j]))))
            for j in range(i + 1, len(dezenas)):
                for k in range(j + 1, len(dezenas)):
                    all_dezena_triplets.append(tuple(sorted((dezenas[i], dezenas[j], dezenas[k]))))
        
        if len(trevos) == 2:
            all_trevo_pairs.append(tuple(sorted(trevos)))

    dezena_counts = Counter(all_dezenas)
    trevo_counts = Counter(all_trevos)
    dezena_pair_counts = Counter(all_dezena_pairs)
    dezena_triplet_counts = Counter(all_dezena_triplets)
    trevo_pair_counts = Counter(all_trevo_pairs)

    weighted_dezenas = []
    for dezena, count in dezena_counts.items():
        weighted_dezenas.extend([dezena] * count)
    
    weighted_trevos = []
    for trevo, count in trevo_counts.items():
        weighted_trevos.extend([trevo] * count)

    weighted_dezena_pairs = []
    for pair, count in dezena_pair_counts.items():
        weighted_dezena_pairs.extend([list(pair)] * count)

    weighted_dezena_triplets = []
    for triplet, count in dezena_triplet_counts.items():
        weighted_dezena_triplets.extend([list(triplet)] * count)

    weighted_trevo_pairs = []
    for pair, count in trevo_pair_counts.items():
        weighted_trevo_pairs.extend([list(pair)] * count)

    return {
        "weighted_dezenas": weighted_dezenas,
        "weighted_trevos": weighted_trevos,
        "weighted_dezena_pairs": weighted_dezena_pairs,
        "weighted_dezena_triplets": weighted_dezena_triplets,
        "weighted_trevo_pairs": weighted_trevo_pairs,
        "sum_mean": np.mean(all_sums),
        "sum_std": np.std(all_sums)
    }

def load_historical_data_for_fe(file_path="/home/ubuntu/milionaria_results.json", features=None):
    if not os.path.exists(file_path):
        return pd.DataFrame()
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    df = pd.DataFrame(data)
    
    dezenas_df = pd.DataFrame(df['dezenas'].tolist(), index=df.index)
    dezenas_df.columns = [f'Dezena{i+1}' for i in range(dezenas_df.shape[1])]
    df = pd.concat([df, dezenas_df], axis=1)
    
    for i in range(1, 7):
        df[f'Dezena{i}'] = pd.to_numeric(df[f'Dezena{i}'], errors='coerce')
    
    df.dropna(subset=[f'Dezena{i}' for i in range(1, 7)], inplace=True)
    df = df.sort_values(by='concurso').reset_index(drop=True)
    
    df_engineered = apply_feature_engineering(df.copy())

    if features:
        for col in features:
            if col in df_engineered.columns:
                df_engineered[col] = pd.to_numeric(df_engineered[col], errors='coerce')
    df_engineered.dropna(inplace=True)

    return df_engineered

def generate_strategic_game(model, features_used, historical_df, historical_patterns, anomaly_dezenas):
    if historical_df.empty:
        return None

    last_draw_features = historical_df.iloc[[-1]][features_used].copy()
    for col in features_used:
        if col in last_draw_features.columns:
            last_draw_features[col] = pd.to_numeric(last_draw_features[col], errors='coerce')
    last_draw_features.dropna(inplace=True)

    if last_draw_features.empty:
        return None

    predicted_sum = model.predict(last_draw_features)[0]

    dezenas = set()
    
    # Neuroplasticidade: Inserir dezenas anômalas (altamente atrasadas) com maior probabilidade
    if anomaly_dezenas and random.random() < 0.6:
        chosen_anomaly = random.choice(anomaly_dezenas)[0]
        dezenas.add(chosen_anomaly)

    if historical_patterns["weighted_dezena_triplets"] and random.random() < 0.7:
        chosen_triplet = random.choice(historical_patterns["weighted_dezena_triplets"])
        dezenas.update(chosen_triplet)

    if len(dezenas) < 6 and historical_patterns["weighted_dezena_pairs"] and random.random() < 0.9:
        chosen_pair = random.choice(historical_patterns["weighted_dezena_pairs"])
        new_dezenas_from_pair = [d for d in chosen_pair if d not in dezenas]
        if len(dezenas) + len(new_dezenas_from_pair) <= 6:
            dezenas.update(new_dezenas_from_pair)

    all_possible_dezenas = list(range(1, 51))
    random.shuffle(all_possible_dezenas)

    while len(dezenas) < 6:
        if random.random() < 0.8 and historical_patterns["weighted_dezenas"]:
            dezena = random.choice(historical_patterns["weighted_dezenas"])
        else:
            dezena = random.choice(all_possible_dezenas)
        if dezena not in dezenas:
            dezenas.add(dezena)
    dezenas = sorted(list(dezenas))

    current_dezenas_set = set(dezenas)
    current_sum = sum(current_dezenas_set)
    diff = int(predicted_sum - current_sum)

    for _ in range(300):
        if diff == 0: break
        dezena_list = list(current_dezenas_set)
        if not dezena_list: break
        old_dezena = random.choice(dezena_list)
        
        if diff > 0:
            potential_dezenas = [d for d in historical_patterns["weighted_dezenas"] if d > old_dezena and d not in current_dezenas_set]
            new_dezena = random.choice(potential_dezenas) if potential_dezenas else old_dezena + 1
        else:
            potential_dezenas = [d for d in historical_patterns["weighted_dezenas"] if d < old_dezena and d not in current_dezenas_set]
            new_dezena = random.choice(potential_dezenas) if potential_dezenas else old_dezena - 1
        
        if 1 <= new_dezena <= 50 and new_dezena not in current_dezenas_set:
            current_dezenas_set.discard(old_dezena)
            current_dezenas_set.add(new_dezena)
            current_sum = sum(current_dezenas_set)
            diff = int(predicted_sum - current_sum)

    trevos = set()
    if historical_patterns["weighted_trevo_pairs"] and random.random() < 0.99:
        chosen_trevo_pair = random.choice(historical_patterns["weighted_trevo_pairs"])
        trevos.update(chosen_trevo_pair)

    while len(trevos) < 2:
        trevo = random.choice(historical_patterns["weighted_trevos"])
        if trevo not in trevos:
            trevos.add(trevo)
    trevos = sorted(list(trevos))

    return {"dezenas": sorted(list(current_dezenas_set)), "trevos": trevos}

def generate_games(num_games=10, model=None, features_used=None, historical_df=None, historical_patterns=None, anomaly_dezenas=None):
    generated_games = {}
    for i in range(num_games):
        if model and features_used and historical_df is not None and historical_patterns is not None:
            game = generate_strategic_game(model, features_used, historical_df, historical_patterns, anomaly_dezenas)
            if game:
                generated_games[f"game_{i+1}"] = game
        else:
            dezenas = sorted(random.sample(range(1, 51), 6))
            trevos = sorted(random.sample(range(1, 7), 2))
            generated_games[f"game_{i+1}"] = {"dezenas": dezenas, "trevos": trevos}
    return generated_games

if __name__ == "__main__":
    model = load_model()
    training_log = load_training_log()
    historical_raw_df = load_historical_data()
    historical_patterns = get_historical_patterns(historical_raw_df)
    anomaly_dezenas = detect_anomalies()

    if model and training_log and not historical_raw_df.empty:
        features = training_log["features_used"]
        historical_df_for_fe = load_historical_data_for_fe(features=features)

        print("\nGerando 10 jogos estratégicos de ultra-potencial (Neuroplasticidade Ativa)...")
        games = generate_games(num_games=10, model=model, features_used=features, historical_df=historical_df_for_fe, historical_patterns=historical_patterns, anomaly_dezenas=anomaly_dezenas)
        for game_id, game in games.items():
            print(f"{game_id}: Dezenas={game['dezenas']}, Trevos={game['trevos']}")

        output_file = "/home/ubuntu/generated_strategic_games.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(games, f, indent=4, ensure_ascii=False)
        print(f"\nJogos estratégicos avançados salvos em {output_file}")
