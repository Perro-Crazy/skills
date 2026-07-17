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
