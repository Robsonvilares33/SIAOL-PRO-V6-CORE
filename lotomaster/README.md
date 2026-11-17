# Lotomaster

Aplicação web local, independente dos serviços atuais do SIAOL, para reproduzir as áreas públicas do MazuSoft nas nove modalidades da CAIXA: Mega-Sena, Lotofácil, Lotomania, Quina, Dia de Sorte, Dupla Sena, Timemania, Super Sete e +Milionária.

A paginação `/history` e a rota `/results` expõem `provenance.latest_lookup`, `recently_checked` e `verified`. Um resultado de consulta bem-sucedida reutilizado no cache de memória durante o TTL de 90 segundos preserva `last_successful_lookup_at` e `recently_checked`; cache de falha ou origem desconhecida emite aviso. Uma página vazia pedida com `before=1` não consulta o último concurso e informa origem desconhecida e aviso. `recently_checked` indica consulta recente ao Worker, não autenticação independente nem garantia de atualização do Worker. O assistente só indica arquivo completo se recebeu essa confirmação recente, chegou ao concurso 1 e não identificou lacunas ou aviso.

Registros SQLite legados são revalidados na leitura, inclusive modalidade, chave de concurso e campos especiais. O último concurso em cache é o maior **válido**; uma chave inválida, mesmo superior, não prova que o concurso exista e não move o recorte. Lacunas dentro da janela conhecida são tentadas novamente e sinalizadas se a recuperação falhar. Offline, lacunas acima do maior concurso válido são desconhecidas, não declaradas inexistentes; consulte os avisos de desatualização. Consultas de janela usam no máximo 500 chaves (100 no histórico, 300 nos resultados); seleção do último válido examina no máximo 2.048 registros por chamada e falha explicitamente ao esgotar o orçamento. Payloads SQLite acima de 65.536 bytes são tratados como inválidos. As leituras não apagam nem reparam automaticamente registros fora do recorte.

O fallback do navegador valida por modalidade e campos especiais antes de exibir ou armazenar, inclusive cache legado; entradas inválidas são descartadas. Na +Milionária, listas combinadas e campos de trevos devem concordar, sem depender da ordem. O assistente solicita o Time do Coração para gerar Timemania; na conferência a comparação ignora diferenças de caixa e espaços em branco.

## O que está incluído

- Painel de resultados oficiais mais recentes por modalidade.
- Consulta de concursos e exportação do histórico em CSV e TXT.
- Gerador aleatório com dezenas fixas/removidas, quantidade variável quando aplicável e filtros de soma, paridade e repetição.
- Regras especiais: mês da sorte, time do coração, dois sorteios, trevos e sete colunas.
- Simulador de jogos contra o último concurso oficial.
- Tabelas históricas para frequência, atrasos, pares/ímpares, repetidas, primos, Fibonacci, soma, pares/trincas, padrões, distribuição, tabelas binárias e estatísticas especiais.
- Calculadora combinatória de probabilidades.
- Cache SQLite local para resultados consultados.
- Assistente analítico explicável, exclusivamente local nos endpoints públicos do backend.
- Configuração no navegador para OpenAI Responses (incluindo GPT-6 Astra), Gemini, Anthropic e APIs compatíveis com OpenAI Chat Completions.
- Leitura paginada de até 500 concursos por análise da CAIXA, incluindo atraso por dezena, grade 10×10 e coocorrência das casas vizinhas da Lotomania.
- Atualização automática da interface a cada cinco minutos e fallback do navegador para a API pública da CAIXA por um Worker de leitura.

### Origem e atualização dos resultados

A conferência é informativa: confirme concurso, dezenas e premiação diretamente na CAIXA. `simulate` aceita um resultado enviado pelo cliente para compatibilidade, mas **não verifica sua autenticidade**; o novo campo `provenance` distingue essa situação de consulta ou cache do servidor. Os endpoints `statistics/from-draws` e `assistant/from-draws` também identificam dados enviados pelo cliente como não verificados. Valores de `source` dentro de dados enviados pelo cliente são apenas declarações, não prova.

