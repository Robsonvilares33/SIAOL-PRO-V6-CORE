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

## Limites da inspeção

A pesquisa usou conteúdo público extraído das páginas. Não foram feitos login, submissão de formulários, tentativas de acesso a páginas premium, nem inspeção de endpoints internos. Algumas tabelas premium e interações que exigem clique não puderam ser verificadas. O navegador direto recebeu uma verificação anti-bot; por isso, a paridade visual deve ser refinada com confirmação do proprietário ou uma captura de referência que possa ser acessada normalmente. As estatísticas desta implementação são cálculos descritivos transparentes e não reproduzem fórmulas proprietárias não documentadas.
