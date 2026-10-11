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

As estatísticas são descritivas, não preditivas. Frequências e atrasos não alteram a probabilidade de um sorteio futuro.

## Instalação e execução

No diretório raiz do repositório:

```bash
python3 -m pip install -r requirements.txt
uvicorn lotomaster.api:app --host 0.0.0.0 --port 8020
```

Abra `http://localhost:8020`. A documentação OpenAPI fica em `http://localhost:8020/api/docs` e o health check em `http://localhost:8020/api/v1/health`.

O primeiro acesso consulta a API pública da CAIXA. Concursos consultados ficam no arquivo `.lotomaster.sqlite3` na raiz do projeto, ignorado pelo Git. Para alterar o local do banco, defina `LOTOMASTER_DB_PATH`.

## API principal

- `GET /api/v1/lotteries`
- `GET /api/v1/{modalidade}/latest`
- `GET /api/v1/{modalidade}/results?limit=30`
- `GET /api/v1/{modalidade}/statistics?limit=50&table=frequency`
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
