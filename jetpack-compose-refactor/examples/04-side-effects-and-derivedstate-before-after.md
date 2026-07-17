# Side-effects com key incorreta e `derivedStateOf`

## Antes

```kotlin
@Composable
fun UserGreeting(userId: String, modifier: Modifier = Modifier) {
    var greeting by remember { mutableStateOf("") }

    LaunchedEffect(Unit) {
        greeting = fetchGreeting(userId)
    }

    Text(text = greeting, modifier = modifier)
}
```

`LaunchedEffect(Unit)` roda só na primeira composição — se `userId` mudar depois (o
mesmo `UserGreeting` sendo reusado para outro usuário, ex.: numa lista com `key`), o
efeito não relança e a saudação antiga permanece na tela, associada ao usuário errado.

## Depois

```kotlin
@Composable
fun UserGreeting(userId: String, modifier: Modifier = Modifier) {
    var greeting by remember { mutableStateOf("") }

    LaunchedEffect(userId) {
        greeting = fetchGreeting(userId)
    }

    Text(text = greeting, modifier = modifier)
}
```

## Por quê

A key de `LaunchedEffect` deve incluir tudo que o corpo do efeito lê e que pode mudar
ao longo da vida do composable. Ao trocar a key de `Unit` para `userId`, o efeito é
cancelado e relançado automaticamente sempre que `userId` mudar, buscando a saudação
correta para o novo valor.

---

## Bônus: `derivedStateOf` para reduzir recomposição

```kotlin
// Antes: recompõe a cada pixel de scroll, mesmo quando o botão não muda de estado
val showBackToTop = listState.firstVisibleItemIndex > 0

// Depois: só recompõe quando o valor booleano de fato muda
val showBackToTop by remember {
    derivedStateOf { listState.firstVisibleItemIndex > 0 }
}
```

`firstVisibleItemIndex` muda a cada scroll, mas `showBackToTop` só precisa mudar
quando cruza o threshold (de `0` para `1`, ou de volta). Sem `derivedStateOf`, tudo que
lê `showBackToTop` recompõe a cada evento de scroll; com `derivedStateOf`, só recompõe
quando o resultado derivado realmente muda.

---

## Bônus: `DisposableEffect` sem `onDispose`

```kotlin
// Antes — observer registrado, nunca removido
@Composable
fun ObserveLifecycle(lifecycleOwner: LifecycleOwner) {
    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event -> /* ... */ }
        lifecycleOwner.lifecycle.addObserver(observer)
    }
}

// Depois
@Composable
fun ObserveLifecycle(lifecycleOwner: LifecycleOwner) {
    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event -> /* ... */ }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }
}
```

Sem `onDispose`, o `observer` registrado continua vivo mesmo depois que
`ObserveLifecycle` sai de composição (ou quando o efeito é relançado por uma troca de
`lifecycleOwner`) — um vazamento de observer que se acumula a cada entrada/saída de
composição.
