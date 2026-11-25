# Referências funcionais da Lotomaster

Este documento preserva as fontes externas usadas para orientar a nova interface e API. A implementação deste repositório é uma reimplementação própria baseada no comportamento público observado; não contém código-fonte interno do MazuSoft.

## MazuSoft — páginas públicas consultadas

Página inicial: <https://www.mazusoft.com.br/>. O índice público organiza as modalidades em geradores, simuladores e tabelas/estatísticas. Para as modalidades, foram consultados índices e, quando disponíveis, caminhos públicos de gerador, conferência/simulação, resultados, tabelas e ferramentas.

| Modalidade | Índice público | Gerador | Simulador/conferência | Resultados | Tabelas |
|---|---|---|---|---|---|
| Mega-Sena | <https://www.mazusoft.com.br/mega/> | <https://www.mazusoft.com.br/mega/gerador.php> | <https://www.mazusoft.com.br/mega/confere.php> | <https://www.mazusoft.com.br/mega/resultados.php> | <https://www.mazusoft.com.br/mega/tabelas.php> |
| Lotofácil | <https://www.mazusoft.com.br/lotofacil/> | <https://www.mazusoft.com.br/lotofacil/gerador.php> | <https://www.mazusoft.com.br/lotofacil/confere.php> | <https://www.mazusoft.com.br/lotofacil/resultados.php> | <https://www.mazusoft.com.br/lotofacil/tabelas.php> |
| Lotomania | <https://www.mazusoft.com.br/lotomania/> | <https://www.mazusoft.com.br/lotomania/gerador.php> | <https://www.mazusoft.com.br/lotomania/confere.php> | <https://www.mazusoft.com.br/lotomania/resultados.php> | <https://www.mazusoft.com.br/lotomania/tabelas.php> |
| Quina | <https://www.mazusoft.com.br/quina/> | <https://www.mazusoft.com.br/quina/gerador.php> | <https://www.mazusoft.com.br/quina/confere.php> | <https://www.mazusoft.com.br/mega/loterias.php> (índice geral) | <https://www.mazusoft.com.br/quina/tabelas.php> |
| Dia de Sorte | <https://www.mazusoft.com.br/dia-de-sorte/> | <https://www.mazusoft.com.br/dia-de-sorte/gerador.php> | <https://www.mazusoft.com.br/dia-de-sorte/confere.php> | <https://www.mazusoft.com.br/dia-de-sorte/resultados.php> | <https://www.mazusoft.com.br/dia-de-sorte/tabelas.php> |
| Dupla Sena | <https://www.mazusoft.com.br/dupla-sena/> | <https://www.mazusoft.com.br/dupla-sena/gerador.php> | <https://www.mazusoft.com.br/dupla-sena/confere.php> | <https://www.mazusoft.com.br/dupla-sena/resultados.php> | <https://www.mazusoft.com.br/dupla-sena/tabelas.php> |
| Timemania | <https://www.mazusoft.com.br/timemania/> | <https://www.mazusoft.com.br/timemania/gerador.php> | <https://www.mazusoft.com.br/timemania/confere.php> | <https://www.mazusoft.com.br/timemania/resultados.php> | <https://www.mazusoft.com.br/timemania/tabelas.php> |
| Super Sete | <https://www.mazusoft.com.br/super-sete/> | <https://www.mazusoft.com.br/super-sete/gerador.php> | <https://www.mazusoft.com.br/super-sete/confere.php> | <https://www.mazusoft.com.br/super-sete/resultados.php> | <https://www.mazusoft.com.br/super-sete/tabelas.php> |
| +Milionária | <https://www.mazusoft.com.br/mais-milionaria/> | <https://www.mazusoft.com.br/mais-milionaria/gerador.php> | <https://www.mazusoft.com.br/mais-milionaria/simulador.php> | <https://www.mazusoft.com.br/mais-milionaria/resultados.php> | <https://www.mazusoft.com.br/mais-milionaria/tabelas.php> |

Também foi observado o índice de ferramentas da Lotofácil em <https://www.mazusoft.com.br/lotofacil/ferramentas.php> e o gerador aleatório da Quina em <https://www.mazusoft.com.br/quina/gerador-aleatorio.php>.

### Elementos públicos observados

- As nove modalidades compartilham as áreas de resultado, gerador, conferência/simulação e tabelas estatísticas.
- Os geradores exibem controles de fixar/remover dezenas, jogo de exemplo, paridade, soma, repetidas e ação de testar; as combinações concretas de controles variam por modalidade.
- As páginas de resultados mostram exportação TXT/Excel e concursos recentes. As páginas de índice apresentam dados do concurso, premiação, acumulação e/ou próximo sorteio.
- A Lotofácil lista ferramentas como testar múltiplos jogos, importação, calculadora de probabilidades e desdobramentos/fechamentos, além de muitas tabelas estatísticas.
- Há seleções especiais: Mês da Sorte (Dia de Sorte), dois sorteios (Dupla Sena), Time do Coração (Timemania), sete colunas com dígitos (Super Sete) e Trevos da Sorte (+Milionária).
- As listas de tabelas incluem, conforme a modalidade, frequência, atraso, pares/ímpares, repetidas, primos, Fibonacci, múltiplos de três, soma, duplas/trincas, padrões, quadrantes, linhas/colunas, moldura/centro, binário e filtros.

