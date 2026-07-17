# Forma de API, slots e Material 2

## `Scaffold` que ignora o padding

```kotlin
// Antes — conteúdo fica atrás da topBar/bottomBar
@Composable
fun HomeScreen() {
    Scaffold(topBar = { TopAppBar(title = { Text("Início") }) }) {
        LazyColumn { items(feed) { PostRow(it) } }
    }
}

// Depois
@Composable
fun HomeScreen() {
    Scaffold(topBar = { TopAppBar(title = { Text("Início") }) }) { innerPadding ->
        LazyColumn(contentPadding = innerPadding) { items(feed) { PostRow(it) } }
    }
}
```

O `Scaffold` entrega um `PaddingValues` com o espaço ocupado pelas barras; sem aplicá-lo
(aqui via `contentPadding`), a primeira linha da lista fica escondida atrás da `topBar`.

## `AnimatedContent` que ignora o `targetState`

```kotlin
// Antes — usa a variável externa, renderiza o estado errado na transição
AnimatedContent(targetState = page) {
    PageContent(page)
}

// Depois — usa o parâmetro recebido pelo lambda
AnimatedContent(targetState = page) { current ->
    PageContent(current)
}
```

## Callback de evento como trailing lambda

```kotlin
// Antes — onClick por último (depois do modifier) parece um slot de conteúdo no call site
@Composable
fun TagChip(label: String, modifier: Modifier = Modifier, onClick: () -> Unit) { ... }

// Depois — evento junto dos obrigatórios, antes do modifier
@Composable
fun TagChip(label: String, onClick: () -> Unit, modifier: Modifier = Modifier) { ... }
```

## Naming de annotation classes

```kotlin
// Antes
@Preview(name = "Telefone")
@Preview(name = "Tablet")
annotation class ScreenSizes          // deveria começar com "Preview"

// Depois
@Preview(name = "Telefone")
@Preview(name = "Tablet")
annotation class PreviewScreenSizes
```

## Material 2 num projeto Material 3

```kotlin
// Antes
import androidx.compose.material.Button   // Material 2
import androidx.compose.material3.Text    // Material 3 — misturando design systems

// Depois
import androidx.compose.material3.Button
import androidx.compose.material3.Text
```

Misturar `androidx.compose.material` (M2) e `androidx.compose.material3` (M3) no mesmo
código gera inconsistência de tema/estilo. Prefira o equivalente em `material3`. Se a
migração ainda não é viável, é uma decisão de projeto — não troque os imports sem
confirmar (os subpacotes `material.icons`/`material.ripple` são compartilhados e não
contam como uso de Material 2).
