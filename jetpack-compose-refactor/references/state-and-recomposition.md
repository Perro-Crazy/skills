# Estado e recomposição

Checagens do scanner que caem neste tópico: `unremembered-mutable-state`,
`autoboxing-state-creation`, `unstable-collection-param`, `launched-effect-key-risk`,
`composition-local-overuse`, `disposable-effect-missing-ondispose`,
`backwards-state-write`, `unmemoized-derived-collection`, `coroutine-in-composition`,
`flow-operator-in-composition`, `mutable-collection-in-state`,
`collect-as-state-not-lifecycle-aware`, `unremembered-object`, `composition-local-naming`,
`immutable-annotation-with-var`, `unstable-type-param`, `mutable-state-param`,
`mutable-class-param`.

## `remember` vs `rememberSaveable` vs `derivedStateOf`

- `remember { mutableStateOf(...) }` sobrevive a recomposições, mas **não** a mudanças
  de configuração (rotação) nem a morte de processo — o valor volta ao inicial.
- `rememberSaveable { mutableStateOf(...) }` sobrevive também a isso, desde que o tipo
  seja `Parcelable`/`Serializable` ou tenha um `Saver` customizado. Use para estado de
  UI que o usuário esperaria ver preservado (texto digitado, aba selecionada, posição
  de scroll relevante).
- Sem `remember` nenhum: `val x = mutableStateOf(...)` dentro do corpo de um composable
  recria o `State` do zero a cada recomposição, perdendo qualquer valor — geralmente um
  bug, não uma escolha intencional. **Finding: `unremembered-mutable-state`.**
  - Mirrors: Android Lint `UnrememberedMutableState`; detekt compose-rules
    `ComposeRememberMissing`.
  - Fix: envolver em `remember { }` (ou `rememberSaveable { }` se precisar sobreviver a
    mudança de configuração/processo).
- `derivedStateOf { }` — use quando o valor é **derivado** de outro estado que muda com
  mais frequência do que o resultado precisa recompor. Exemplo clássico: `firstVisibleItemIndex`
  de uma `LazyListState` muda a cada scroll, mas um botão "voltar ao topo" só precisa
  recompor quando cruza um threshold (`> 0` vs `== 0`) — sem `derivedStateOf`, o botão
  recomporia a cada pixel de scroll.

## Autoboxing em `mutableStateOf`

`mutableStateOf<Int>(0)` ou `mutableStateOf(0)` cria um `MutableState<Int>` genérico,
que faz autoboxing (`Int` -> `Integer`) a cada leitura/escrita. Para os tipos primitivos
mais comuns em UI (contadores, offsets, opacidade), existem variantes especializadas
sem boxing: `mutableIntStateOf`, `mutableFloatStateOf`, `mutableLongStateOf`,
`mutableDoubleStateOf`. **Finding: `autoboxing-state-creation`.**
- Mirrors: Android Lint `AutoboxingStateCreation`.
- Fix: trocar por `mutableIntStateOf(0)`/`mutableFloatStateOf(0f)`/etc, e ler o valor
  via `.intValue`/`.floatValue` em vez de `.value`.
- Não vale a pena para tipos não-primitivos (`String`, data classes, enums) — ali não
  há boxing a evitar.

## Parâmetros de coleção instáveis

Compose decide se pode **pular** (skip) a recomposição de um composable comparando
seus parâmetros por estabilidade. `List<T>`, `Map<K,V>` e `Set<T>` da stdlib do Kotlin
são interfaces que **podem** ser mutáveis por trás (`ArrayList`, `LinkedHashMap` etc.),
então o compilador do Compose as marca como **instáveis** — todo composable que recebe
um `List<T>` como parâmetro nunca pode ser pulado, mesmo que a lista não tenha mudado.
**Finding: `unstable-collection-param`.**
- Mirrors: detekt/ktlint compose-rules `ComposeUnstableCollections`.
- Fix preferido: trocar por `ImmutableList<T>`/`ImmutableMap<K,V>`/`ImmutableSet<T>`
  de `kotlinx.collections.immutable` (`persistentListOf`, `.toImmutableList()`) —
  o compilador do Compose reconhece esses tipos como estáveis.
