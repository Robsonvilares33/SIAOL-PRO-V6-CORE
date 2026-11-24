# Lotomaster

Aplicação web local e independente dos serviços atuais do SIAOL, que reúne recursos identificados nas áreas públicas das nove modalidades da CAIXA: Mega-Sena, Lotofácil, Lotomania, Quina, Dia de Sorte, Dupla Sena, Timemania, Super Sete e +Milionária. Não é uma reprodução integral dos sistemas ou algoritmos privados da MazuSoft.

A paginação `/history` e a rota `/results` expõem `provenance.latest_lookup`, `recently_checked` e `verified`. Um resultado de consulta bem-sucedida reutilizado no cache de memória durante o TTL de 90 segundos preserva `last_successful_lookup_at` e `recently_checked`; cache de falha ou origem desconhecida emite aviso. Uma página vazia pedida com `before=1` não consulta o último concurso e informa origem desconhecida e aviso. `recently_checked` indica consulta recente ao Worker, não autenticação independente nem garantia de atualização do Worker. O assistente só indica arquivo completo se recebeu essa confirmação recente, chegou ao concurso 1 e não identificou lacunas ou aviso.

Registros SQLite legados são revalidados na leitura, inclusive modalidade, chave de concurso e campos especiais. O último concurso em cache é o maior **válido**; uma chave inválida, mesmo superior, não prova que o concurso exista e não move o recorte. Lacunas dentro da janela conhecida são tentadas novamente e sinalizadas se a recuperação falhar. Offline, lacunas acima do maior concurso válido são desconhecidas, não declaradas inexistentes; consulte os avisos de desatualização. Consultas de janela usam no máximo 500 chaves (100 no histórico, 300 nos resultados); seleção do último válido examina no máximo 2.048 registros por chamada e falha explicitamente ao esgotar o orçamento. Payloads SQLite acima de 65.536 bytes são tratados como inválidos. As leituras não apagam nem reparam automaticamente registros fora do recorte.

O fallback do navegador valida por modalidade e campos especiais antes de exibir ou armazenar, inclusive cache legado; entradas inválidas são descartadas. Na +Milionária, listas combinadas e campos de trevos devem concordar, sem depender da ordem. O assistente solicita o Time do Coração para gerar Timemania; na conferência a comparação ignora diferenças de caixa e espaços em branco.

## O que está incluído