Resultados podem vir do Worker, do cache do servidor ou do cache do navegador. Quando a atualização falha, os avisos permanecem visíveis enquanto o cache de memória é usado; o histórico pode ser parcial. A chave `latest:v2` do navegador não reutiliza a chave antiga, que poderia ter sido sobrescrita por um concurso histórico: até uma nova consulta bem-sucedida, a recuperação offline do último concurso pode ficar indisponível.

As estatísticas são descritivas, não preditivas. Frequências e atrasos não alteram a probabilidade de um sorteio futuro. A geração permanece aleatória e não pondera dezenas históricas. Não há probabilidades calibradas fora da amostra para dezenas individuais.

## Instalação e execução

No diretório raiz do repositório:

```bash
python3 -m pip install -r requirements.txt
uvicorn lotomaster.api:app --host 0.0.0.0 --port 8020
```

Abra `http://localhost:8020`. A documentação OpenAPI fica em `http://localhost:8020/api/docs` e o health check em `http://localhost:8020/api/v1/health`.

O primeiro acesso consulta a API pública da CAIXA. Concursos consultados ficam no arquivo `.lotomaster.sqlite3` na raiz do projeto, ignorado pelo Git. Para alterar o local do banco, defina `LOTOMASTER_DB_PATH`.

O backend e o fallback do navegador consultam a API oficial `https://servicebus2.caixa.gov.br/portaldeloterias/api` por um Cloudflare Worker público, somente de leitura, limitado aos nove endpoints de modalidades suportados e com CORS restrito ao site e ao preview autorizado. O código do Worker está em `cloudflare/workers/lotomaster-caixa-proxy.js`. O endereço usado pelo backend pode ser substituído pela variável `LOTOMASTER_CAIXA_PROXY_URL`. A aplicação não coleta dados por scraping do MazuSoft. Em Vercel, o banco SQLite fica em armazenamento temporário e pode ser reinicializado entre execuções; resultados atuais continuam sendo consultados na CAIXA. A interface confere novos concursos a cada cinco minutos enquanto está aberta.

O assistente do navegador permite que cada pessoa informe a própria chave e modelo. A chave fica em `sessionStorage` por padrão e só é enviada diretamente ao provedor selecionado após uma ação explícita; a opção de persistir neste dispositivo usa `localStorage` e não deve ser ativada em computador compartilhado. Nenhuma chave do proprietário é distribuída. APIs personalizadas precisam permitir chamadas cross-origin (CORS) do navegador e usar o protocolo escolhido.

Ao pedir análise, o navegador pagina os resultados públicos a partir do mais recente, até o concurso 1 ou até o limite de 500 concursos por análise. Se houver histórico anterior ao limite, ele não é incluído. Concursos indisponíveis no recorte são identificados e exigem aceite para análise parcial; a pessoa escolhe expressamente se envia esses dados ao provedor configurado. A origem não é verificada independentemente e o cache pode estar desatualizado. Concursos futuros ainda não existem: a interface acompanha resultados publicados, sem prevê-los. Sugestões da IA são experimentais, sem vantagem probabilística demonstrada. Custos, retenção e uso dos dados dependem do provedor e da chave pessoal.

Outras consultas de histórico usam janelas de até 300 concursos por modalidade; no modo de até 500, a interface usa páginas de até 100 e envia o recorte ao endpoint de estatísticas, não ao endpoint do assistente, que tem limite de 300. Para persistir e analisar todo o histórico oficial de forma compartilhada em uma hospedagem serverless, é necessário um armazenamento durável além do SQLite temporário.

## API principal

- `GET /api/v1/lotteries`
- `GET /api/v1/{modalidade}/latest`
- `GET /api/v1/{modalidade}/results?limit=30`
- `GET /api/v1/{modalidade}/history?limit=100&before=...`
- `GET /api/v1/{modalidade}/statistics?limit=50&table=frequency`
- `GET /api/v1/{modalidade}/assistant?limit=50`
- `POST /api/v1/{modalidade}/statistics/from-draws`
- `POST /api/v1/{modalidade}/assistant/from-draws`
- `POST /api/v1/{modalidade}/generate`
- `POST /api/v1/{modalidade}/simulate`
- `GET /api/v1/{modalidade}/probability`
- `GET /api/v1/{modalidade}/export.csv?limit=100`
- `GET /api/v1/{modalidade}/export.txt?limit=100`

