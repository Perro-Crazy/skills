# Naming de `@Preview` e `key` em listas preguiçosas

## Antes

```kotlin
@Preview
@Composable
fun demo() {
    UserCard(name = "Ana")
}

@Composable
fun UserList(users: List<User>, modifier: Modifier = Modifier) {
    LazyColumn(modifier = modifier) {
        items(users) { user ->
            UserCard(name = user.name)
        }
    }
}
```

Dois problemas: a função de preview é pública, com nome que não segue a convenção
(`demo` em vez de algo terminado em `Preview`); e `items(users) { ... }` não passa
`key`, então reordenar/remover usuários da lista confunde a identidade dos itens (perda
de estado por item, animações quebradas).

## Depois

```kotlin
@Preview
@Composable
private fun UserCardPreview() {
    UserCard(name = "Ana")
}

@Composable
fun UserList(users: List<User>, modifier: Modifier = Modifier) {
    LazyColumn(modifier = modifier) {
        items(users, key = { it.id }) { user ->
            UserCard(name = user.name)
        }
    }
}
```

## Por quê

`private fun UserCardPreview()` deixa claro, só pelo nome e modificador de
visibilidade, que essa função é um artefato de tooling para a IDE/ferramentas de
preview, não parte da API pública do módulo. Passar `key = { it.id }` (um identificador
estável do usuário, não o índice da lista) garante que o Compose reconhece
corretamente cada item entre recomposições, mesmo que a lista seja reordenada ou tenha
itens removidos no meio.

---

## Bônus: emitir UI e devolver valor na mesma função

```kotlin
// Antes
@Composable
fun UserBadge(user: User): Boolean {
    Text(user.name)
    return user.isOnline
}

// Depois — separar emissão de UI da lógica que devolve valor
@Composable
fun UserBadge(user: User) {
    Text(user.name)
}

fun isUserOnline(user: User): Boolean = user.isOnline
```

`UserBadge` emitindo `Text` e devolvendo `Boolean` ao mesmo tempo torna a função
confusa de chamar (quem usa `UserBadge(user)` só para desenhar a UI precisa descartar
o retorno) e impossível de testar a lógica de `isOnline` sem montar uma composição.

---

## Bônus: naming do slot de conteúdo

```kotlin
// Antes
@Composable
fun Panel(title: String, modifier: Modifier = Modifier, body: @Composable () -> Unit) {
    Column(modifier) {
        Text(title)
        body()
    }
}

// Depois
@Composable
fun Panel(title: String, modifier: Modifier = Modifier, content: @Composable () -> Unit) {
    Column(modifier) {
        Text(title)
        content()
    }
}
```

`content` é o nome usado consistentemente pelos componentes do Material/Foundation
para o slot de conteúdo principal — seguir a mesma convenção deixa a assinatura mais
previsível para quem já conhece as APIs padrão do Compose.

---

## Bônus: `Modifier` não hoisted no lambda de item

```kotlin
// Antes — Modifier reconstruído a cada item, sem depender do item
@Composable
fun ProductRows(products: ImmutableList<Product>, modifier: Modifier = Modifier) {
    LazyColumn(modifier = modifier) {
        items(products, key = { it.id }) { product ->
            Row(modifier = Modifier.fillMaxWidth().padding(16.dp)) {
                Text(product.name)
            }
        }
    }
}

// Depois
@Composable
fun ProductRows(products: ImmutableList<Product>, modifier: Modifier = Modifier) {
    val rowModifier = Modifier.fillMaxWidth().padding(16.dp)
    LazyColumn(modifier = modifier) {
        items(products, key = { it.id }) { product ->
            Row(modifier = rowModifier) {
                Text(product.name)
            }
        }
    }
}
```

A cadeia `Modifier.fillMaxWidth().padding(16.dp)` é idêntica em todo item — não
depende de `product` — então recriá-la a cada item recomposto é trabalho
desnecessário. Declarar `rowModifier` uma única vez fora do lambda de item evita essa
recriação repetida.