- Painel de resultados oficiais mais recentes por modalidade.
- Consulta paginada do histórico oficial por concurso (30, 50 ou 100 por página), com navegação por cursor e indicação de concursos indisponíveis; exportação recente em CSV, TXT e Excel (XLSX), até 100 concursos por arquivo.
- Gerador aleatório com dezenas fixas/removidas, pesos manuais opcionais e filtros de soma, paridade, repetidas, primos, Fibonacci, sequência, saltos e, na Lotofácil, distribuição por linha e coluna. Na Lotomania há filtros de mínimo/máximo para Q1–Q4 da grade 10×10 e contagens por quadrante em cada jogo. Opcionalmente, o gerador pode restringir dezenas ao conjunto local que acumula 80% das aparições nos até 1.000 concursos mais recentes presentes no cache; ordena por frequência decrescente e desempata pela dezena crescente. É descritivo e retrospectivo, não preditivo, e exige histórico no cache. O Super Sete não aceita filtros numéricos nem pesos.
- Desdobramentos exaustivos locais, sem gravação, com paginação de até 1.000 combinações por página, pool de até 100 dezenas, fixas opcionais e diagnósticos de aprovação/reprovação com todos os motivos locais. Modalidades com bônus ou colunas não são suportadas. Filtros de repetidas exigem o número explícito de um concurso de referência. Na Lotofácil há também o fechamento específico de 6–12 repetidas selecionadas do resultado anterior, igualmente paginado, com filtros e referência explícita quando repetidas são filtradas. É possível preparar para o conferidor somente os jogos exibidos, até o limite de 500 por envio; nada é encaminhado automaticamente. Nenhum fechamento garante prêmio ou reproduz algoritmos/garantias proprietários da MazuSoft.
- Contagem combinatória da Lotofácil para p dezenas por jogo, f dezenas fixas e r removidas: `C(25-f-r, p-f)`, com as entradas validadas. É apenas a quantidade de combinações compatíveis com as restrições, não gera nem salva jogos e não representa probabilidade de prêmio ou vantagem.
- Pesquisa histórica da Lotofácil por três critérios definidos localmente: conter todas as dezenas escolhidas, igualdade exata com as 15 dezenas ou não conter nenhuma das escolhidas. A busca utiliza apenas os concursos recebidos; um recorte parcial ou com lacunas não equivale ao histórico completo, e a origem dos dados enviados não é autenticada pelo servidor. A implementação não afirma equivalência com as fórmulas ou a ferramenta da MazuSoft.
- Regras especiais na conferência: mês da sorte, time do coração, dois sorteios, trevos e sete colunas. Bônus por jogo são preservados por padrão quando os jogos são encaminhados; substituição coletiva exige ação explícita. A +Milionária aceita apostas de 6–12 dezenas e 2–6 trevos no gerador, na conferência simples/histórica e na calculadora. Cada bilhete múltiplo equivale a `C(n,6) × C(t,2)` subapostas simples.
- Simulador de jogos contra o último concurso oficial.
- Tabelas históricas para frequência, atrasos, pares/ímpares, repetidas, primos, Fibonacci, soma, pares/trincas, padrões, distribuição, tabelas binárias e estatísticas especiais. Em Dia de Sorte, `months-repeat` compara apenas concursos consecutivos e informa cortes por lacunas; repetições sem par consecutivo disponível são marcadas como indisponíveis, não como zero observado.
- Calculadora combinatória de probabilidades para as nove modalidades, com contagens exatas, chances por faixa e tratamento sem dupla contagem de “qualquer prêmio”. Dia de Sorte e Timemania incluem eventos especiais; Super Sete permite opções por coluna. Na +Milionária, as dez faixas oficiais cobrem apostas de 6–12 dezenas e 2–6 trevos; faixas distintas podem se sobrepor no mesmo bilhete.
- Cache SQLite local para resultados consultados. **Meus Jogos** valida e mantém até 500 bilhetes por modalidade no `localStorage` (máximo de 1.500.000 caracteres por conjunto). Filtros são locais; repetir dezenas exige referência informada pela pessoa, não verificada pela CAIXA. Salvar, filtrar e remover não chamam a API; um jogo só é enviado quando a pessoa decide conferi-lo.
- Conferência simples ou histórica em lote por intervalo, com atalho para preencher concursos disponíveis (até 10.000), até 100.000 comparações por solicitação e sem gravação de jogos. Dados enviados pelo cliente são validados estruturalmente, mas a origem oficial não é autenticada. Relatórios CSV são baixados localmente apenas quando solicitados.
- Assistente analítico explicável: o motor determinístico calcula as probabilidades teóricas e a IA pode interpretá-las com estatísticas descritivas. O assistente do backend é local por padrão; chamadas explícitas ao Gemini no servidor exigem habilitação, bearer token distinto da chave do provedor e limites locais. Para oferecer a visitantes, ainda é necessário gateway autenticado e quotas por usuário. Testes sintéticos de conectividade dos provedores não comprovam integração histórica completa nem CORS no navegador.
- Configuração no navegador para OpenAI Responses (incluindo GPT-6 Astra), Gemini, Anthropic e APIs compatíveis com OpenAI Chat Completions.
- Leitura paginada de até 500 concursos por análise da CAIXA, incluindo atraso por dezena, grade 10×10 e coocorrência das casas vizinhas da Lotomania.
- Atualização automática da interface a cada cinco minutos e fallback do navegador para a API pública da CAIXA por um Worker de leitura.

### Origem e atualização dos resultados

