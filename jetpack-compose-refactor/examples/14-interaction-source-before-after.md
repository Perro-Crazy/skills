# Observar interação em `Card(onClick = ...)` via `InteractionSource`

## Antes

```kotlin
@Composable
fun Teste(
    onOkCallback: () -> Unit,
    modifier: Modifier = Modifier,
) {
    var focus = false

    Card(
        modifier = modifier.onFocusEvent {
            focus = it.isFocused
        },
        onClick = onOkCallback,
    ) {
    }
}
```

Três problemas que passam batido na inspeção visual:

1. `Modifier.onFocusEvent` em `Card` **nunca dispara** — `Card` não é focusable
   por padrão (precisaria de `.focusable()` na chain), então `focus` continua
   `false` para sempre.
2. `var focus = false` (sem `remember { mutableStateOf(...) }`) reseta a cada
   recomposição — mesmo se o `onFocusEvent` disparasse, o valor seria perdido.
3. `focus` é dead code — nunca é lido em lugar nenhum, então toda a lógica de
   observação não tem efeito observável.

## Depois

```kotlin
@Composable
fun Teste(
    onOkCallback: () -> Unit,
    modifier: Modifier = Modifier,
    interactionSource: MutableInteractionSource = remember { MutableInteractionSource() },
) {
    LaunchedEffect(interactionSource) {
        interactionSource.interactions.collect { interaction ->
            // Press, Release, Focus, Unfocus, Drag — todos visíveis aqui
            when (interaction) {
                is PressInteraction.Press -> { /* feedback de "apertou" */ }
                is PressInteraction.Release -> { /* feedback de "soltou" */ }
                is FocusInteraction.Focus -> { /* navegou para cá por teclado */ }
                is FocusInteraction.Unfocus -> { /* saiu por teclado */ }
            }
        }
    }

    Card(
        onClick = onOkCallback,
        interactionSource = interactionSource,
        modifier = modifier,
    ) {
    }
}
```

## Por quê

- `InteractionSource` é a **API pública do Compose para observar estado de
  interação** (toque, foco, drag, hover). Cobre tudo que `onFocusEvent` cobre
  e mais, sem precisar de `Modifier.focusable()`.
- `remember { MutableInteractionSource() }` mantém a mesma instância entre
  recomposições (sem isso, a cada recomposição o `Card` recebe um
  `InteractionSource` novo e perde a capacidade de correlacionar eventos).
- `interactionSource` é recebido como **parâmetro hoisted** (com o
  `remember { ... }` só no valor default) — quem chama `Teste(...)` pode
  passar sua própria instância para customizar ripple/animação ou observar o
  mesmo estado de fora. Ver "Bônus: hoisting" abaixo para o caso em que isso
  falta.
- `LaunchedEffect(interactionSource)` é o ciclo de vida correto: inicia
  quando o composable entra em composição, cancela quando sai (a corrotina
  é cancelada automaticamente pelo `LaunchedEffect`).
- O bloco `when` fica aberto a extensões: drag, hover, gestures customizadas.
  Como aqui **dois eixos** são observados juntos (press e foco), a coleta
  manual é justificada — não existe um único `collectIsXAsState()` que cubra
  os dois ao mesmo tempo. Ver "Bônus: observação direta" abaixo para o caso
  em que só um eixo é observado (e um helper substitui tudo isso).

## Bônus: observação direta (`interaction-source-manual-collect`)

Quando o `collect` só distingue eventos de **um único eixo**, a corrotina
inteira (LaunchedEffect + when) pode virar uma linha declarativa.

```kotlin
// Antes — só quer saber "está pressionado agora", mas monta a coroutine inteira
@Composable
fun PressableCard(
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    interactionSource: MutableInteractionSource = remember { MutableInteractionSource() },
) {
    var pressed by remember { mutableStateOf(false) }

    LaunchedEffect(interactionSource) {
        interactionSource.interactions.collect { interaction ->
            when (interaction) {
                is PressInteraction.Press -> pressed = true
                is PressInteraction.Release -> pressed = false
                is PressInteraction.Cancel -> pressed = false
            }
        }
    }

    Card(onClick = onClick, interactionSource = interactionSource, modifier = modifier) {
        Text(if (pressed) "pressionado" else "solto")
    }
}

// Depois — collectIsPressedAsState() já resolve Press/Release/Cancel
@Composable
fun PressableCard(
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    interactionSource: MutableInteractionSource = remember { MutableInteractionSource() },
) {
    val pressed by interactionSource.collectIsPressedAsState()

    Card(onClick = onClick, interactionSource = interactionSource, modifier = modifier) {
        Text(if (pressed) "pressionado" else "solto")
    }
}
```

`collectIsFocusedAsState()`, `collectIsDraggedAsState()` e
`collectIsHoveredAsState()` seguem o mesmo princípio para os eixos de
foco, drag e hover, respectivamente.

## Bônus: hoisting (`interaction-source-not-hoisted`)

```kotlin
// Antes — MutableInteractionSource preso dentro do componente
@Composable
fun WrapperCard(onClick: () -> Unit, modifier: Modifier = Modifier) {
    val interactionSource = remember { MutableInteractionSource() }
    Card(onClick = onClick, interactionSource = interactionSource, modifier = modifier) { }
}

// Depois — hoisted, com o remember só no valor default
@Composable
fun WrapperCard(
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    interactionSource: MutableInteractionSource = remember { MutableInteractionSource() },
) {
    Card(onClick = onClick, interactionSource = interactionSource, modifier = modifier) { }
}
```

Sem o hoisting, quem chama `WrapperCard(...)` não tem como observar (ex.:
estilizar de forma diferente quando pressionado) nem testar o estado de
interação do `Card` de fora — a instância fica presa na composição interna.

## Bônus: stale closure em callback (`interaction-source-callback-not-stable`)

```kotlin
// Antes — onClick capturado pelo LaunchedEffect na primeira composição
@Composable
fun ClickCard(
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    interactionSource: MutableInteractionSource = remember { MutableInteractionSource() },
) {
    LaunchedEffect(interactionSource) {
        interactionSource.interactions.collect { interaction ->
            if (interaction is PressInteraction.Release) {
                onClick() // pode ser a lambda antiga se o pai recompôs com outra
            }
        }
    }

    Card(interactionSource = interactionSource, modifier = modifier) { }
}

// Depois — rememberUpdatedState garante que a chamada usa a lambda mais recente
@Composable
fun ClickCard(
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    interactionSource: MutableInteractionSource = remember { MutableInteractionSource() },
) {
    val currentOnClick by rememberUpdatedState(onClick)

    LaunchedEffect(interactionSource) {
        interactionSource.interactions.collect { interaction ->
            if (interaction is PressInteraction.Release) {
                currentOnClick()
            }
        }
    }

    Card(interactionSource = interactionSource, modifier = modifier) { }
}
```

Como `LaunchedEffect(interactionSource)` só reinicia quando `interactionSource`
muda (não quando `onClick` muda), a lambda capturada dentro dele pode ficar
desatualizada se o pai recompuser `ClickCard` com um novo `onClick` — a
alternativa a `rememberUpdatedState` seria incluir `onClick` nas keys do
`LaunchedEffect`, mas isso reinicia a coroutine (e perde eventos em trânsito)
a cada recomposição da lambda.

Note que este exemplo também dispara `interaction-source-manual-collect` (só
observa `PressInteraction.Release`, um único eixo) — os dois findings são
independentes e ambos legítimos aqui; ver "Bônus: observação direta" acima
para o fix desse segundo ponto.
