# Escrita "para trás" em estado (loop de recomposição)

## Antes

```kotlin
@Composable
fun Counter() {
    var count by remember { mutableIntStateOf(0) }
    Text("Cliques: $count")
    count++
}
```

`count` é lido em `Text("Cliques: $count")` e escrito de novo logo em seguida
(`count++`), fora de qualquer callback — ou seja, toda vez que `Counter` recompõe, ele
mesmo dispara a próxima recomposição, gerando um loop infinito sem nenhuma interação
do usuário.

## Depois

```kotlin
@Composable
fun Counter() {
    var count by remember { mutableIntStateOf(0) }
    Text("Cliques: $count")
    Button(onClick = { count++ }) {
        Text("Incrementar")
    }
}
```

## Por quê

Mover `count++` para dentro de `onClick` faz a escrita acontecer só em resposta a um
evento real do usuário, não a cada execução do corpo do composable. A leitura
(`Text("Cliques: $count")`) continua fora do callback — é normal e esperado que o
corpo leia o estado a cada recomposição; o problema é especificamente escrever de
volta no mesmo nível em que já foi lido.
