# Interação e foco

Checagens do scanner que caem neste tópico: `interaction-source-in-clickable`,
`interaction-source-manual-collect`, `interaction-source-not-hoisted`,
`interaction-source-callback-not-stable`.

Nenhuma tem equivalente direto em Android Lint, ktlint compose-rules ou detekt
compose-rules hoje — são regras próprias baseadas na API pública do Compose
Foundation (`androidx.compose.foundation.interaction.MutableInteractionSource`).

## Por que `InteractionSource` em vez de `onFocusEvent`

`Modifier.onFocusEvent { }` é a API correta para **observar foco por teclado/D-pad**
(TV, TalkBack focus traversal, navegação externa). Mas ela só dispara em composables
que tenham `Modifier.focusable()` na chain — nem `Card`/`ElevatedCard`/`OutlinedCard`
nem `Surface` do Material3 trazem `focusable()` por padrão. Resultado: um `Card`
com `onClick` que usa `Modifier.onFocusEvent { ... }` para "saber se está sendo
usado" **nunca recebe o callback** (porque o card nunca fica focado), e o `var`
mutado dentro do lambda é dead code.

`InteractionSource` é a API idiomática do Compose para observar o que o usuário
está fazendo com um composable interativo, e expõe **todos** os signals relevantes:

| Interaction | Quando dispara |
|---|---|
| `PressInteraction.Press` | dedo (ou mouse) pressionou |
| `PressInteraction.Release` | dedo/mouse soltou (mesmo se arrastou pra fora) |
| `PressInteraction.Cancel` | gesto foi cancelado (ex.: scroll consumiu) |
| `FocusInteraction.Focus` | ganhou foco por teclado/D-pad |
| `FocusInteraction.Unfocus` | perdeu foco |
| `DragInteraction.Start/Stop/Cancel` | arraste começou/terminou |

Os componentes Material3 que aceitam `onClick` também aceitam um parâmetro
`interactionSource: MutableInteractionSource`. Passar a referência dá ao caller
controle total sobre cores de ripple/pressed/hover, animação, side-effects, etc.

## `interaction-source-in-clickable`

**Finding:** `interaction-source-in-clickable` (severidade `info`).

**Quando dispara:** o corpo de um composable contém **simultaneamente**:

- um `Card(...)`/`ElevatedCard(...)`/`OutlinedCard(...)`/`Surface(...)` com
  `onClick` em algum lugar, **ou** um `Modifier.clickable(...)` na chain, **e**
- um `Modifier.onFocusEvent(...)` em algum lugar, **e**
- **nenhuma** referência a `InteractionSource`/`MutableInteractionSource`/
  `interactionSource` no escopo da função.

**Quando NÃO dispara** (falsos positivos evitados pelo escopo):

- Composables que usam `onFocusEvent` sem superfície clicável no mesmo corpo
  (legítimo: observar foco num `TextField`, num `OutlinedTextField`, num wrapper
  com `Modifier.focusable()` aplicado manualmente, etc.).
- Composables que já usam `InteractionSource` — qualquer forma de
  `InteractionSource`/`MutableInteractionSource`/`interactionSource` no corpo
  suprime o finding.
- Composables com `Card`/`Surface` sem `onClick` (decorativos) — não são
  interativos, então não há expectativa de observar interação.

**Por que `info` e não `warning`:** detecção de intenção é frágil. Há casos
legítimos em que `onFocusEvent` é a escolha certa (ex.: card de UI de TV sem
toque), e a checagem depende de uma heurística textual. Severidade `info` evita
bloquear CI em projetos onde o padrão é outro.

## Como corrigir

```kotlin
// Padrão 1: passar MutableInteractionSource ao Card e coletar interactions
val interactionSource = remember { MutableInteractionSource() }
LaunchedEffect(interactionSource) {
    interactionSource.interactions.collect { interaction ->
        when (interaction) {
            is PressInteraction.Press -> { /* ... */ }
            is PressInteraction.Release -> { /* ... */ }
            is FocusInteraction.Focus -> { /* ... */ }
        }
    }
}
Card(
    onClick = onOkCallback,
    interactionSource = interactionSource,
    modifier = modifier,
) { /* ... */ }

// Padrão 2: Modifier.clickable com interactionSource explícito
val interactionSource = remember { MutableInteractionSource() }
Box(
    modifier = modifier
        .clickable(
            interactionSource = interactionSource,
            indication = rememberRipple(),
            onClick = onOkCallback,
        ),
)
```

Veja `examples/14-interaction-source-before-after.md` para o diff completo antes/
depois aplicado ao caso real que motivou esta regra (composable `Teste` no
projeto `sleep_visualizer`).

