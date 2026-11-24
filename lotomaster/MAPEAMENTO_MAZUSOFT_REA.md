# Mapeamento MazuSoft e evidências REA

## Escopo observado

As páginas públicas das nove modalidades seguem `https://www.mazusoft.com.br/{modalidade}/`, com gerador, conferência, resultados e tabelas. O padrão de caminhos é `gerador.php`, `confere.php`, `resultados.php` e `tabelas.php`; para +Milionária, a página de conferência usa `simulador.php`. As modalidades são Mega-Sena, Lotofácil, Lotomania, Quina, Dia de Sorte, Dupla Sena, Timemania, Super Sete e +Milionária.

As páginas observadas oferecem geração, conferência, resultados e tabelas. Foram observados também recursos de fixar/remover números. Particularidades visíveis: Lotomania usa dezenas de 00 a 99 e contempla prêmio zero; Dupla Sena tem dois sorteios; Dia de Sorte inclui mês; Timemania, time; Super Sete, sete colunas; e +Milionária, trevos.

Na página autenticada do gerador da Lotofácil foram vistos filtros de pares/ímpares, soma, distribuição por linha/coluna, repetidas do concurso anterior, sequência, saltos, Fibonacci, primos, Pareto e pesos. As opções visíveis incluem jogos de 15 a 20 dezenas e quantidades de 1 a 100. A lógica exata e as fórmulas desses filtros não foram verificadas.

Na conferência da Lotofácil foram observados concurso “Todos”, comando “CONFERIR”, ordenação por sorteio/acertos, faixas de 11 a 15 acertos e opção de salvar. Não foram salvos nem manipulados jogos ou estudos. A página de ferramentas lista teste de múltiplos jogos, importação, calculadora e fechamentos. A inspeção autenticada posterior foi parcial, como descrito adiante.

## Execução e limites do REA

