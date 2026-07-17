# Performance de listas preguiçosas (`LazyColumn`/`LazyRow`/`LazyVerticalGrid`)

Checagens do scanner que caem neste tópico: `lazy-items-missing-key`,
`lazy-items-missing-content-type`.

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