A conferência é informativa: confirme concurso, dezenas e premiação diretamente na CAIXA. `simulate` aceita resultado enviado pelo navegador, mas valida sua estrutura sem autenticar a origem; o campo `provenance` distingue dado enviado pelo cliente, cache e consulta do servidor. `statistics/from-draws` e `assistant/from-draws` também identificam dados do cliente como não verificados. Valores de `source` fornecidos pelo cliente são apenas declarações.

Resultados podem vir do Worker, do cache do servidor ou do navegador. Se a atualização falha, os avisos permanecem visíveis enquanto o cache é usado; o histórico pode estar parcial. A chave de navegador `latest:v2` não reutiliza a chave antiga, que poderia ter sido substituída por um concurso histórico. `recently_checked` significa consulta recente ao Worker, não autenticação independente nem garantia de atualização da fonte. Uma página vazia com `before=1` não consulta o concurso mais recente e informa proveniência desconhecida.

Na tela **Resultados**, os controles de página consultam concursos anteriores sob demanda; lacunas são mostradas, nunca preenchidas por estimativas. Exportações incluem até 100 concursos recentes. O assistente só identifica arquivo completo se a consulta recente confirmar essa condição, alcançar o concurso 1 e não houver lacunas ou aviso.

As estatísticas descrevem apenas o histórico recebido e não preveem sorteios. As chances da calculadora derivam de contagens combinatórias exatas; numeradores e denominadores são inteiros e os decimais/“aprox. 1 em N” são apenas exibição. Contagem de combinações não é probabilidade de prêmio. Sem pesos manuais, a geração é aleatória; filtros selecionam o conjunto admissível e pesos alteram a preferência de geração, não a chance matemática de um bilhete específico no sorteio. Não há ponderação histórica automática nem probabilidades calibradas fora da amostra para dezenas individuais. Modelos não preveem resultados. O filtro próprio de saltos conta pares adjacentes de dezenas ordenadas separados por mais de 1; sua equivalência à referência não foi estabelecida.

## Instalação e execução

No diretório raiz do repositório:

```bash
python3 -m pip install -r requirements.txt
uvicorn lotomaster.api:app --host 0.0.0.0 --port 8020
```

Abra `http://localhost:8020`. A documentação OpenAPI fica em `http://localhost:8020/api/docs` e o health check em `http://localhost:8020/api/v1/health`.

O primeiro acesso consulta a API pública da CAIXA. Concursos consultados ficam no arquivo `.lotomaster.sqlite3` na raiz do projeto, ignorado pelo Git. Para alterar o local do banco, defina `LOTOMASTER_DB_PATH`.

O backend e o fallback do navegador consultam a API oficial `https://servicebus2.caixa.gov.br/portaldeloterias/api` por um Cloudflare Worker público, somente de leitura, limitado aos nove endpoints de modalidades suportados e com CORS restrito ao site e ao preview autorizado. O código do Worker está em `cloudflare/workers/lotomaster-caixa-proxy.js`. O endereço usado pelo backend pode ser substituído pela variável `LOTOMASTER_CAIXA_PROXY_URL`. A aplicação não coleta dados por scraping do MazuSoft. Em Vercel, o banco SQLite fica em armazenamento temporário e pode ser reinicializado entre execuções; resultados atuais continuam sendo consultados na CAIXA. A interface confere novos concursos a cada cinco minutos enquanto está aberta.

O assistente do navegador permite que cada pessoa informe a própria chave e modelo. A chave fica em `sessionStorage` por padrão e só é enviada diretamente ao provedor selecionado após uma ação explícita; a opção de persistir neste dispositivo usa `localStorage` e não deve ser ativada em computador compartilhado. Nenhuma chave do proprietário é distribuída. APIs personalizadas precisam permitir chamadas cross-origin (CORS) do navegador e usar o protocolo escolhido. O Gemini no servidor é um caminho distinto: as duas rotas recusam chamadas pagas sem configuração completa e um bearer token válido, que nunca pode ser incluído no HTML, JavaScript, armazenamento do navegador ou aplicativo público.