- Alternativa sem adicionar dependência nova: envolver a coleção num wrapper anotado
  `@Immutable` (se a coleção interna nunca é mutada após a criação) ou `@Stable` (se
  há mutação controlada com notificação, ex.: via `SnapshotStateList`).
- **Nunca adicione a dependência `kotlinx-collections-immutable` no projeto-alvo sem
  confirmar com quem pediu a refatoração** — é uma decisão de dependência que afeta o
  time todo. Sinalize a sugestão e proponha o wrapper `@Immutable` como alternativa que
  não exige nova dependência.

## Side-effects: `LaunchedEffect` / `DisposableEffect` / `SideEffect`

- A **key** de um `LaunchedEffect(key1, key2, ...)` controla quando o efeito é
  cancelado e relançado. `LaunchedEffect(Unit)`/`LaunchedEffect(true)` roda só uma vez
  por entrada na composição — correto para inicialização única, **errado** se o corpo
  do efeito lê algum valor externo que muda ao longo do tempo (o efeito não vai
  perceber a mudança). **Finding: `launched-effect-key-risk`** (severidade `info` —
  é um lembrete para revisão manual, não uma certeza de bug, já que o scanner não
  consegue provar que o corpo referencia algo fora da key).
  - Sem regra de linter dedicada — checagem própria inspirada nas diretrizes oficiais
    de side-effects do Compose.
  - Ao revisar: se o corpo do efeito referencia um parâmetro do composable, um valor de
    `remember`/state, ou qualquer coisa que possa mudar, considere se deveria estar na
    key.
- `rememberCoroutineScope()` — use para lançar uma corrotina em resposta a um evento do
  usuário (ex.: clique de botão chama `scope.launch { ... }`), **não** `LaunchedEffect`,
  que é para efeitos atrelados ao ciclo de vida da composição em si.
- `DisposableEffect`/`SideEffect` seguem a mesma lógica de key que `LaunchedEffect`.

## `CompositionLocal`

`CompositionLocal` (via `.current`) é o mecanismo do Compose para passar dados
implicitamente pela árvore de composição sem precisar declará-los como parâmetro em
cada nível — genuinamente útil para preocupações **transversais**: tema
(`MaterialTheme`), densidade de tela, direção de layout, lifecycle owner. Quando usado
para dados de **negócio** (sessão de usuário, estado de feature flags, ViewModels),
vira um acoplamento implícito difícil de rastrear e testar. **Finding:
`composition-local-overuse`** (severidade `info` — o scanner sinaliza qualquer
`Local*.current` fora de uma lista de CompositionLocals de plataforma conhecidos, para
revisão manual).
- Mirrors: detekt compose-rules `CompositionLocalUsage`.
- Ao revisar: se o `CompositionLocal` carrega dado de negócio, prefira passá-lo como
  parâmetro explícito (hoisting) — mais fácil de testar, ter preview e rastrear de onde
  vem o valor.

## `DisposableEffect` sem `onDispose`

Todo `DisposableEffect(key) { ... }` precisa terminar devolvendo um
`DisposableEffectResult`, e a única forma pública de construir um é `onDispose { }` —
o bloco de limpeza chamado quando o efeito sai de composição ou é relançado (troca de
key). Um `DisposableEffect` sem `onDispose` no corpo normalmente indica um recurso
registrado (`addObserver`, listener, `BroadcastReceiver`) que nunca é liberado.
**Finding: `disposable-effect-missing-ondispose`.**
- Sem regra de linter dedicada — checagem própria, mesma família de
  `launched-effect-key-risk` (diretrizes oficiais de side-effects do Compose).
- Fix: sempre parear o registro de um recurso com sua liberação correspondente dentro
  de `onDispose { }` (ex.: `addObserver`/`removeObserver`,
  `registerReceiver`/`unregisterReceiver`).
- Falso positivo conhecido: uma função auxiliar que constrói e devolve o
  `DisposableEffectResult` em outro lugar (o texto `onDispose` não aparece
  literalmente dentro deste bloco específico) — raro, mas confirme antes de assumir bug.

## Escrita "para trás" em estado (loop de recomposição)

