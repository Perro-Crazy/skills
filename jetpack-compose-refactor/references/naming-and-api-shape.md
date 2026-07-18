# Naming, ordenação de parâmetros e forma de API

Checagens do scanner que caem neste tópico: `composable-naming`,
`event-callback-naming`, `param-ordering`, `multiple-content-emitters`,
`preview-naming-visibility`, `composable-emit-and-return`, `content-slot-param-naming`,
`event-trailing-lambda`, `scaffold-padding-ignored`, `boxwithconstraints-unused-scope`,
`animatedcontent-unused-target`, `composable-annotation-naming`,
`preview-annotation-naming`, `material2-usage`, `material3-deprecated-divider`.

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

## Emitir UI XOR devolver valor

As guidelines oficiais de API do Compose são explícitas: um composable deve **ou**
emitir UI (nesse caso, retorna `Unit`) **ou** calcular e devolver um valor — nunca os
dois na mesma função. Misturar os dois torna o composable difícil de testar (o valor
de retorno só existe se a função também compuser UI) e quebra a expectativa de quem
chama, que não espera precisar "descartar" um valor de retorno de algo que parece só
desenhar a tela. **Finding: `composable-emit-and-return`** — dispara quando o tipo de
retorno não é `Unit`/vazio e o corpo também chama pelo menos um componente de UI
conhecido no nível raiz.
- Sem regra de linter dedicada — checagem própria.
- Fix: separe as duas responsabilidades — um composable que só emite UI, e uma função
  Kotlin comum (não `@Composable`) que calcula o valor, chamada por quem precisar dele.

## Naming do parâmetro de slot de conteúdo

Quando um composable expõe exatamente um parâmetro de slot de conteúdo `@Composable`
(uma lambda trailing usada para permitir customização do conteúdo interno), a
convenção é nomeá-lo `content` — o mesmo padrão usado pelos componentes do Material/
Foundation (`Box(content: @Composable BoxScope.() -> Unit)`, `Card(content: ...)`
etc.). **Finding: `content-slot-param-naming`** (severidade `info`).
- Sem regra de linter dedicada — checagem própria.
- Exceção conhecida e legítima: nomes específicos de contexto, como `itemContent` em
  wrappers de listas (`LazyColumn`), continuam fora do allowlist atual de nomes de
  slot — o finding dispara mesmo assim, mas confirme antes de renomear, já que nesses
  casos o nome específico costuma ser mais claro que `content` genérico.

## Callback de evento como trailing lambda

A trailing lambda (último parâmetro) deve ser reservada para o **slot de conteúdo**
`@Composable`, porque no call site ela vira o bloco `{ }` após a chamada. Um callback
de evento (`onClick: () -> Unit`) na última posição, **depois** do `modifier`, ocupa
esse lugar e faz o call site parecer que aceita conteúdo (`MyButton("x") { ... }`
parece um slot de conteúdo, mas é o `onClick`). **Finding: `event-trailing-lambda`**
(severidade `info`; o scanner sinaliza quando o último parâmetro é uma lambda de evento
não-`@Composable` com nome `on*` e existe um parâmetro `modifier` antes dele).
- Mirrors: ktlint/detekt compose-rules `LambdaParameterEventTrailing`.
- Fix: mova o evento para junto dos parâmetros obrigatórios, antes do `modifier`.

## Slots que ignoram o valor fornecido

Alguns componentes entregam um valor ao lambda de conteúdo que **precisa** ser usado —
ignorá-lo é um bug:

- **`Scaffold`/`BottomSheetScaffold`** entregam um `PaddingValues` que representa o
  espaço ocupado por `topBar`/`bottomBar`. Se o lambda de conteúdo não o aplica (ex.:
  `Modifier.padding(innerPadding)`), o conteúdo fica **atrás** das barras. **Finding:
  `scaffold-padding-ignored`** (severidade `warning`; o scanner sinaliza quando o lambda
  de conteúdo não captura o parâmetro, ou o captura e não o referencia).
  - Mirrors: Android Lint `UnusedMaterial3ScaffoldPaddingParameter`.
- **`AnimatedContent`** entrega o `targetState` ao lambda; usar a variável externa em
  vez do parâmetro recebido faz o conteúdo animado renderizar o estado errado durante a
  transição. **Finding: `animatedcontent-unused-target`** (severidade `warning`).
  - Mirrors: Android Lint `UnusedContentLambdaTargetStateParameter`.
- **`BoxWithConstraints`** expõe `constraints`/`maxWidth`/`maxHeight`/... — se o corpo
  não os usa, um `Box` comum é mais barato (`BoxWithConstraints` adia a composição do
  conteúdo até a medição). **Finding: `boxwithconstraints-unused-scope`** (severidade
  `info`).
  - Mirrors: Android Lint `UnusedBoxWithConstraintsScope`.

## Naming de annotation classes

- **Annotation de multipreview** (uma `annotation class` que agrega vários `@Preview`)
  deve usar o prefixo `Preview` (ex.: `PreviewScreenSizes`). **Finding:
  `preview-annotation-naming`** (severidade `info`).
  - Mirrors: ktlint/detekt compose-rules `PreviewAnnotationNaming`.
- **Annotation marcada com `@Composable`** deve terminar com o sufixo `Composable`.
  **Finding: `composable-annotation-naming`** (severidade `info`).
  - Mirrors: ktlint/detekt compose-rules `ComposableAnnotationNaming`.

## Material 2 num projeto Material 3

Import de `androidx.compose.material.*` (Material 2, excluindo os subpacotes `icons`/
`ripple`/`pullrefresh`) num projeto que usa Material 3 mistura dois design systems —
inconsistência visual e de tema. **Finding: `material2-usage`** (severidade `info`;
checagem de nível de arquivo, sobre os imports; é opt-in no compose-rules upstream, mas
aqui é sinalizada como `info` para revisão).
- Mirrors: ktlint/detekt compose-rules `Material2` (`compose:material-two`); Android
  Lint `UsingMaterialAndMaterial3Libraries`.
- Fix: use o equivalente em `androidx.compose.material3`. Se a migração para M3 ainda
  não é viável, é uma decisão de projeto — não troque imports sem confirmar.

## `Divider` deprecated no Material 3

`androidx.compose.material3.Divider` está marcado `@Deprecated` desde a versão 1.1.0 do
Compose Material3, em favor de `HorizontalDivider`/`VerticalDivider` — a API antiga não
deixava explícita a orientação, obrigando quem lê a inferir pelo contexto do layout
(`Row`/`Column`) em vez do nome da própria chamada. **Finding:
`material3-deprecated-divider`** (severidade `info`; checagem própria, textual — o
scanner não distingue se o `Divider` importado é de `material` (M2) ou `material3`).
- Sem regra de linter dedicada — checagem própria.
- Se o `Divider` em questão for do Material 2, o finding `material2-usage` cobre a
  migração do import; este finding é sobre a chamada em si, deprecated em ambos os casos
  depois da migração para M3.
- Fix: troque por `HorizontalDivider(...)` (caso mais comum, divisor horizontal dentro de
  uma `Column`) ou `VerticalDivider(...)` (dentro de uma `Row`), conforme a orientação real
  do divisor no layout.
