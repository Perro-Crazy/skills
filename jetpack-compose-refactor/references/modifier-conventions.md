# Convenções de `Modifier`

Checagens do scanner que caem neste tópico: `modifier-param-missing`,
`modifier-param-no-default`, `modifier-param-wrong-name`, `modifier-reused`,
`modifier-composed-deprecated`, `multiple-modifier-params`, `modifier-chain-order-risk`.

## Por que a convenção existe

`Modifier` é o mecanismo do Compose para que quem **chama** um composable ajuste
layout, tamanho, padding, semântica, clique, etc. de fora, sem o composable precisar
expor um parâmetro específico para cada uma dessas coisas. Um composable que emite UI
mas não aceita `Modifier` de fora não pode ser reutilizado em contextos diferentes
(ex.: dentro de uma `Row` que precisa de `weight(1f)`, ou com `testTag` para testes).

## As quatro regras de forma

1. **Exatamente um parâmetro `Modifier`**, nunca dois ou mais — se o composable
   precisa aplicar modificadores diferentes a partes internas diferentes, isso deve
   ser resolvido internamente (`modifier.then(...)` em pontos específicos), não com
   múltiplos parâmetros `Modifier` na assinatura pública. **Finding:
   `multiple-modifier-params`.**
2. **Nomeado exatamente `modifier`** — não `mod`, `modif`, `containerModifier`, etc.
   **Finding: `modifier-param-wrong-name`** (mirrors: detekt/ktlint compose-rules
   `ModifierNaming`).
3. **Com valor default `= Modifier`** — permite chamar o composable sem precisar
   passar um `Modifier` explícito no caso comum. **Finding: `modifier-param-no-default`**
   (mirrors: detekt/ktlint compose-rules `ModifierWithoutDefault`).
4. **Presente em todo composable público que emite UI** — se o composable chama
   qualquer função de layout/componente conhecida (`Box`, `Row`, `Text`, `Button` etc.)
   mas não tem parâmetro `Modifier` nenhum, isso é sinalizado. **Finding:
   `modifier-param-missing`** (mirrors: Android Lint `ModifierParameter`; detekt/ktlint
   compose-rules `ModifierMissing`).

## Posição na assinatura

`modifier` deve vir logo após os parâmetros obrigatórios (sem default) e antes dos
parâmetros opcionais — ver `references/naming-and-api-shape.md` para a ordenação
completa. Isso é convenção, não uma regra técnica, mas facilita muito ler/comparar
assinaturas de composables em toda a base.

## Reuso da mesma instância em múltiplos filhos

Cada filho direto de um composable deveria receber seu **próprio** `Modifier`
(tipicamente construído a partir do `modifier` recebido só no elemento raiz, e
`Modifier` "puro" — ou um novo derivado — nos filhos). Se a mesma variável `modifier`
é passada como valor para mais de um filho irmão, qualquer coisa que o chamador tenha
aplicado (padding, clique, tamanho) acaba se repetindo em todos os filhos, o que quase
sempre não é a intenção. **Finding: `modifier-reused`** (severidade `info` — é uma
heurística textual contando quantas vezes o nome do parâmetro aparece como valor no
corpo; sempre confirme visualmente antes de agir, já que passar `modifier` uma vez
para o container raiz e usar `Modifier` "limpo" nos filhos internos é o padrão comum
e correto — o finding só é real quando a mesma variável vai para **mais de um** filho).
- Mirrors: detekt/ktlint compose-rules `ModifierReused`.
- Fix: aplique `modifier` só no elemento raiz do composable; filhos internos recebem
  `Modifier` novo (ou um derivado específico, não compartilhado).

## `Modifier.composed { }` está em migração

`Modifier.composed { }` permite que um `Modifier` customizado leia estado
`@Composable` (ex.: `remember`, tema) — mas tem custo de performance (recompõe a cada
uso) e a API está sendo gradualmente substituída por `ModifierNodeElement`/
`Modifier.Node`, que é mais eficiente e não exige uma lambda composable. **Finding:
`modifier-composed-deprecated`** (severidade `info` — sinaliza qualquer uso de
`composed { }`/`composed(...)` no arquivo, não só dentro de composables, já que a API
mais comum de declarar isso é via uma extension function de `Modifier` que não é ela
mesma anotada `@Composable`).
- Sem regra de linter dedicada até o momento — é a recomendação oficial de migração da
  equipe do Compose.
- Fix: para modificadores novos, prefira implementar `ModifierNodeElement` +
  `Modifier.Node`. Para modificadores existentes usando `composed { }` que já
  funcionam bem, migrar é uma melhoria de performance, não uma correção de bug — priorize
  conforme o impacto (uso em listas grandes/recomposição frequente pesa mais).

## Ordem de encadeamento do `modifier` recebido

O `modifier` recebido do chamador deveria normalmente ser o **início** da cadeia
aplicada ao elemento raiz (`modifier.background(...).padding(...)`), não anexado ao
final via `.then(...)` (`Modifier.background(...).then(modifier)`). Quando o
`modifier` do chamador é anexado por último, os modificadores internos do componente
são aplicados primeiro, invertendo a precedência esperada — o chamador normalmente
espera poder sobrepor/ajustar o que o componente já aplica, não o contrário. **Finding:
`modifier-chain-order-risk`** (severidade `info` — o scanner só reconhece o padrão
textual literal `.then(<nome-do-parâmetro-modifier>)`; não analisa a cadeia inteira).
- Sem regra de linter dedicada — checagem própria.
- Fix: reordene para que o `modifier` recebido seja o receiver inicial da cadeia:
  `modifier.background(...)` em vez de `Modifier.background(...).then(modifier)`.