Um `mutableStateOf`-backed (`var x by remember { mutableStateOf(...) }`) que é **lido**
(ex.: usado num `Text`) e depois **escrito de novo** (`x = ...`, `x++`, etc.) no mesmo
nível do corpo da função — fora de qualquer lambda de evento/efeito (`onClick`,
`LaunchedEffect`, etc.) — dispara uma nova recomposição a cada vez que a função roda,
e se a escrita não estiver condicionada a algo externo, isso é um loop de recomposição
infinito. **Finding: `backwards-state-write`** (severidade `info` — heurístico de
fluxo de controle baseado em profundidade de chaves, não uma prova; sempre confirme
visualmente).
- Sem regra de linter dedicada — checagem própria, inspirada no exemplo oficial
  `BackwardsWrite` da documentação de bugs de estado do Compose.
- Fix: mova a escrita para dentro de um callback (`onClick = { x++ }`), de forma que
  ela só aconteça em resposta a um evento, não a cada execução do corpo do composable.
- O scanner só reconhece a forma `var x by remember { mutableStateOf(...) }` — a forma
  `val x = remember { mutableStateOf(...) }` + `x.value = ...` não é coberta ainda.

## Transformação de coleção não memoizada

Chamadas como `.sortedBy { }`, `.sortedWith(...)`, `.filter { }`, `.map { }` ou
`.groupBy { }` feitas diretamente no corpo de um composable (inclusive dentro do
lambda de item de uma `LazyColumn`) sem estarem envolvidas por `remember { }`
recalculam a coleção inteira a cada recomposição, mesmo quando a entrada não mudou.
**Finding: `unmemoized-derived-collection`** (severidade `info` — não dá para saber o
tamanho real da coleção nem distinguir com certeza todo wrapper de efeito customizado;
prioridade menor que os outros findings de `remember` ausente).
- Sem regra de linter dedicada — checagem própria.
- Fix: `val sorted = remember(products) { products.sortedBy { it.price } }`, usando
  como key(s) do `remember` os valores dos quais o resultado realmente depende.
- O scanner ignora esse padrão quando o cercamento imediato é `LaunchedEffect`/
  `produceState` — ali a recomputação já é controlada pela key do efeito, não pela
  recomposição.

## Trabalho assíncrono na composição

- **`launch`/`async` direto no corpo do composable** — criar uma corrotina durante a
  composição a lança de novo a cada recomposição (potencialmente muitas vezes). O
  builder deve viver dentro de `LaunchedEffect(key) { }` (trabalho atrelado à
  composição) ou de `rememberCoroutineScope()` + `scope.launch { }` disparado por um
  evento (ex.: `onClick`). **Finding: `coroutine-in-composition`** (severidade
  `warning`; o scanner só sinaliza `launch`/`async` no nível direto do corpo — dentro
  de qualquer bloco `{ }`, como um `onClick` ou um efeito, não dispara).
  - Mirrors: Android Lint `CoroutineCreationDuringComposition`.
- **Operador de `Flow` (`.map`/`.filter`/`.combine`/...) encadeado com `collectAsState`
  no corpo** — recria o `Flow` a cada recomposição. **Finding:
  `flow-operator-in-composition`** (severidade `info` — o scanner sinaliza quando há um
  operador de Flow numa janela imediatamente antes de um `collectAsState`).
  - Mirrors: Android Lint `FlowOperatorInvokedInComposition`.
  - Fix: mova a transformação para o ViewModel, ou para `remember { fluxo.map { } }`.
- **`collectAsState()` em vez de `collectAsStateWithLifecycle()`** — `collectAsState`
  coleta enquanto o composable está em composição, mesmo com o app em background;
  `collectAsStateWithLifecycle` usa `repeatOnLifecycle` e pausa a coleta fora do estado
  ativo, economizando recursos/bateria. **Finding: `collect-as-state-not-lifecycle-aware`**
  (severidade `info`).
  - Recomendação oficial (developer.android.com) — sem lint dedicado habilitado por
    padrão. **Exceção**: em código multiplataforma/`commonMain`, `collectAsStateWithLifecycle`
    não existe (é Android-only); ali `collectAsState` é o correto — confirme o sourceSet
    antes de trocar.

## Coleção mutável dentro de `MutableState`

