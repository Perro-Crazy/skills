# Coleções instáveis e `remember` ausente

## Antes

```kotlin
@Composable
fun TagList(tags: List<String>, modifier: Modifier = Modifier) {
    val expanded = mutableStateOf(false)

    Column(modifier = modifier) {
        tags.forEach { tag ->
            Text(tag)
        }
        Button(onClick = { expanded.value = !expanded.value }) {
            Text(if (expanded.value) "Recolher" else "Expandir")
        }
    }
}
```

Dois problemas independentes aqui: `tags: List<String>` é um tipo instável (quebra
skippability), e `expanded` é recriado do zero a cada recomposição porque não está
dentro de `remember { }` — o botão nunca vai de fato alternar de estado de forma
persistente entre recomposições.

## Depois

```kotlin
@Composable
fun TagList(tags: ImmutableList<String>, modifier: Modifier = Modifier) {
    val expanded = remember { mutableStateOf(false) }

    Column(modifier = modifier) {
        tags.forEach { tag ->
            Text(tag)
        }
        Button(onClick = { expanded.value = !expanded.value }) {
            Text(if (expanded.value) "Recolher" else "Expandir")
        }
    }
}

// no chamador:
TagList(tags = listOf("kotlin", "compose", "android").toImmutableList())
```

## Por quê

`ImmutableList<String>` (de `kotlinx.collections.immutable`) é reconhecido pelo
compilador do Compose como estável, permitindo que `TagList` seja pulado em
recomposições onde `tags` não mudou de verdade. `remember { mutableStateOf(false) }`
garante que `expanded` sobrevive a recomposições — sem isso, o valor volta para `false`
toda vez que qualquer coisa acima recompõe, mesmo sem o usuário ter clicado em nada.

Se adicionar `kotlinx-collections-immutable` ao projeto não for uma opção imediata
(nova dependência precisa de aprovação do time), a alternativa é envolver `tags` num
data class anotado `@Immutable` que contenha a lista internamente — resolve a
instabilidade sem precisar da biblioteca externa.
