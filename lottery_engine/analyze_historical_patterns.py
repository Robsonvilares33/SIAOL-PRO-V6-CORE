import json
import os
from collections import Counter
import numpy as np
from datetime import datetime
from analyze_backtest_results import load_knowledge_base, save_knowledge_base # Reutilizar funções de KB

def analyze_patterns(file_path="/home/ubuntu/milionaria_results.json"):
    if not os.path.exists(file_path):
        print(f"Erro: Arquivo de dados não encontrado em {file_path}")
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    all_dezenas = []
    all_trevos = []
    all_sums = []
    all_dezena_pairs = []
    all_dezena_triplets = []
    all_trevo_pairs = []
    even_odd_ratios = []
    high_low_ratios = []
    consecutive_counts = []

    for draw in data:
        dezenas = sorted(draw['dezenas'])
        trevos = sorted(draw['trevos'])

        all_dezenas.extend(dezenas)
        all_trevos.extend(trevos)
        all_sums.append(sum(dezenas))

        # Análise de pares/ímpares
        even_count = sum(1 for d in dezenas if d % 2 == 0)
        odd_count = len(dezenas) - even_count
        even_odd_ratios.append((even_count, odd_count))

        # Análise de altos/baixos (1-25 baixo, 26-50 alto)
        high_count = sum(1 for d in dezenas if d >= 26)
        low_count = len(dezenas) - high_count
        high_low_ratios.append((high_count, low_count))

        # Análise de números consecutivos
        consecutive = 0
        for i in range(len(dezenas) - 1):
            if dezenas[i+1] - dezenas[i] == 1:
                consecutive += 1
        consecutive_counts.append(consecutive)

        # Gerar pares e trios de dezenas
        for i in range(len(dezenas)):
            for j in range(i + 1, len(dezenas)):
                all_dezena_pairs.append(tuple(sorted((dezenas[i], dezenas[j]))))
            for j in range(i + 1, len(dezenas)):
                for k in range(j + 1, len(dezenas)):
                    all_dezena_triplets.append(tuple(sorted((dezenas[i], dezenas[j], dezenas[k]))))
        
        # Gerar pares de trevos
        if len(trevos) == 2:
            all_trevo_pairs.append(tuple(sorted(trevos)))

    # Frequência das dezenas
    dezena_counts = Counter(all_dezenas)
    most_common_dezenas = dezena_counts.most_common(10)

    # Frequência dos trevos
    trevo_counts = Counter(all_trevos)
    most_common_trevos = trevo_counts.most_common(2)

    # Frequência de pares de dezenas
    dezena_pair_counts = Counter(all_dezena_pairs)
    most_common_dezena_pairs = dezena_pair_counts.most_common(5)

    # Frequência de trios de dezenas
    dezena_triplet_counts = Counter(all_dezena_triplets)
    most_common_dezena_triplets = dezena_triplet_counts.most_common(5)

    # Frequência de pares de trevos
    trevo_pair_counts = Counter(all_trevo_pairs)
    most_common_trevo_pairs = trevo_pair_counts.most_common(1)

    # Estatísticas de pares/ímpares
    avg_even = np.mean([r[0] for r in even_odd_ratios])
    avg_odd = np.mean([r[1] for r in even_odd_ratios])

    # Estatísticas de altos/baixos
    avg_high = np.mean([r[0] for r in high_low_ratios])
    avg_low = np.mean([r[1] for r in high_low_ratios])

    # Estatísticas de números consecutivos
    avg_consecutive = np.mean(consecutive_counts)

    # Distribuição das somas
    sum_mean = np.mean(all_sums)
    sum_median = np.median(all_sums)
    sum_std = np.std(all_sums)

    print("\n--- Análise de Padrões Históricos ---")
    print("\nDezenas Mais Frequentes:")
    for dezena, count in most_common_dezenas:
        print(f"- Dezena {dezena}: {count} vezes")

    print("\nTrevos Mais Frequentes:")
    for trevo, count in most_common_trevos:
        print(f"- Trevo {trevo}: {count} vezes")

    print("\nPares de Dezenas Mais Frequentes:")
    for pair, count in most_common_dezena_pairs:
        print(f"- Par {pair}: {count} vezes")

    print("\nTrios de Dezenas Mais Frequentes:")
    for triplet, count in most_common_dezena_triplets:
        print(f"- Trio {triplet}: {count} vezes")

    print("\nPares de Trevos Mais Frequentes:")
    for pair, count in most_common_trevo_pairs:
        print(f"- Par {pair}: {count} vezes")

    print("\nEstatísticas da Soma das Dezenas:")
    print(f"- Média: {sum_mean:.2f}")
    print(f"- Mediana: {sum_median:.2f}")
    print(f"- Desvio Padrão: {sum_std:.2f}")

    print("\nEstatísticas de Par/Ímpar:")
    print(f"- Média de Pares: {avg_even:.2f}")
    print(f"- Média de Ímpares: {avg_odd:.2f}")

    print("\nEstatísticas de Alto/Baixo:")
    print(f"- Média de Altos (26-50): {avg_high:.2f}")
    print(f"- Média de Baixos (1-25): {avg_low:.2f}")

    print("\nEstatísticas de Números Consecutivos:")
    print(f"- Média de Consecutivos: {avg_consecutive:.2f}")

    # Adicionar insights à base de conhecimento
    kb = load_knowledge_base()
    insights_report = f"### Análise de Padrões Históricos Estendida\n\n**Dezenas Mais Frequentes:**\n" + \
                      "\n".join([f"- Dezena {d}: {c} vezes" for d, c in most_common_dezenas]) + \
                      f"\n\n**Trevos Mais Frequentes:**\n" + \
                      "\n".join([f"- Trevo {t}: {c} vezes" for t, c in most_common_trevos]) + \
                      f"\n\n**Pares de Dezenas Mais Frequentes:**\n" + \
                      "\n".join([f"- Par {p}: {c} vezes" for p, c in most_common_dezena_pairs]) + \
                      f"\n\n**Trios de Dezenas Mais Frequentes:**\n" + \
                      "\n".join([f"- Trio {t}: {c} vezes" for t, c in most_common_dezena_triplets]) + \
                      f"\n\n**Pares de Trevos Mais Frequentes:**\n" + \
                      "\n".join([f"- Par {p}: {c} vezes" for p, c in most_common_trevo_pairs]) + \
                      f"\n\n**Estatísticas da Soma das Dezenas:**\n- Média: {sum_mean:.2f}\n- Mediana: {sum_median:.2f}\n- Desvio Padrão: {sum_std:.2f}" + \
                      f"\n\n**Estatísticas de Par/Ímpar:**\n- Média de Pares: {avg_even:.2f}\n- Média de Ímpares: {avg_odd:.2f}" + \
                      f"\n\n**Estatísticas de Alto/Baixo:**\n- Média de Altos (26-50): {avg_high:.2f}\n- Média de Baixos (1-25): {avg_low:.2f}" + \
                      f"\n\n**Estatísticas de Números Consecutivos:**\n- Média de Consecutivos: {avg_consecutive:.2f}"
    
    kb["strategic_insights"].append({
        "timestamp": datetime.now().isoformat(),
        "analysis_type": "historical_patterns_extended",
        "report": insights_report
    })
    save_knowledge_base(kb)
    print("\nInsights de padrões históricos estendidos salvos na base de conhecimento.")

if __name__ == "__main__":
    analyze_patterns()