`mutableStateOf(mutableListOf())` (ou `mutableMapOf`/`ArrayList`/`HashMap`/...) guarda
uma coleção **mutável** dentro de um `MutableState`. Mutar a coleção no lugar
(`.add()`, `.remove()`) não troca a referência do `State`, então o Compose não é
notificado e a UI não recompõe. **Finding: `mutable-collection-in-state`** (severidade
`warning`).
- Mirrors: Android Lint `MutableCollectionMutableState`.
- Fix: use `mutableStateListOf`/`mutableStateMapOf` (que são observáveis), ou substitua
  a coleção inteira por uma nova (imutável) a cada mudança.

## Objetos de estado criados sem `remember`

Certos objetos que carregam estado precisam sobreviver a recomposições e por isso
devem ser criados dentro de `remember { }` (ou via a factory `rememberXxx` quando
existe): `Animatable`, `MutableInteractionSource`, `TextFieldState`, `FocusRequester`,
`BringIntoViewRequester`, e `movableContentOf`. Criá-los direto no corpo os recria a
cada recomposição, perdendo o estado acumulado. **Finding: `unremembered-object`**
(severidade `warning`; o scanner verifica a ausência de `remember` no statement da
criação).
- Mirrors: Android Lint `RememberInComposition` (família `UnrememberedAnimatable`/
  `UnrememberedMutableInteractionSource`); ktlint/detekt compose-rules
  `RememberContentMissing` (para `movableContentOf`).
- Fix: `val x = remember { Animatable(0f) }`, ou `rememberCoroutineScope`/
  `rememberTextFieldState`/etc. conforme a API.

## Naming de `CompositionLocal`

Uma propriedade criada com `compositionLocalOf`/`staticCompositionLocalOf` deve usar o
prefixo `Local` (ex.: `LocalSpacing`, não `Spacing`) — é a convenção que a distingue de
valores/estados comuns na leitura do código. **Finding: `composition-local-naming`**
(severidade `warning`; checagem de nível de arquivo, sobre a declaração).
- Mirrors: Android Lint `CompositionLocalNaming`; ktlint/detekt compose-rules
  `CompositionLocalNaming`.

## Estabilidade avançada (além de coleções instáveis)

Complementam `unstable-collection-param` (coleções `List`/`Map`/`Set`), atacando
outras fontes de instabilidade que quebram a skippability de um composable:

- **Parâmetro de tipo de estado mutável do Compose** (`MutableState<T>`,
  `MutableIntState`, `SnapshotStateList`, `SnapshotStateMap`, ...) — divide a posse do
  estado entre quem chama e o composable. **Finding: `mutable-state-param`** (severidade
  `warning`). Fix: padrão stateless — `value: T` + `onValueChange: (T) -> Unit`.
  - Mirrors: ktlint/detekt compose-rules `MutableStateParam`.
- **Parâmetro de tipo de biblioteca externa** (`java.util.Date`, `Calendar`,
  `LocalDateTime`, `LocalDate`, `LocalTime`, `Instant`) — tipos de módulos onde o
  compilador do Compose não roda são sempre instáveis. **Finding: `unstable-type-param`**
  (severidade `info` — lista conservadora de tipos claramente externos/mutáveis). Fix:
  passe os campos já formatados (ex.: uma `String`), ou envolva num tipo próprio
  anotado `@Immutable`.
  - Sem lint dedicado — diretrizes oficiais de estabilidade do Compose.
- **Parâmetro cujo tipo é uma classe com `var` no construtor** (declarada no mesmo
  arquivo) — o compilador só rastreia mutações de `State`, então qualquer classe com
  `var` é instável. **Finding: `mutable-class-param`** (severidade `info` — o scanner só
  cruza contra classes com `var` declaradas no próprio arquivo; não resolve tipos entre
  arquivos). Fix: torne as propriedades `val` e anote `@Immutable`, ou `@Stable` se há
  mutação observável.
  - Sem lint dedicado — diretrizes oficiais de estabilidade do Compose.
- **`@Immutable`/`@Stable` sobre uma classe com `var` no construtor** — a anotação é uma
  promessa de estabilidade que a classe não cumpre; o Compose pode pular recomposições
  incorretamente confiando nela. **Finding: `immutable-annotation-with-var`** (severidade
  `warning`; checagem de nível de arquivo). Fix: torne as propriedades `val`, ou remova
  a anotação.
  - Sem lint dedicado — diretrizes oficiais de estabilidade do Compose.
