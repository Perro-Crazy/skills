# Estado e recomposição

Checagens do scanner que caem neste tópico: `unremembered-mutable-state`,
`autoboxing-state-creation`, `unstable-collection-param`, `launched-effect-key-risk`,
`composition-local-overuse`.

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
