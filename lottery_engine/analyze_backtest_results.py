import json
import os
from collections import defaultdict
from datetime import datetime

def load_knowledge_base(file_path="/home/ubuntu/knowledge_base.json"):
    if not os.path.exists(file_path):
        return {"observations": [], "metrics": [], "strategic_insights": []}
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_knowledge_base(knowledge_base, file_path="/home/ubuntu/knowledge_base.json"):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(knowledge_base, f, indent=4, ensure_ascii=False)

def analyze_backtest_results(knowledge_base):
    all_game_hits = []
    for metric in knowledge_base["metrics"]:
        if metric["type"] == "backtest_run":
            all_game_hits.extend(metric["results"])

    if not all_game_hits:
        return "Nenhum resultado de backtest encontrado para análise."

    # Análise básica: Contagem total de acertos por categoria
    total_hits = defaultdict(int)
    for game_hits in all_game_hits:
        for key, value in game_hits.items():
            if key.startswith("hits_"):
                total_hits[key] += value
    
    # Identificar jogos com melhor desempenho (ex: mais hits_2_1 ou hits_3_1)
    best_performing_games = sorted(all_game_hits, key=lambda x: x.get("hits_3_1", 0) + x.get("hits_2_1", 0), reverse=True)

    insights = []
    insights.append("### Análise de Resultados do Backtest\n")
    insights.append("**Contagem Total de Acertos por Categoria:**\n")
    for category, count in total_hits.items():
        insights.append(f"- {category}: {count}\n")
    insights.append("\n")

    if best_performing_games:
        insights.append("**Jogos com Melhor Desempenho (baseado em hits_3_1 e hits_2_1):**\n")
        for i, game in enumerate(best_performing_games[:3]): # Top 3 jogos
            insights.append(f"- Game {game['game_id']}: Dezenas={game['dezenas']}, Trevos={game['trevos']}, Total Hits (3_1 + 2_1) = {game.get('hits_3_1', 0) + game.get('hits_2_1', 0)}\n")
    
    # Adicionar uma observação geral sobre a necessidade de refinar a estratégia
    insights.append("\n**Observação:** Os resultados atuais refletem a estratégia de geração de jogos aprimorada, que incorpora a predição do modelo e padrões históricos. O próximo passo é usar esses insights para refinar ainda mais a estratégia, buscando aumentar os acertos de categorias superiores.")

    return "".join(insights)

if __name__ == "__main__":
    kb = load_knowledge_base()
    analysis_report = analyze_backtest_results(kb)
    
    # Adicionar o relatório de análise como um insight estratégico
    kb["strategic_insights"].append({
        "timestamp": datetime.now().isoformat(),
        "analysis_type": "backtest_summary",
        "report": analysis_report
    })
    save_knowledge_base(kb)
    print("Análise do backtest salva na base de conhecimento.")
    print(analysis_report)