### Observações adicionais em sessão autenticada da Lotofácil

- Na calculadora (<https://www.mazusoft.com.br/lotofacil/calculadora.php>), para jogo de 15 dezenas com 10 fixas e 8 removidas, foi retornada a contagem 21; com 8 fixas e 7 removidas, foi retornada 120. Esses valores são compatíveis com a contagem de combinações `C(25-f-r,p-f)` nas entradas observadas. A linha “14 Pontos - 1 em 0,80” também apareceu no segundo caso, mas sua semântica não foi determinada; não deve ser copiada nem interpretada como probabilidade.
- Na ferramenta de combinações (<https://www.mazusoft.com.br/lotofacil/combinacoes.php>), foram observadas as opções “contém”, “combinação exata” e “não contém”. A busca “contém 01 e 02” retornou 1.352 de 3.835. A seleção “combinação exata 01 e 02” produziu erro; não há evidência para concluir qual comportamento interno seria esperado. A Lotomaster oferece esses critérios com definições matemáticas próprias, sem alegar reprodução do sistema de referência.
- Essas observações são exemplos pontuais, não validação de equivalência geral. Não foram gerados ou salvos jogos.

## Fonte oficial de resultados

A interface consulta a API pública do Portal de Loterias da CAIXA e mantém um cache local SQLite. Os endpoints usados são:

- <https://servicebus2.caixa.gov.br/portaldeloterias/api/megasena>
- <https://servicebus2.caixa.gov.br/portaldeloterias/api/lotofacil>
- <https://servicebus2.caixa.gov.br/portaldeloterias/api/lotomania>
- <https://servicebus2.caixa.gov.br/portaldeloterias/api/quina>
- <https://servicebus2.caixa.gov.br/portaldeloterias/api/diadesorte>
- <https://servicebus2.caixa.gov.br/portaldeloterias/api/duplasena>
- <https://servicebus2.caixa.gov.br/portaldeloterias/api/timemania>
- <https://servicebus2.caixa.gov.br/portaldeloterias/api/supersete>
- <https://servicebus2.caixa.gov.br/portaldeloterias/api/maismilionaria>

A consulta pode acrescentar o número do concurso ao caminho do endpoint para recuperar um concurso específico. A implementação persiste os dados normalizados recebidos e continua servindo o cache se a fonte oficial ficar indisponível.

### Indicador de concurso especial observado na API

Nos registros oficiais consultados, `indicadorConcursoEspecial=1` identifica um concurso regular e `=2` identifica um concurso especial: a [Mega-Sena 2811, de 04/01/2025](https://servicebus2.caixa.gov.br/portaldeloterias/api/megasena/2811) retorna `1`, enquanto a [Mega da Virada 2810, de 31/12/2024](https://servicebus2.caixa.gov.br/portaldeloterias/api/megasena/2810) retorna `2`. A [página oficial da Mega-Sena](https://loterias.caixa.gov.br/Paginas/mega-sena.aspx) descreve as regras da Mega da Virada como concurso especial. O `tipoJogo` permanece `MEGA_SENA` nos dois registros e não deve ser usado para inferir esse indicador. O normalizador do backend e o fallback do navegador tratam agora `1` como regular e `2` como especial.

## Regras oficiais usadas nos cálculos de probabilidade

- [CAIXA — regras dos sorteios](https://loterias.caixa.gov.br/Paginas/regras-sorteios.aspx): universos e tamanhos dos sorteios; dois sorteios da Dupla Sena; reposição antes do sorteio do Time do Coração da Timemania no universo de 01 a 80; sete colunas independentes do Super Sete; sorteio separado dos dois trevos entre seis na +Milionária.
- [CAIXA — Timemania](https://loterias.caixa.gov.br/paginas/timemania.aspx): escolha de dez números entre oitenta e de um Time do Coração; premiação para o time sorteado ou para três a sete acertos.
- [CAIXA — +Milionária](https://loterias.caixa.gov.br/Paginas/Mais-Milionaria.aspx): a página oficial lista dez faixas de premiação e define a Faixa 10 como 2 prognósticos certos + 1 trevo; as Faixas 2, 4 e 6 agrupam 6, 5 e 4 acertos, respectivamente, com 1 ou nenhum trevo.
- [CAIXA — +Milionária, notícias](https://caixanoticias.caixa.gov.br/Paginas/Not%C3%ADcias/2023/07-Julho/milionaria-passa-a-ter-dois-sorteios-toda-semana.aspx): informa a possibilidade de apostas múltiplas com 6–12 dezenas e 2–6 trevos. Esse intervalo está implementado na geração, validação, conferência simples/histórica e cálculo de probabilidades nesta versão.

A calculadora usa contagem hipergeométrica para dezenas sem reposição e contagem exata por coluna para o Super Sete. Na +Milionária, uma aposta de `n` dezenas e `t` trevos corresponde a `C(n,6) × C(t,2)` subapostas simples. Se `h` dezenas sorteadas estão entre as `n` escolhidas e `k` dos dois trevos sorteados estão entre os `t` escolhidos, a quantidade de subapostas com `x` acertos principais e `y` acertos de trevos é `C(h,x) × C(n-h,6-x) × C(k,y) × C(t-k,2-y)` (combinações fora do domínio valem zero). As probabilidades por faixa são de presença — pelo menos uma subaposta na faixa — sobre o espaço equiprovável `C(50,6) × C(6,2)`; linhas de faixas distintas podem se sobrepor no mesmo bilhete. “Qualquer prêmio” conta a união dos estados sorteados `h,k` uma única vez, sem somar faixas sobrepostas. A conferência também agrega, por faixa, a quantidade de subapostas premiadas sem serializar uma lista completa para bilhetes maiores. Categorias de bônus podem se sobrepor às faixas principais em outras modalidades; a saída identifica essa sobreposição e calcula “qualquer prêmio” como união dos eventos. Para Dupla Sena, a chance de um evento de faixa em pelo menos um dos sorteios considera a independência documentada das duas extrações. A contagem de combinações com fixas/removidas na Lotofácil é `C(25-f-r,p-f)`, uma quantidade de combinações admissíveis, não uma previsão nem probabilidade de prêmio. Nada disso replica fórmulas internas desconhecidas da MazuSoft nem prevê resultados.

## Registros oficiais usados na auditoria

O teste `tests/test_official_draw_probability_audit.py` usa respostas oficiais por número de concurso, para reproduzir a checagem sem depender de o endpoint genérico refletir o resultado mais recente. Foram conferidos resultados e campos adicionais aplicáveis:

- Mega-Sena 3088 (19/11/2026): <https://servicebus2.caixa.gov.br/portaldeloterias/api/megasena/3088>
- Lotofácil 3827 (11/11/2026): <https://servicebus2.caixa.gov.br/portaldeloterias/api/lotofacil/3827>
- Lotomania 3000 (16/11/2026): <https://servicebus2.caixa.gov.br/portaldeloterias/api/lotomania/3000>
- Quina 7161 (06/11/2026): <https://servicebus2.caixa.gov.br/portaldeloterias/api/quina/7161>
- Dia de Sorte 1334 (28/10/2026): <https://servicebus2.caixa.gov.br/portaldeloterias/api/diadesorte/1334> — Mês da Sorte.
- Dupla Sena 3034 (18/11/2026): <https://servicebus2.caixa.gov.br/portaldeloterias/api/duplasena/3034> — primeiro e segundo sorteios.
- Timemania 2455 (15/10/2026): <https://servicebus2.caixa.gov.br/portaldeloterias/api/timemania/2455> — Time do Coração.
- Super Sete 909 (09/10/2026): <https://servicebus2.caixa.gov.br/portaldeloterias/api/supersete/909> — dígitos posicionais nas sete colunas.
- +Milionária 405 (06/11/2026): <https://servicebus2.caixa.gov.br/portaldeloterias/api/maismilionaria/405> — dois trevos.

Os cálculos foram comparados com contagens combinatórias exatas e, para o bilhete múltiplo de +Milionária, enumeração explícita independente de subapostas. A comparação é teórica e não usa frequências históricas para alterar probabilidades. A avaliação registra que não apareceu divergência matemática nessas amostras; a única divergência demonstrada foi a interpretação de `indicadorConcursoEspecial` documentada acima. As datas são de concursos fixos e não afirmam atualidade do histórico geral da CAIXA.

## Limites da inspeção

Além da pesquisa pública sem login, em etapa posterior foi observada uma sessão já autenticada da Lotofácil, incluindo os casos pontuais documentados acima; essa inspeção e a análise REA estão descritas em [MAPEAMENTO_MAZUSOFT_REA.md](MAPEAMENTO_MAZUSOFT_REA.md). Não foram gerados, salvos ou alterados jogos ou estudos. Algumas tabelas premium e interações não puderam ser verificadas; o erro da opção “combinação exata” não permite inferir seu comportamento. O navegador descartável do REA recebeu uma verificação anti-bot; por isso, a paridade não foi comprovada. As estatísticas desta implementação são cálculos descritivos transparentes e não reproduzem fórmulas proprietárias não documentadas. Para estatísticas de repetidas da Lotofácil, lacunas entre concursos tornam o indicador indisponível; na UI/IA esses dados não são apresentados como válidos, e o campo legado permanece zero apenas por compatibilidade.
