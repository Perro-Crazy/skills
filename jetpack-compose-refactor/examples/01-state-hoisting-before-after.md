# Hoisting de estado

## Antes

```kotlin
@Composable
fun SearchBar(modifier: Modifier = Modifier) {
    var query by remember { mutableStateOf("") }

    TextField(
        value = query,
        onValueChange = { query = it },
        modifier = modifier,
    )
}
```

## Depois

```kotlin
@Composable
fun SearchBar(
    query: String,
    onQueryChange: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    TextField(
        value = query,
        onValueChange = onQueryChange,
        modifier = modifier,
    )
}

// no chamador (composable de tela, ou onde o estado precisa realmente viver):
var query by remember { mutableStateOf("") }
SearchBar(query = query, onQueryChange = { query = it })
```

## Por quê

`query` no "antes" é estado de UI que só existe dentro de `SearchBar` — quem chama não
tem acesso a ele, não consegue observá-lo, resetá-lo, ou sincronizá-lo com outra fonte
(ex.: um `ViewModel` que também precisa saber o termo de busca atual para disparar uma
chamada de rede). Hoisting move o estado para fora, tornando `SearchBar` um componente
stateless puro: mais fácil de testar (basta passar valores), de dar preview (com
qualquer valor fixo de `query`), e de reutilizar em contextos onde o estado já vem de
outro lugar (ex.: um `ViewModel`, como em
`05-viewmodel-forwarding-before-after.md`).
