import json
import os
import pandas as pd
import numpy as np
from collections import Counter
from datetime import datetime
from analyze_backtest_results import load_knowledge_base, save_knowledge_base

def detect_anomalies(file_path="/home/ubuntu/milionaria_results.json"):
    if not os.path.exists(file_path):
        print(f"Erro: Arquivo {file_path} não encontrado.")
        return None

    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    df = pd.DataFrame(data)
    
    # Calcular atrasos (quantos concursos atrás cada dezena apareceu pela última vez)
    all_dezenas = list(range(1, 51))
    last_seen = {d: -1 for d in all_dezenas}
    delays = {d: [] for d in all_dezenas}

    for idx, row in df.iterrows():
        concurso = row['concurso']
        dezenas_sorteadas = row['dezenas']
        for d in all_dezenas:
            if d in dezenas_sorteadas:
                if last_seen[d] != -1:
                    delays[d].append(concurso - last_seen[d])
                last_seen[d] = concurso

    current_concurso = df.iloc[-1]['concurso']
    current_delays = {d: current_concurso - last_seen[d] for d in all_dezenas}

    # Identificar dezenas "anômalas" (atraso significativamente acima da média histórica)
    anomaly_report = []
    anomaly_report.append("### Relatório de Detecção de Anomalias e Atrasos (Neuroplasticidade)")
    
    overdue_dezenas = []
    for d, delay in current_delays.items():
        avg_delay = np.mean(delays[d]) if delays[d] else 0
        if delay > avg_delay * 1.5 and avg_delay > 0:
            overdue_dezenas.append((d, delay, avg_delay))

    overdue_dezenas = sorted(overdue_dezenas, key=lambda x: x[1], reverse=True)
    
    anomaly_report.append("\n**Dezenas com Atraso Anômalo (Candidatas Fortes para Correção):**")
    for d, delay, avg in overdue_dezenas[:5]:
        anomaly_report.append(f"- Dezena {d}: Atraso atual de {delay} concursos (Média histórica: {avg:.1f})")

    # Anomalias de Soma (Somas extremas nos últimos 5 concursos)
    recent_sums = [sum(row['dezenas']) for _, row in df.tail(5).iterrows()]
    avg_sum = np.mean([sum(row['dezenas']) for _, row in df.iterrows()])
    anomaly_report.append(f"\n**Análise de Tendência de Soma Recente:**")
    anomaly_report.append(f"- Média histórica da soma: {avg_sum:.2f}")
    anomaly_report.append(f"- Somas dos últimos 5 concursos: {recent_sums}")

    report_str = "\n".join(anomaly_report)
    print(report_str)

    # Salvar na base de conhecimento
    kb = load_knowledge_base()
    kb["strategic_insights"].append({
        "timestamp": datetime.now().isoformat(),
        "analysis_type": "anomaly_detection",
        "report": report_str
    })
    save_knowledge_base(kb)

    return overdue_dezenas

if __name__ == "__main__":
    detect_anomalies()