O REA 6.10.1 ([repositório](https://github.com/morluto/rea)) foi efetivamente executado com `list-browser-targets` e `inspect-web-page` sobre navegador temporário sem login, na URL do gerador da Lotofácil. A página retornada era “Just a moment...” (proteção Cloudflare); portanto, a captura não demonstra o conteúdo nem o comportamento da aplicação.

Separadamente, uma consulta a [`confer.min.js`](https://www.mazusoft.com.br/lotofacil/js/confer.min.js) obteve texto de script público, transcrito/reconstituído em `/workspace/rea-mazusoft-public/confer.min.js`. Esse texto não prova os bytes originais e seu código não foi incorporado ao repositório. A análise estática REA `analyze-javascript-application` está documentada integralmente em `/tmp/rea-mazusoft-js-analysis.json`.

O código cliente analisado indica uma chamada `fetch` a `AppConfig.baseUrl`, com argumentos `meujogo`, `concurso`, `order` e `cmd=load`, e renderização de respostas por concurso e faixas de acerto. O endpoint efetivo é dinâmico e não foi resolvido. Isso não revela o PHP nem o backend, não confirma fórmulas e não prova que o fluxo foi executado.

## Fontes e cautelas

- [MazuSoft — Mega-Sena](https://www.mazusoft.com.br/mega/)
- [MazuSoft — Lotofácil](https://www.mazusoft.com.br/lotofacil/)
- [MazuSoft — Lotomania](https://www.mazusoft.com.br/lotomania/)
- [MazuSoft — Quina](https://www.mazusoft.com.br/quina/)
- [MazuSoft — Dia de Sorte](https://www.mazusoft.com.br/dia-de-sorte/)
- [MazuSoft — Dupla Sena](https://www.mazusoft.com.br/dupla-sena/)
- [MazuSoft — Timemania](https://www.mazusoft.com.br/timemania/)
- [MazuSoft — Super Sete](https://www.mazusoft.com.br/super-sete/)
- [MazuSoft — +Milionária](https://www.mazusoft.com.br/mais-milionaria/)
- [Script público de conferência](https://www.mazusoft.com.br/lotofacil/js/confer.min.js)
- [REA no GitHub](https://github.com/morluto/rea)

O mapeamento é uma observação textual, não uma validação completa das páginas ou de suas regras. Pesquisa textual e código cliente não bastam para provar comportamento, fórmulas, resultados oficiais ou equivalência entre sistemas.

## Ampliação do levantamento — nove modalidades

Foram consultados os índices públicos, geradores, páginas de conferência, resultados e tabelas das nove modalidades, por modalidade. Há evidência textual de navegação comum por resultados, gerador, conferência e tabelas; os catálogos citam ainda estatísticas de frequência, atraso, paridade, soma, Fibonacci, primos e outras. Em várias páginas de resultados aparecem exportação TXT e Excel, mas os arquivos não foram baixados nem os fluxos testados. Fontes: [Mega-Sena](https://www.mazusoft.com.br/mega/), [Lotofácil](https://www.mazusoft.com.br/lotofacil/), [Lotomania](https://www.mazusoft.com.br/lotomania/), [Quina](https://www.mazusoft.com.br/quina/), [Dia de Sorte](https://www.mazusoft.com.br/dia-de-sorte/), [Dupla Sena](https://www.mazusoft.com.br/dupla-sena/), [Timemania](https://www.mazusoft.com.br/timemania/), [Super Sete](https://www.mazusoft.com.br/super-sete/) e [+Milionária](https://www.mazusoft.com.br/mais-milionaria/).

Na sessão autenticada da Lotofácil, a verificação de segurança foi concluída automaticamente. A observação direta do [gerador](https://www.mazusoft.com.br/lotofacil/gerador.php) confirmou controles para paridade, soma, linhas, colunas, repetidas, sequência de números, saltos, Fibonacci, primos, Pareto e pesos; não revelou as fórmulas ou os parâmetros exatos usados. O seletor de dezenas exibia 15–20; o de quantidade de jogos exibia 1–30 e depois 40, 50, 60, 70, 80, 90 e 100. A [lista de ferramentas](https://www.mazusoft.com.br/lotofacil/ferramentas.php) inclui combinações, conferir até 23 dezenas, gerador aleatório, múltiplos jogos, importação, calculadora, desdobramentos e dois geradores de fechamentos. Essas descrições identificam rótulos, não comprovam regras internas, conteúdos Premium nem equivalência de comportamento. Não foram salvos ou alterados jogos.

O runtime Node 24.22.2 já existente permitiu executar o REA 6.10.1 novamente. A descoberta passiva em `127.0.0.1:19222`, limitada à origem MazuSoft, identificou apenas a página `Just a moment...` de um navegador temporário, e não a aba autenticada observada no navegador conectado. O REA, portanto, não inspecionou a sessão autenticada. Os controles acima foram observados pelo navegador conectado, não por captura REA; análise estática anterior REA continua limitada ao script público descrito acima. Nenhum cookie, token ou credencial foi copiado.

A tela autenticada de [gerador de fechamentos da Lotofácil](https://www.mazusoft.com.br/lotofacil/gerador-fechamento.php) apresentou uma grade de 25 dezenas, o último concurso, opções para fixar/remover dezenas que se repetem, quantidade de repetidas de 6 a 12, simulador e equilíbrio das combinações, além do botão para gerar combinações de repetidas. O fechamento completo e suas eventuais garantias ou fórmulas não foram executados nem verificados; a existência dos controles não demonstra como o algoritmo funciona.

## Continuação da inspeção autenticada — 23/11/2026

No navegador conectado, [o gerador autenticado da Lotofácil](https://www.mazusoft.com.br/lotofacil/gerador.php) exibiu novamente controles booleanos para paridade, soma, linhas, colunas, repetidas, sequência grande de números, sequência grande de saltos, Fibonacci, primos, princípio de Pareto e pesos. Os dez primeiros estavam marcados e pesos desmarcado no estado observado. Marcar apenas pesos não revelou novos parâmetros visíveis; foi restaurado ao estado inicial, sem enviar formulário nem salvar jogos. Essa observação não estabelece os algoritmos ou seus parâmetros. A página já exibia um jogo ao ser carregada; nenhuma ação de salvar foi realizada.

O [gerador de fechamento](https://www.mazusoft.com.br/lotofacil/gerador-fechamento.php) mostrou seleção de repetidas do concurso anterior, opção de 6 a 12 repetidas, fixação/remoção, equilíbrio e simulador. Isso é uma interface diferente da enumeração exaustiva simples implementada localmente; não foi obtida uma garantia, especificação ou equivalência de resultados.

O REA 6.10.1 foi novamente executado (`list-browser-targets` e `inspect-web-page`, apenas a origem MazuSoft, sem cookies ou dados de armazenamento). Na porta CDP disponível para o REA identificou-se apenas um Chrome Headless separado, na página de bloqueio “Just a moment...”. O navegador autenticado usa canal de depuração do tipo pipe, e não foi constatado um endpoint CDP de rede conectável pelo REA. Não foram copiados cookies nem se tentaram contornar a verificação. Assim, os controles autenticados acima foram observados no navegador conectado, não com o REA. Saída REA local da inspeção: `/tmp/lotomaster-rea-20261123-inspect.json`. A paridade integral e as fórmulas do backend continuam não demonstradas.

Em um teste isolado no navegador conectado, sem salvar ou apostar jogos, foi selecionado o concurso-base 3835 e nove repetidas: 03, 04, 05, 09, 15, 16, 19, 21, 22. A opção “Desdobramento Completo de 10 Dezena(s) = 210 Jogos” apresentou 210 linhas. A comparação de todas as linhas confirmou o conjunto exato de combinações composto pelas nove repetidas e todas as escolhas de seis dentre as dez dezenas ausentes do concurso-base (01, 06, 07, 08, 11, 14, 20, 23, 24, 25); a primeira linha também conferiu. É um caso observado, não prova de regra geral, garantia ou paridade completa. A opção de grupos de 2 dezenas com 10 jogos não foi validada. O teste foi no navegador conectado, não via REA; o REA continuou limitado ao navegador temporário na página “Just a moment...”, sem cópia de cookies ou outros dados de sessão.

## Novas evidências públicas — 23/11/2026

A página pública de [Ferramentas da Lotomania](https://www.mazusoft.com.br/lotomania/ferramentas.php) lista “Gerador Lotomania - Versão Quadrantes”. O [gerador público](https://www.mazusoft.com.br/lotomania/gerador.php) mostra a grade de 00 a 99 em dez colunas, mas o conteúdo extraído não descreve controles, fórmula ou algoritmo do modo Quadrantes. A implementação local, portanto, expõe seus próprios limites por quatro blocos 5×5 e não afirma copiar a regra privada da MazuSoft.

A página pública de [Ferramentas da Lotofácil](https://www.mazusoft.com.br/lotofacil/ferramentas.php) descreve “Montar Jogo e Testar com até 23 dezenas”. Isso evidencia o limite anunciado para a ferramenta de conferência, não altera a regra de apostas: o gerador local permanece limitado ao máximo de 20 dezenas configurado para apostas oficiais. O comportamento de telas premium ou fórmulas internas não foi inferido a partir desses rótulos.

## Inspeção autenticada adicional — 23/11/2026

A [calculadora da Lotofácil](https://www.mazusoft.com.br/lotofacil/calculadora.php) mostrou seletores de 15–20 dezenas, quantidades de fixas e removidas. Dois cálculos foram executados sem salvar ou apostar: para 15 dezenas, 10 fixas e 8 removidas, mostrou **21 combinações**; para 15 dezenas, 8 fixas e 7 removidas, mostrou **120 combinações**. A própria página descreve ainda 816 combinações para 15 dezenas com 7 removidas e nenhuma fixa, e 210 para 15 dezenas com 9 fixas e 6 removidas. As contagens desses quatro exemplos coincidem com `C(25-f-r, p-f)`, mas não provam a equivalência de todas as opções ou a fórmula interna.

No segundo teste a página também mostrou “14 Pontos - 1 em 0,80”. Esse texto, se interpretado como probabilidade `1/0,80`, excederia 100%; o significado exato e a fórmula não foram estabelecidos. Por isso a Lotomaster não copia esse valor nem o usa como chance de prêmio. Valores monetários exibidos na referência são variáveis e não foram incorporados.

A ferramenta autenticada [Combinações dos Números](https://www.mazusoft.com.br/lotofacil/combinacoes.php) apresenta modos “Contém os Números”, “Combinação Exata” e “Não contém os Números”, com seleção de 1 a 15 dezenas. Na consulta 01 e 02 pelo primeiro modo, a tela indicou 1.352 concursos em 3.835 e mostrou resultados incluindo os concursos 3829 e 3827 com ambas as dezenas. Depois, ao solicitar “Combinação Exata” para as mesmas duas dezenas, a tela retornou erro, mantendo a contagem anterior; não se pode concluir a semântica do modo ou tratar os dados remanescentes como nova resposta. Não foram salvos jogos nem alterados estudos.

A [CAIXA](https://caixanoticias.caixa.gov.br/Paginas/Not%C3%ADcias/2023/07-Julho/milionaria-passa-a-ter-dois-sorteios-toda-semana.aspx) informa que a +Milionária aceita apostas múltiplas com 6 a 12 números e 2 a 6 trevos. Nesta versão do Lotomaster, esses limites estão implementados na geração, validação, conferência simples e histórica e probabilidades exatas; isso é uma afirmação sobre o código e os testes locais, não uma confirmação de paridade com a MazuSoft.

A [página oficial da +Milionária](https://loterias.caixa.gov.br/Paginas/Mais-Milionaria.aspx) descreve as dez faixas por acertos de dezenas e trevos. Um bilhete de `n` dezenas e `t` trevos é calculado como `C(n,6) × C(t,2)` subapostas simples. Cada probabilidade de faixa mede a presença de pelo menos uma subaposta premiada; faixas podem se sobrepor no mesmo bilhete, enquanto a chance de “qualquer prêmio” é a união exata dos resultados sorteados, sem dupla contagem. A nova cobertura inclui uma referência combinatória independente nos extremos 6/12 dezenas e 2/6 trevos. Ela verifica a fórmula e não representa uma comparação exaustiva com a MazuSoft ou com o sistema de conferência oficial da CAIXA.

## Critérios locais de pesquisa histórica da Lotofácil

A Lotomaster oferece `contains_all` (resultado contém todas as dezenas escolhidas), `exact` (o conjunto é igual às 15 dezenas escolhidas) e `excludes_all` (o resultado não contém nenhuma delas). “Combinação exata” exige 15 dezenas e a igualdade ignora a ordem. Essa semântica é uma definição local para a amostra histórica carregada; não valida o comportamento interno da MazuSoft, cuja tentativa de combinação exata observada retornou erro.
