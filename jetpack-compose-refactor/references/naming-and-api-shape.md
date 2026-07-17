# Naming, ordenação de parâmetros e forma de API

Checagens do scanner que caem neste tópico: `composable-naming`,
`event-callback-naming`, `param-ordering`, `multiple-content-emitters`,
`preview-naming-visibility`.

## Naming de composables

- Composables que **emitem UI** (retornam `Unit`) usam PascalCase de substantivo —
  como se fossem um tipo/componente, não um verbo: `UserCard`, não `userCard` nem
  `showUserCard`. **Finding: `composable-naming`** (mirrors: Android Lint
  `ComposableNaming`).
- Composables que **retornam um valor** (ex.: um composable "factory" que devolve um
  `State<T>` via `remember`) seguem a convenção normal de função Kotlin, lowerCamelCase
  — ex.: `rememberScrollState()`. O scanner só valida o caso PascalCase (emissão de
  UI); o caso lowerCamelCase-com-retorno não é sinalizado.

## Naming de callbacks de evento

Parâmetros do tipo `() -> Unit` (ou `(T) -> Unit`) que representam uma interação do
usuário devem começar com `on`: `onClick`, `onValueChange`, `onDismissRequest`.
**Finding: `event-callback-naming`** (severidade `info`; mirrors: detekt/ktlint
compose-rules `ComposableEventParameterNaming`).
- Exceção: parâmetros de **slot de conteúdo** (`content`, `label`, `icon`,
  `leadingIcon`, `title`, etc.) não são eventos e não precisam do prefixo `on` — o
  scanner já exclui esses nomes comuns da checagem.

## Ordenação de parâmetros

Convenção (de trás para frente, a mais importante primeiro): parâmetros
**obrigatórios** (sem default) vêm primeiro, depois `modifier`, depois os demais
**opcionais** (com default), e por último — se existir — o **slot de conteúdo**
`@Composable` (ex.: `content: @Composable () -> Unit`), para permitir a sintaxe de
trailing lambda no call site (`MyCard(title) { ... }` em vez de
`MyCard(title, content = { ... })`).

**Importante**: essa exigência de "vir por último" vale só para slots de conteúdo
`@Composable` de verdade, não para qualquer parâmetro do tipo `() -> Unit`. Um
callback de evento comum (`onClick: () -> Unit`) é um parâmetro obrigatório normal e
pode/deve vir antes de `modifier`, junto dos outros obrigatórios — não é obrigado a
ser o último parâmetro. **Finding: `param-ordering`** cobre dois casos:
1. Um parâmetro opcional (com default) aparecendo antes de `modifier`.
2. Um parâmetro de slot de conteúdo `@Composable` que não está na última posição.

Mirrors: Android Lint `ComposableParametersOrdering`; detekt compose-rules
`ComposableParamOrder`.

## Múltiplos emissores de UI sem slots

Um composable que emite mais de um componente de UI diretamente no nível raiz do seu
corpo (sem envolvê-los num único container `Row`/`Column`/`Box`, e sem expor slots
nomeados para isso) tende a ser difícil de reutilizar — quem chama não controla como
esses elementos se organizam entre si. **Finding: `multiple-content-emitters`**
(mirrors: detekt/ktlint compose-rules `ComposeMultipleContentEmitters`).
- Fix: envolva os emissores num único container apropriado, ou refatore para expor
  slots nomeados (`leadingIcon: @Composable () -> Unit`, `trailingIcon: @Composable
  () -> Unit`, etc.) se cada emissor representa uma região logicamente distinta que
  quem chama deveria poder customizar/omitir independentemente.
- O scanner só conta chamadas conhecidas de componentes do Material/Foundation no
  nível raiz do corpo (profundidade zero de chaves) — chamadas dentro de lambdas
  aninhadas (ex.: dentro do `content` de uma `Row`) não contam como "emissores soltos".

## Convenções de `@Preview`

- Funções `@Preview` não deveriam ser públicas — são um artefato de tooling/IDE, não
  parte da API do módulo. **Finding: `preview-naming-visibility`.**
- O nome deve terminar com o sufixo `Preview` (ex.: `UserCardPreview`), para ficar
  claro na navegação do projeto e em buscas que aquela função não é um composable de
  produção.
- Mirrors: detekt/ktlint compose-rules `ComposePreviewNaming`, `ComposePreviewPublic`.