Ao pedir análise, o navegador pagina os resultados públicos a partir do mais recente até o concurso 1 ou até o limite de 500 concursos por análise; histórico anterior ao limite não é incluído. Cursores, contagens, duplicatas e lacunas são validados. Concursos indisponíveis no recorte são identificados e exigem aceite separado para análise parcial. Resultados, estatísticas e frações combinatórias só são enviados ao provedor escolhido após ação e consentimento explícitos; retirar o consentimento cancela requisições pendentes, mas não desfaz uma requisição já recebida pelo serviço. A origem não é verificada independentemente e o cache pode estar desatualizado. As rotas do Gemini no backend só encaminham quando `use_gemini=true`, `LOTOMASTER_ENABLE_SERVER_GEMINI=true`, `GEMINI_API_KEY`, `LOTOMASTER_SERVER_GEMINI_TOKEN` forte e bearer token válido estão presentes. Uma sugestão opcional da IA é experimental, não substitui o gerador e não tem vantagem probabilística demonstrada. Custos, retenção e uso dos dados dependem do provedor e da chave pessoal.

### Habilitação segura do Gemini no servidor

O caminho de IA do navegador usa a chave informada pela própria pessoa. O Gemini do servidor fica fechado se qualquer pré-requisito faltar. Para habilitá-lo somente para um chamador confiável, configure `LOTOMASTER_ENABLE_SERVER_GEMINI=true`, `GEMINI_API_KEY` e `LOTOMASTER_SERVER_GEMINI_TOKEN` aleatório com pelo menos 32 caracteres. A chave e o token devem ser diferentes e guardados somente no gerenciador de segredos do servidor. As rotas aceitam `Authorization: Bearer <token>`; nunca inclua esse token no navegador, repositório ou logs.

Para um site público, um gateway confiável deve autenticar cada pessoa, aplicar quotas e limites por usuário e só então injetar o token. Há limites adicionais em memória de 10 chamadas por minuto por endereço cliente e 30 por minuto no total; eles não substituem quotas no provedor, limites distribuídos ou proteção da hospedagem. Mantenha o Gemini do servidor desabilitado em hospedagem pública até esses controles externos existirem.

Outras consultas de histórico usam janelas de até 300 concursos por modalidade; no modo de até 500, a interface usa páginas de até 100 e envia o recorte ao endpoint de estatísticas, não ao endpoint do assistente, que tem limite de 300. Para persistir e analisar todo o histórico oficial de forma compartilhada em uma hospedagem serverless, é necessário um armazenamento durável além do SQLite temporário.

## API principal

