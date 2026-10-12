# Lotomaster

Aplicação web local, independente dos serviços atuais do SIAOL, para reproduzir as áreas públicas do MazuSoft nas nove modalidades da CAIXA: Mega-Sena, Lotofácil, Lotomania, Quina, Dia de Sorte, Dupla Sena, Timemania, Super Sete e +Milionária.

## O que está incluído

- Painel de resultados oficiais mais recentes por modalidade.
- Consulta de concursos e exportação do histórico em CSV e TXT.
- Gerador aleatório com dezenas fixas/removidas, quantidade variável quando aplicável e filtros de soma, paridade e repetição.
- Regras especiais: mês da sorte, time do coração, dois sorteios, trevos e sete colunas.
- Simulador de jogos contra o último concurso oficial.
- Tabelas históricas para frequência, atrasos, pares/ímpares, repetidas, primos, Fibonacci, soma, pares/trincas, padrões, distribuição, tabelas binárias e estatísticas especiais.
- Calculadora combinatória de probabilidades.
- Cache SQLite local para resultados consultados.
- Assistente analítico explicável; Gemini opcional para resumir estatísticas descritivas.
- Atualização automática da interface a cada cinco minutos e fallback do navegador diretamente para a API pública da CAIXA quando a hospedagem bloquear a consulta do backend.

As estatísticas são descritivas, não preditivas. Frequências e atrasos não alteram a probabilidade de um sorteio futuro. A geração permanece aleatória e não pondera dezenas históricas. Não há probabilidades calibradas fora da amostra para dezenas individuais.

## Instalação e execução

No diretório raiz do repositório:

```bash
python3 -m pip install -r requirements.txt
uvicorn lotomaster.api:app --host 0.0.0.0 --port 8020
```

Abra `http://localhost:8020`. A documentação OpenAPI fica em `http://localhost:8020/api/docs` e o health check em `http://localhost:8020/api/v1/health`.

O primeiro acesso consulta a API pública da CAIXA. Concursos consultados ficam no arquivo `.lotomaster.sqlite3` na raiz do projeto, ignorado pelo Git. Para alterar o local do banco, defina `LOTOMASTER_DB_PATH`.

O backend consulta diretamente `https://servicebus2.caixa.gov.br/portaldeloterias/api`; o navegador também pode consultar essa mesma API oficial como fallback. A aplicação não coleta dados por scraping do MazuSoft. Em Vercel, o banco SQLite fica em armazenamento temporário e pode ser reinicializado entre execuções; resultados atuais continuam sendo consultados na CAIXA. A interface atualiza a cada cinco minutos enquanto está aberta.

Para habilitar o resumo generativo, configure `GEMINI_API_KEY` como variável secreta no ambiente de hospedagem. Sem essa variável, o assistente continua disponível como análise estatística local explicável. O Gemini não escolhe dezenas com base em frequências nem afirma prever sorteios; a geração de bilhetes continua uniformemente aleatória, sujeita apenas às regras e restrições solicitadas.

O histórico é carregado sob demanda em janelas de até 300 concursos por modalidade. Para persistir e analisar todo o histórico oficial de forma compartilhada em uma hospedagem serverless, é necessário um armazenamento durável além do SQLite temporário.

## API principal

- `GET /api/v1/lotteries`
- `GET /api/v1/{modalidade}/latest`
- `GET /api/v1/{modalidade}/results?limit=30`
- `GET /api/v1/{modalidade}/statistics?limit=50&table=frequency`
- `GET /api/v1/{modalidade}/assistant?limit=50`
- `POST /api/v1/{modalidade}/statistics/from-draws`
- `POST /api/v1/{modalidade}/assistant/from-draws`
- `POST /api/v1/{modalidade}/generate`
- `POST /api/v1/{modalidade}/simulate`
- `GET /api/v1/{modalidade}/probability`
- `GET /api/v1/{modalidade}/export.csv?limit=100`
- `GET /api/v1/{modalidade}/export.txt?limit=100`

Execute a suíte local sem depender da API da CAIXA:

```bash
python3 -m unittest discover -s lotomaster/tests -v
```

Veja [as fontes e o mapeamento público do MazuSoft](REFERENCE.md).

## Limites desta primeira versão

Os fechamentos exaustivos, tabelas Premium, fórmulas proprietárias não documentadas e autenticação de terceiros não são reproduzidos. Nenhum serviço atual do SIAOL foi substituído; esta camada web possui pacote, rotas e persistência separados.
