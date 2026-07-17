# Estabilidade e objetos que exigem `remember`

## Antes

```kotlin
val Spacing = staticCompositionLocalOf { 8.dp }        // sem o prefixo Local

@Immutable
data class Filter(var query: String, var onlyFavorites: Boolean)  // @Immutable + var

@Composable
fun SearchBar(
    state: MutableState<String>,                        // estado mutável como parâmetro
    createdAt: java.util.Date,                           // tipo externo instável
    filter: Filter,                                      // classe com var
) {
    val interaction = MutableInteractionSource()         // criado sem remember
    OutlinedTextField(
        value = state.value,
        onValueChange = { state.value = it },
        interactionSource = interaction,
    )
}
```

## Depois

```kotlin
val LocalSpacing = staticCompositionLocalOf { 8.dp }

@Immutable
data class Filter(val query: String, val onlyFavorites: Boolean)  // val -> realmente imutável

@Composable
fun SearchBar(
    query: String,                                       // value + callback (stateless)
    onQueryChange: (String) -> Unit,
    createdAtLabel: String,                              // já formatado, tipo estável
    filter: Filter,
    modifier: Modifier = Modifier,
) {
    val interaction = remember { MutableInteractionSource() }
    OutlinedTextField(
        value = query,
        onValueChange = onQueryChange,
        interactionSource = interaction,
        modifier = modifier,
    )
}
```

## Por quê

`LocalSpacing` segue a convenção de prefixo `Local`. Trocar `var` por `val` em `Filter`
faz a classe realmente cumprir o contrato `@Immutable` (senão o Compose pode pular
recomposições confiando numa promessa falsa) e a torna estável como parâmetro. O padrão
`value` + `onValueChange` remove a posse dividida do estado (`MutableState` como
parâmetro). Passar `createdAtLabel: String` em vez de `java.util.Date` evita um tipo de
biblioteca externa instável. E `remember { MutableInteractionSource() }` preserva o
objeto entre recomposições em vez de recriá-lo a cada uma.
