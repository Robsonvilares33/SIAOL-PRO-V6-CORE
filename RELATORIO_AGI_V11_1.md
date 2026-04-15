# 🚀 SIAOL-PRO v11.1 AGI - Relatório de Implantação e Guia de Operação

## 1. Visão Geral da Implantação
O sistema **SIAOL-PRO v11.1 AGI** foi implantado com sucesso no terminal Ubuntu, operando de forma 100% autônoma e local. A arquitetura agora conta com uma verdadeira "mente" de Inteligência Artificial rodando na própria máquina, sem depender de APIs pagas (como OpenAI ou Anthropic) para a análise crítica.

### Componentes Ativos no Terminal:
*   **Ollama v0.20.7:** Servidor de IA local.
*   **Qwen2.5:3b:** Modelo de linguagem de alta performance e baixo peso, atuando como o "cérebro" do SIAOL-PRO.
*   **Claude Code v2.1.109:** CLI oficial da Anthropic instalado e configurado para usar o Ollama como backend.
*   **Aider v0.86.2:** Ferramenta open-source de AI Pair Programming para edições autônomas de código.
*   **Telegram Engine:** Bot (`@siaol_pro_v10_bot`) conectado e enviando predições em tempo real.

---

## 2. O Ciclo Autônomo (Orquestrador)
O script `siaol_autonomous.py` é o coração do sistema. Ele executa as seguintes 7 fases de forma totalmente independente:

1.  **Coleta de Dados Reais:** Conecta-se à API da Caixa Econômica Federal e baixa os últimos 100 concursos da loteria solicitada.
2.  **Análise Estatística:** Calcula a frequência de cada dezena, o atraso (vácuo) e a proporção de números pares/ímpares.
3.  **Mapa de Calor de Teses:** Avalia as 10 Teses do SIAOL-PRO (DNA Numérico, Vácuo Estatístico, Quantum Collapse, etc.) com base nos dados reais e define qual tese está mais "quente".
4.  **Análise IA Local (Qwen2.5):** O modelo Qwen2.5 recebe todos os dados estatísticos e define a estratégia do dia, gerando um JSON com os números recomendados.
5.  **Geração de Jogos:** O motor cria os jogos (10 para Mega/Quina/Lotofácil, 20 para Lotomania), aplicando a **preferência estrita por números pares** solicitada pelo usuário.
6.  **Anti-Sycophancy Check:** A IA local analisa os próprios jogos gerados, procurando falhas, padrões óbvios ou excesso de repetição, e atribui uma nota de qualidade (0 a 100).
7.  **Envio e Armazenamento:** Os jogos são formatados e enviados automaticamente para o Telegram do usuário, além de serem salvos no banco de dados Supabase e em arquivos JSON locais.

---

## 3. Guia de Operação Contínua

O sistema está pronto para rodar a qualquer momento. Como ele está no terminal Ubuntu, você pode acioná-lo de várias formas.

### Comando Manual Completo
Para rodar o ciclo para todas as loterias (Mega-Sena, Lotofácil, Quina e Lotomania):
```bash
cd /home/ubuntu/SIAOL_LIVE && python3 siaol_autonomous.py
```

### Comando Específico por Loteria
Para rodar apenas para uma ou mais loterias específicas:
```bash
cd /home/ubuntu/SIAOL_LIVE && python3 siaol_autonomous.py megasena lotomania
```

### Automação Semanal (Cronjob)
Para que o sistema rode sozinho toda semana (ex: segundas e quintas às 10h da manhã), você pode adicionar a seguinte linha ao seu `crontab`:
```bash
0 10 * * 1,4 cd /home/ubuntu/SIAOL_LIVE && python3 siaol_autonomous.py >> /home/ubuntu/SIAOL_LIVE/cron.log 2>&1
```

---

## 4. Evolução e Aprendizado Contínuo
Sempre que a IA local (Qwen2.5) identificar um novo padrão ou o módulo Anti-Sycophancy detectar uma fraqueza recorrente, você pode usar o **Aider** ou o **Claude Code** (que agora rodam localmente) para pedir que eles mesmos atualizem o código do `siaol_autonomous.py`.

Exemplo de comando para evolução autônoma:
```bash
aider --model ollama/qwen2.5:3b siaol_autonomous.py -m "Adicione uma nova tese chamada 'Salto Quântico' que penaliza jogos com números consecutivos."
```

O SIAOL-PRO AGI agora é um organismo vivo no seu terminal. Ele coleta, pensa, critica a si mesmo e entrega o resultado diretamente na palma da sua mão via Telegram.
