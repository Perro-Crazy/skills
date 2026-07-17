# Performance de listas preguiçosas (`LazyColumn`/`LazyRow`/`LazyVerticalGrid`)

Checagens do scanner que caem neste tópico: `lazy-items-missing-key`,
`lazy-items-missing-content-type`, `lazy-item-modifier-not-hoisted`.

## O caso canônico de "linter é necessário, mas não suficiente"

Nenhuma das duas checagens abaixo tem cobertura em Android Lint, ktlint compose-rules
ou detekt compose-rules hoje. Isso é intencional como exemplo dentro deste skill: um
projeto pode passar 100% limpo em todos os três linters e ainda ter problemas reais de
performance em listas — por isso o workflow em `SKILL.md` sempre roda essas checagens
adicionais, mesmo quando os linters configurados não acusam nada.

## `key =` em `items(...)`

Ao usar `items(list) { item -> ... }` dentro de uma `LazyColumn`/`LazyRow`/
`LazyVerticalGrid` sem passar `key = { ... }`, o Compose usa a **posição** do item
como identidade. Se a lista muda (item inserido/removido/reordenado no meio), todos os
itens após o ponto de mudança são tratados como "itens diferentes" na posição em vez
de reconhecidos como os mesmos itens movidos — o que quebra animações de
inserção/remoção e causa recomposição/recriação de estado desnecessária (ex.: o estado
de scroll ou de expansão de um item específico "pula" para outro).

**Finding: `lazy-items-missing-key`.**
- Fix: `items(list, key = { it.id }) { item -> ... }`, usando um identificador
  **estável e único** por item — nunca o índice da lista (o índice muda exatamente nos
  casos em que a key deveria proteger contra isso).

## `contentType =` em `items(...)`

Quando uma lista mistura tipos de item heterogêneos (ex.: cabeçalhos, separadores,
itens de conteúdo, todos na mesma `LazyColumn`), declarar `contentType = { ... }`
permite ao Compose reaproveitar melhor as composições existentes ao reciclar slots de
layout, reduzindo o custo de recomposição ao rolar. **Finding:
`lazy-items-missing-content-type`** (severidade `info` — é uma otimização, não um bug;
menos crítico que `key` ausente, mas vale mencionar quando a lista claramente mistura
tipos).
- Fix: `items(list, key = { ... }, contentType = { it.type }) { item -> ... }`.
- Para listas homogêneas (todo item é do mesmo tipo/layout), esse ganho é marginal —
  priorize a correção de `key` ausente primeiro.

## Cadeia de `Modifier` reconstruída a cada item

Um `Modifier` (`Modifier.fillMaxWidth().padding(16.dp)` etc.) construído dentro do
lambda de item de `items(...)`/`itemsIndexed(...)` que **não depende dos dados do
item** é recriado do zero a cada item recomposto, mesmo sendo sempre idêntico — um
candidato claro para ser hoisted para uma `val` declarada uma única vez fora do
lambda. **Finding: `lazy-item-modifier-not-hoisted`** (severidade `info` — a checagem
mais heurística deste tópico; ver limitações abaixo).
- Sem regra de linter dedicada — checagem própria.
- Fix: `val rowModifier = Modifier.fillMaxWidth().padding(16.dp)` declarado fora do
  `items(...) { ... }`, reutilizado em cada item.
- **Exceção que o scanner já exclui**: cadeias que usam funções dependentes do scope
  do item (`.align(...)`, `.weight(...)`, `.matchParentSize()`, `.animateItem()`) não
  podem ser hoisted mesmo sem depender do dado do item, pois exigem o receiver de
  scope local (`BoxScope`/`RowScope`/`LazyItemScope`) — essas não são sinalizadas.
- **Limitação conhecida**: o scanner só verifica se o **nome literal** do(s)
  parâmetro(s) do item aparece na cadeia — uma variável local derivada do item
  (`val cor = item.corPreferida; Modifier.background(cor)`) não é detectada como
  dependência, e a cadeia pode ser sinalizada incorretamente como hoistable. Confirme
  manualmente antes de mover.