- `GET /api/v1/lotteries`
- `GET /api/v1/{modalidade}/latest`
- `GET /api/v1/{modalidade}/results?limit=30`
- `GET /api/v1/{modalidade}/history?limit=100&before=...`
- `GET /api/v1/{modalidade}/statistics?limit=50&table=frequency`
- `GET /api/v1/{modalidade}/assistant?limit=50&use_gemini=false` — o resumo permanece local; `use_gemini=true` requer configuração completa (`LOTOMASTER_ENABLE_SERVER_GEMINI`, `GEMINI_API_KEY` e `LOTOMASTER_SERVER_GEMINI_TOKEN`) e `Authorization: Bearer <token>` válido. Não exponha o token ao frontend; um gateway público deve autenticar usuários e limitar quotas antes de injetá-lo.
- `POST /api/v1/{modalidade}/statistics/from-draws`
- `POST /api/v1/{modalidade}/assistant/from-draws` — corpo `{draws: [...], use_gemini: false}`; o encaminhamento ao Gemini exige `use_gemini: true`, a mesma configuração completa e `Authorization: Bearer <token>` válido. O endpoint tem autenticação própria para a chamada Gemini; não equivale a login de usuários nem substitui autenticação/quotas no gateway público.
- `POST /api/v1/{modalidade}/generate`
- `POST /api/v1/{modalidade}/closures/exhaustive` — recebe `pool`, `pick_count`, `fixed` opcional, `filters`, `offset`, `page_size` (1–1.000) e, quando filtros de repetidas são usados, `reference_contest` explícito. Retorna uma página da enumeração lexicográfica, contagem total, próximo offset e todos os motivos locais de filtro por combinação; não materializa páginas anteriores nem grava jogos. Pool máximo de 100 dezenas; modalidades com bônus ou colunas não são suportadas.
- `POST /api/v1/lotofacil/closures/repeated` — recebe `previous_draw` (15 dezenas), `repeated` (6–12 dezenas distintas desse resultado), filtros locais e paginação. Busca um concurso de referência somente se filtros de repetidas forem pedidos e após receber `reference_contest` explícito; de outro modo usa somente os números informados e não persiste jogos.
- `GET /api/v1/lotofacil/combination-count?pick_count=15&fixed_count=10&removed_count=8` — devolve apenas a quantidade de combinações compatíveis e a fórmula; não gera jogos nem calcula a chance de prêmio.
- `POST /api/v1/lotofacil/history-number-search` — recebe `numbers`, até 5.000 `draws` enviados pelo cliente e `match_mode` (`contains_all`, `exact` ou `excludes_all`; padrão legado `contains_all`). Devolve concursos que contêm todas as dezenas, têm o conjunto exatamente igual às 15 dezenas escolhidas, ou não contêm nenhuma das escolhidas, respectivamente. Opera somente sobre a amostra recebida, sem consultar rede nem gravar dados; a origem não é autenticada pelo endpoint.
- `POST /api/v1/{modalidade}/simulate`
- `POST /api/v1/{modalidade}/simulate/history` — recebe `tickets` e `draws`; até 500 jogos, 5.000 concursos e 100.000 comparações por requisição. Os concursos recebidos são validados estruturalmente, mas sua origem oficial não é autenticada pelo endpoint.
- `GET /api/v1/{modalidade}/probability`
- `GET /api/v1/{modalidade}/export.csv?limit=100`
- `GET /api/v1/{modalidade}/export.txt?limit=100`
- `GET /api/v1/{modalidade}/export.xlsx?limit=100`

### Segurança e compatibilidade das análises

- `assistant` e `assistant/from-draws` permanecem locais por padrão. Gemini no servidor exige solicitação explícita, habilitação, chave do provedor e bearer token forte separado; endpoints públicos não devem encaminhar chamadas pagas sem autenticação, gateway e quotas.
- `statistics/from-draws` aceita de 1 a 500 concursos; `assistant/from-draws`, de 1 a 300. Cada corpo é limitado a 1.000.000 bytes antes do parsing, inclusive em requisições por partes (413 acima do limite); entradas inválidas retornam 422. Configure também limites de tamanho, tempo, concorrência e taxa no proxy.
- Cada concurso exige modalidade correta, número inteiro positivo único e dezenas inteiras na quantidade/faixa da modalidade, sem repetição (exceto dígitos em colunas distintas do Super Sete). Campos especiais e ordem, quando enviados, devem ser coerentes. Dados suplementares ausentes não entram em suas estatísticas. A validação estrutural não autentica a origem dos dados.
- `/simulate` valida resultado de todas as origens, inclusive cache antigo, e exige dados especiais aplicáveis para Dupla Sena, +Milionária, Dia de Sorte e Timemania. Exige também bônus compatíveis nos jogos e Time do Coração para gerar Timemania. Confirme prêmios na CAIXA.
- A +Milionária aceita apostas múltiplas de 6–12 dezenas e 2–6 trevos no gerador, conferidor e calculadora; cada bilhete equivale a `C(n,6) × C(t,2)` subapostas simples. Trevos individuais são preservados por padrão; substituir em lote exige ação explícita. O indicador de concursos especiais em analytics chama-se `marked_special_draws`.
- Alterações no formato CAIXA podem causar rejeição. Dados inválidos já armazenados podem causar erro na análise e devem ser verificados separadamente. Limite de corpo não restringe tamanho da resposta CAIXA nem protege outras rotas.

Execute os testes offline a partir da raiz do repositório, usando banco temporário para preservar o banco local:

