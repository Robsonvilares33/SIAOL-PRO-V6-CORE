import pandas as pd
import numpy as np

def calculate_gematria(number):
    s = str(number)
    return sum(int(digit) for digit in s)

def is_fibonacci(n):
    if n < 0: return False
    if n == 0 or n == 1: return True
    a, b = 0, 1
    while b < n:
        a, b = b, a + b
    return b == n

def add_gematria_features(df, columns):
    for col in columns:
        df[f'{col}_gematria'] = df[col].apply(calculate_gematria).astype(float)
    return df

def add_fibonacci_features(df, columns, max_number=60):
    fib_sequence = [0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55]
    for col in columns:
        df[f'{col}_is_fibonacci'] = df[col].apply(lambda x: 1 if x in fib_sequence else 0).astype(float)
    return df

def apply_feature_engineering(df):
    dezena_columns = [f'Dezena{i}' for i in range(1, 7)]

    # Garantir que as features de gematria e fibonacci sejam criadas para TODAS as dezenas
    df = add_gematria_features(df, dezena_columns)
    df = add_fibonacci_features(df, dezena_columns, max_number=60)

    df['soma_gematria_total'] = df[[f'{col}_gematria' for col in dezena_columns]].sum(axis=1).astype(float)
    df['count_fibonacci'] = df[[f'{col}_is_fibonacci' for col in dezena_columns]].sum(axis=1).astype(float)

    # Features Combinadas e Não-Lineares
    for i in range(1, 7):
        col = f'Dezena{i}'
        
        # Interações entre gematria e dezenas originais
        df[f'{col}_gema_x_dez'] = (df[col] * df[f'{col}_gematria']).astype(float)
        df[f'{col}_gema_dif'] = (df[col] - df[f'{col}_gematria']).astype(float)

        # Diferenças entre dezenas consecutivas
        if i > 1:
            prev_col = f'Dezena{i-1}'
            df[f'diff_{prev_col}_{col}'] = (df[col] - df[prev_col]).astype(float)

        # Novas interações Gematria-Fibonacci para todas as dezenas
        df[f'{col}_gematria_x_fibonacci'] = (df[f'{col}_gematria'] * df[f'{col}_is_fibonacci']).astype(float)
        
        # Novas transformações não-lineares (log da Gematria)
        df[f'{col}_gematria_log'] = df[f'{col}_gematria'].apply(lambda x: np.log1p(x) if x > 0 else 0).astype(float)

    # Estatísticas agregadas das dezenas
    df['dezenas_mean'] = df[dezena_columns].mean(axis=1).astype(float)
    df['dezenas_std'] = df[dezena_columns].std(axis=1).astype(float)
    df['dezenas_min'] = df[dezena_columns].min(axis=1).astype(float)
    df['dezenas_max'] = df[dezena_columns].max(axis=1).astype(float)

    # ==========================================================================
    # NOVAS FEATURES AVANÇADAS NA SOMA DAS DEZENAS
    # ==========================================================================

    # Calcular a soma das dezenas (target para a previsão)
    df['soma_dezenas'] = df[[f'Dezena{i}' for i in range(1, 7)]].sum(axis=1).astype(float)

    # Features de Variação e Dispersão
    df['std_dezenas'] = df[[f'Dezena{i}' for i in range(1, 7)]].std(axis=1).astype(float)
    df['range_dezenas'] = (df[[f'Dezena{i}' for i in range(1, 7)]].max(axis=1) - df[[f'Dezena{i}' for i in range(1, 7)]].min(axis=1)).astype(float)
    df['median_dezenas'] = df[[f'Dezena{i}' for i in range(1, 7)]].median(axis=1).astype(float)

    # Features de Agrupamento (contagem de dezenas em faixas)
    df['count_0_10'] = df[[f'Dezena{i}' for i in range(1, 7)]].apply(lambda x: ((x >= 0) & (x <= 10)).sum(), axis=1).astype(float)
    df['count_11_20'] = df[[f'Dezena{i}' for i in range(1, 7)]].apply(lambda x: ((x >= 11) & (x <= 20)).sum(), axis=1).astype(float)
    df['count_21_30'] = df[[f'Dezena{i}' for i in range(1, 7)]].apply(lambda x: ((x >= 21) & (x <= 30)).sum(), axis=1).astype(float)
    df['count_31_40'] = df[[f'Dezena{i}' for i in range(1, 7)]].apply(lambda x: ((x >= 31) & (x <= 40)).sum(), axis=1).astype(float)
    df['count_41_50'] = df[[f'Dezena{i}' for i in range(1, 7)]].apply(lambda x: ((x >= 41) & (x <= 50)).sum(), axis=1).astype(float)

    # Interações de Gematria/Fibonacci com a Soma das Dezenas
    df['soma_gematria_total_x_soma_dezenas'] = (df['soma_gematria_total'] * df['soma_dezenas']).astype(float)
    df['count_fibonacci_div_soma_dezenas'] = (df['count_fibonacci'] / (df['soma_dezenas'] + 1)).astype(float) # Adiciona 1 para evitar divisão por zero

    return df

if __name__ == "__main__":
    # Exemplo de DataFrame de resultados da loteria
    data = {
        'Concurso': [1, 2, 3],
        'Dezena1': [3, 6, 10],
        'Dezena2': [4, 10, 15],
        'Dezena3': [18, 35, 20],
        'Dezena4': [25, 40, 30],
        'Dezena5': [33, 45, 40],
        'Dezena6': [47, 47, 50],
        'Trevos': ['2,6', '1,3', '1,4']
    }
    df_test = pd.DataFrame(data)

    print("DataFrame Original:")
    print(df_test)

    df_engineered = apply_feature_engineering(df_test.copy())

    print("\nDataFrame com Features de Gematria e Fibonacci (Aprimorado com Interações):")
    print(df_engineered.head())
