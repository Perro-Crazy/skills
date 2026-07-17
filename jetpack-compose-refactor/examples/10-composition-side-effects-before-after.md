# Trabalho assíncrono e Flow na composição

## Antes

```kotlin
@Composable
fun Feed(viewModel: FeedViewModel, scope: CoroutineScope) {
    scope.launch { viewModel.refresh() }                          // corrotina na composição
    val items by viewModel.itemsFlow
        .map { it.sortedBy(Item::date) }                          // operador de Flow na composição
        .collectAsState(emptyList())                              // não é lifecycle-aware
    val selected = remember { mutableStateOf(mutableListOf<Int>()) }  // coleção mutável em State

    LazyColumn {
        items(items, key = { it.id }) { ItemRow(it) }
    }
}
```

Quatro problemas: `scope.launch { }` roda a cada recomposição; `.map { }` recria o
`Flow` a cada recomposição; `collectAsState()` continua coletando com o app em
background; e `mutableStateOf(mutableListOf())` não notifica o Compose quando a lista é
mutada no lugar.

## Depois

```kotlin
@Composable
fun Feed(viewModel: FeedViewModel, modifier: Modifier = Modifier) {
    LaunchedEffect(Unit) { viewModel.refresh() }                  // atrelado à composição
    val items by viewModel.sortedItems                           // ordenação feita no ViewModel
        .collectAsStateWithLifecycle()                           // pausa fora do lifecycle ativo
    val selected = remember { mutableStateListOf<Int>() }        // lista observável

    LazyColumn(modifier = modifier) {
        items(items, key = { it.id }) { ItemRow(it) }
    }
}
```

## Por quê

`LaunchedEffect(Unit)` executa o refresh uma vez por entrada na composição, não a cada
recomposição. A transformação `.sortedBy(...)` vive no ViewModel (exposta como
`sortedItems: StateFlow`), então não é refeita na UI. `collectAsStateWithLifecycle()`
respeita o ciclo de vida (economiza recursos em background). E `mutableStateListOf`
é uma lista observável — `.add()`/`.remove()` disparam recomposição corretamente.

> Nota multiplataforma: em `commonMain` (KMP), `collectAsStateWithLifecycle` não existe
> (é Android-only) — ali `collectAsState()` é o correto e não deve ser trocado.