```bash
test_db=$(mktemp /tmp/lotomaster-tests-XXXXXX.sqlite3)
trap 'rm -f "$test_db"' EXIT
LOTOMASTER_DB_PATH="$test_db" python3 lotomaster/tests/offline_pytest.py
node --test lotomaster/tests/*.js lotomaster/tests/*.cjs
```

Veja [as fontes](REFERENCE.md), [o mapeamento e os limites da inspeção REA](MAPEAMENTO_MAZUSOFT_REA.md) e [a avaliação da Lotomaster](AVALIACAO_LOTOMASTER.md).

## Limites desta versão

O REA é uma ferramenta de engenharia reversa, não uma aplicação de loteria a ser copiada integralmente. Nesta inspeção, o REA só alcançou um navegador temporário em página de bloqueio; não acessou a sessão autenticada nem o backend privado. A observação manual de um fechamento completo da Lotofácil coincidiu em um cenário de 210 jogos, mas não prova equivalência geral. Fechamentos e garantias proprietárias, tabelas Premium, fórmulas não documentadas e autenticação de resultados enviados pelo cliente não são reproduzidos. Filtros de quadrantes e demais regras locais não reivindicam equivalência aos algoritmos privados da MazuSoft. A Lotofácil aceita 15–23 dezenas na conferência, enquanto a geração permanece limitada a 15–20. A conferência é informativa; confirme prêmios na CAIXA. Nenhum serviço atual do SIAOL foi substituído; esta camada web possui pacote, rotas e persistência separados.

## Servidor MCP para agentes (Cue e Grok Bot)

A integração MCP fica separada da aplicação web, em `lotomaster/mcp_server.py`. Ela oferece dois transportes: `stdio` local para um agente que inicia o processo e Streamable HTTP no caminho `/mcp`. O stdio troca mensagens MCP JSON-RPC em linhas por stdin/stdout, não exige Bearer e não publica uma porta de rede. O stdout é reservado ao protocolo; não adicione mensagens de log nesse canal.

### Cue: processo local por stdio

Configuração a aplicar no computador que executará o subprocesso do Cue:

```text
Programa: python3
Argumentos: -m lotomaster.mcp_server --transport stdio
Diretório de trabalho: <raiz-do-checkout, diretório que contém lotomaster/>
```

O computador precisa ter Python 3 e as dependências do projeto instaladas. O comando pode ser testado manualmente na raiz do checkout. Este checkout está no ambiente sandbox desta tarefa; não se deve presumir que seu caminho exista ou seja compartilhado com o computador onde o Cue iniciará o processo. Não foi configurado conector do Cue.

### Grok Bot: endpoint público HTTPS

O Grok Bot precisa alcançar um servidor MCP pela internet; `localhost`, `127.0.0.1` e o transporte stdio local não servem. Para conectá-lo será necessário um domínio público com DNS, TLS/HTTPS válido, hospedagem do processo HTTP, proxy reverso seguro que encaminhe `/mcp`, hostname permitido e `LOTOMASTER_MCP_BEARER_TOKEN` forte guardado no ambiente do servidor. Um túnel público seria outra opção, mas nenhum domínio, hospedagem, proxy ou túnel foi criado/configurado nesta tarefa. A URL e o Bearer devem ser adicionados ao conector MCP customizado do Grok Bot somente depois de o endpoint existir. O conector é separado da API de modelos Grok/xAI. Nenhum conector Grok foi configurado.

### Transporte HTTP (quando houver host confiável)

O modo HTTP mantém Bearer obrigatório e falha fechado se faltar `LOTOMASTER_MCP_BEARER_TOKEN` com pelo menos 32 caracteres aleatórios. Por padrão, escuta apenas em `127.0.0.1:8765`; não publique a porta diretamente nem exponha o token em código, HTML, URL, prompts ou logs. Para um teste local, execute na raiz do repositório:

```bash
export LOTOMASTER_MCP_BEARER_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
python3 -m lotomaster.mcp_server --transport http
```