## `interaction-source-manual-collect`

**Finding:** `interaction-source-manual-collect` (severidade `info`).

**Quando dispara:** o corpo de um composable contém `<algo>.interactions.collect { ... }`
(coleta manual do `Flow<Interaction>`) e, dentro desse bloco, os únicos tipos de
`Interaction` referenciados pertencem a um único eixo:

| Eixo | Subtipos | Helper declarativo equivalente |
|---|---|---|
| pressed | `PressInteraction.Press`/`Release`/`Cancel` | `collectIsPressedAsState()` |
| focused | `FocusInteraction.Focus`/`Unfocus` | `collectIsFocusedAsState()` |
| dragged | `DragInteraction.Start`/`Stop`/`Cancel` | `collectIsDraggedAsState()` |
| hovered | `HoverInteraction.Enter`/`Exit` | `collectIsHoveredAsState()` |

**Quando NÃO dispara:** o bloco mistura tipos de mais de um eixo (ex.: `Press` e
`Focus` juntos) — nesse caso não existe um único helper que cubra o caso, e a
coleta manual (com `LaunchedEffect` + `when`) é a forma correta.

**Por que `info`:** o helper `collectIsXAsState()` resume o eixo inteiro num
único `Boolean` — se o código faz algo mais elaborado que só "ligar/desligar um
estado" dentro do `when` (ex.: disparar um evento one-shot diferente em Press vs.
em Release), a troca não é 1:1. A checagem sinaliza a oportunidade, mas quem
revisa precisa confirmar que o `when` só deriva estado.

## `interaction-source-not-hoisted`

**Finding:** `interaction-source-not-hoisted` (severidade `info`).

**Quando dispara:** o composable **cria** sua própria instância
(`remember { MutableInteractionSource() }` ou `MutableInteractionSource()` direto,
sem receber via parâmetro), tem pelo menos um parâmetro de callback (tipo função,
ex.: `onClick: () -> Unit`) — sinal de que é um componente parametrizado/
reutilizável, não uma tela-folha — e contém uma superfície clicável (`Card`/
`Surface` com `onClick`, ou `Modifier.clickable`).

**Quando NÃO dispara:** o composable já recebe `interactionSource` como
parâmetro (com ou sem valor default) — o padrão idiomático é
`interactionSource: MutableInteractionSource = remember { MutableInteractionSource() }`,
que continua "hoisted" mesmo com um `remember` no valor default, porque quem
chama pode sobrescrever.

**Por que `info`:** "é reutilizável" é inferido pela presença de um parâmetro de
callback — heurística razoável, mas nem todo composable com um `onClick` é uma
peça de design system pensada para reuso/testes; screens-folha também podem ter
esse formato legitimamente sem precisar expor `interactionSource`.

## `interaction-source-callback-not-stable`

**Finding:** `interaction-source-callback-not-stable` (severidade `info`).

**Quando dispara:** um parâmetro de callback (tipo função) do composable é
referenciado dentro de um `LaunchedEffect(...)` cujo corpo também referencia
`.interactions`/`interactionSource`/`InteractionSource` (escopo deste módulo), o
nome do callback **não** é uma das keys desse `LaunchedEffect`, e
`rememberUpdatedState` não aparece em nenhum lugar do corpo da função.

**Quando NÃO dispara:**

- `rememberUpdatedState` aparece em qualquer lugar do corpo (assume-se que o
  padrão foi aplicado corretamente).
- o próprio callback é uma das keys do `LaunchedEffect` (ex.:
  `LaunchedEffect(interactionSource, onClick) { ... }`) — o effect reinicia
  quando o callback muda, então não há referência obsoleta (o trade-off é
  reiniciar a coroutine, potencialmente perdendo eventos em trânsito).

**Por quê isso importa:** `LaunchedEffect` só reinicia quando uma de suas keys
muda. Se o corpo captura um parâmetro de callback por closure sem incluí-lo nas
keys, a coroutine continua rodando com a lambda da composição em que nasceu —
se o pai recompuser com uma nova lambda (ex.: uma outra instância de `() -> Unit`
por causa de uma variável capturada), a versão antiga é a que executa.
`rememberUpdatedState(callback)` resolve isso sem reiniciar o effect: mantém uma
referência sempre atualizada, lida dentro da coroutine.

**Por que `info`:** a checagem não verifica se a lambda passada realmente muda de
identidade entre recomposições (pode ser um `remember` no pai, ou uma referência
de método estável) — sinaliza o padrão de risco, não uma certeza de bug.