### Segurança e compatibilidade das análises

- Os dois endpoints públicos do assistente sempre usam análise local, mesmo com `GEMINI_API_KEY` no servidor ou `use_gemini=true`; o parâmetro legado é aceito, mas ignorado. Não é necessário configurar credenciais. A função Python interna permite ativar Gemini explicitamente, e só deve ser usada em ambiente de confiança com autenticação, autorização, quotas e controles de custo apropriados; não a exponha diretamente.
- `statistics/from-draws` aceita de 1 a 500 concursos (antes 5.000); `assistant/from-draws`, de 1 a 300. O corpo de cada um é limitado a 1.000.000 bytes antes do parsing, inclusive em requisições por partes; acima disso retorna 413. Entradas inválidas retornam 422. Configure também limites de tamanho, tempo, concorrência e taxa no proxy de produção: limites por requisição não impedem abuso por volume ou por outras rotas.
- Cada concurso deve ter modalidade exata, inteiro positivo único e dezenas inteiras na quantidade e faixa da modalidade, sem repetição (exceto dígitos em colunas distintas do Super Sete). Campos especiais e ordem, quando enviados, devem ser coerentes. Dados suplementares opcionais ausentes não entram em suas respectivas estatísticas. A origem CAIXA exige segundo sorteio para Dupla Sena e trevos para +Milionária. Frequência geral do Super Sete conta presença por concurso, enquanto as tabelas por coluna contam por posição.
- `/simulate` valida resultados de todas as origens, exigindo os dados especiais do concurso para Dupla Sena, +Milionária, Dia de Sorte e Timemania. Exige também mês, time e trevos nos jogos das respectivas modalidades e rejeita campos incompatíveis. O gerador de Timemania exige informar o time. Uma entrada estruturalmente válida ainda não é autenticada; confirme prêmios na CAIXA.
- O gerador e conferidor da +Milionária aceitam apenas apostas simples de 6 dezenas e 2 trevos. A calculadora de probabilidade pode calcular seleções de mais trevos, mas isso não habilita sua geração ou conferência. Nos jogos gerados, trevos individuais são preservados; ao editar o campo de trevos, o novo valor se aplica a todos os jogos exibidos. O indicador de concurso especial em analytics agora se chama `marked_special_draws` (antes `officially_marked_special_draws`).
- Validação estrutural não prova que um histórico enviado pelo cliente é oficial. Alterações em formato da CAIXA podem causar rejeição; dados inválidos já armazenados podem causar erro na análise e devem ser verificados separadamente. O limite de corpo não protege as outras rotas nem restringe o tamanho da resposta da CAIXA no transporte.

Execute a suíte local sem depender da API da CAIXA (instale `pytest` e `httpx` no ambiente de testes):

```bash
python3 lotomaster/tests/offline_pytest.py
PYTHON="$(command -v python3)" node --test lotomaster/tests/test_frontend.js lotomaster/tests/test_review_regressions.js lotomaster/tests/test_latest_review.js
node lotomaster/tests/test_browser_cache.cjs
```

Veja [as fontes e o mapeamento público do MazuSoft](REFERENCE.md).

## Limites desta primeira versão

O simulador da +Milionária confere somente apostas simples de 6 dezenas e 2 trevos. Apostas múltiplas não são desdobradas nem têm prêmios ou valores calculados: o simulador as rejeita, inclusive quando geradas com mais de 2 trevos. Para confirmar a premiação, consulte a CAIXA.

Os fechamentos exaustivos, tabelas Premium, fórmulas proprietárias não documentadas e autenticação de terceiros não são reproduzidos. Nenhum serviço atual do SIAOL foi substituído; esta camada web possui pacote, rotas e persistência separados.