A configuração HTTP continua rejeitando hostnames não permitidos e qualquer `Origin` não autorizado. Para implantação atrás de proxy, defina `LOTOMASTER_MCP_ALLOWED_HOSTS` com o hostname exato; se o cliente enviar `Origin`, configure somente origens exatas em `LOTOMASTER_MCP_ALLOWED_ORIGINS`, sem curinga. Nenhum processo MCP foi deixado rodando por esta tarefa.

### Acesso e limites

Ferramentas do modo padrão: catálogo e regras; leitura paginada do histórico existente no SQLite (somente leitura); listagem e leitura de arquivos textuais/código permitidos no checkout; análise de concursos fornecidos; conferência de até 100 jogos contra até 50 concursos completos (limite total de 5.000 comparações); cálculo combinatório; geração de até 20 prévias em memória. A leitura de arquivos é limitada a extensões textuais/código, 1 MiB e janelas de até 400 linhas. Caminhos fora do checkout, links simbólicos, arquivos ocultos, credenciais, bancos, binários, ambientes, dependências e diretórios de build são excluídos; padrões de chaves/tokens são mascarados. O texto retornado é dado não confiável e não deve ser executado como instrução.

Por padrão, o MCP não escreve arquivos, jogos, estudos ou bancos; não atualiza dados, acessa serviços externos ou credenciais, opera contas, aposta, publica nem envia dados a terceiros. Jogos salvos no `localStorage` de outro navegador não ficam automaticamente visíveis ao processo MCP; jogos precisam ser fornecidos para análise. Históricos podem estar incompletos e sua origem não é autenticada. Estatísticas e conferências retrospectivas não são previsões.

O transporte HTTP limita a oito requisições simultâneas e responde 503 quando os slots estão ocupados. Esse limite local reduz pressão de recursos, mas não substitui limites de taxa, quotas ou proteção contra abuso no proxy reverso.

#### Editor local opcional, somente na branch autorizada

O editor vem **desativado**. Para disponibilizá-lo a um subprocesso local, defina explicitamente a variável abaixo antes de iniciar o MCP por `stdio`:

```bash
export LOTOMASTER_MCP_ENABLE_BRANCH_EDIT=1
python3 -m lotomaster.mcp_server --transport stdio
```

Com a opção ligada, `edit_branch_file` só substitui arquivos de código permitidos sob `lotomaster/` ou o README funcional, apenas na branch `feature/lotomaster-public-parity`, e exige o SHA-256 atual. Avaliações, mapeamentos e estudos congelados — inclusive caminhos identificados como estudos ou experimentos — ficam fora do escopo. Caminhos absolutos, traversal, symlinks, hard links, arquivos ocultos, credenciais e binários são bloqueados. Não se criam novos arquivos de projeto nem se apagam arquivos; a substituição atômica usa um arquivo temporário transitório no mesmo diretório.

`review_branch_diff` mostra alterações locais staged/unstaged do escopo, com padrões conhecidos de segredo redigidos; para arquivos não rastreados, mostra somente os nomes, não o conteúdo. `run_branch_checks` executa os testes `unittest` do Lotomaster, análise de sintaxe Python sem bytecode, `node --check` nos dois arquivos JavaScript fixos e `git diff --check`. Os testes usam SQLite temporário removido ao final e um ambiente sem as chaves do processo; executar testes ainda executa código do checkout com as permissões locais do processo.

As gravações do editor são best-effort sob concorrência: mantenha o checkout exclusivo durante a edição. A branch é capturada no início da chamada e pode não corresponder à branch no instante da gravação.

O editor não oferece comandos de commit, push, merge ou deploy, e não escreve no banco de histórico, jogos ou estudos. O transporte HTTP continua somente leitura, mesmo se a variável de opt-in estiver definida. Revise o diff antes de qualquer outra etapa manual. Nesta revisão, o código do modo opcional está preparado, mas nenhum conector do Cue foi ativado; o subprocesso precisa ser configurado no computador que tem o checkout. A interface da aplicação continua apenas informando que a conexão está pendente e não consulta o MCP, não exibe tokens nem ativa conectores. Grok continua dependente de endpoint público HTTPS e configuração do servidor.
