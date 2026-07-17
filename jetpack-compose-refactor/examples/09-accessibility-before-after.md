# Acessibilidade

## Antes

```kotlin
@Composable
fun ProfileRow(user: User, onEdit: () -> Unit, modifier: Modifier = Modifier) {
    Row(modifier = modifier) {
        Image(painter = user.avatar, contentDescription = "")          // anunciado como vazio
        Text(user.name)
        Box(modifier = Modifier.size(24.dp).clickable { onEdit() }) {   // alvo de 24.dp, sem role
            Icon(Icons.Default.Edit, contentDescription = null)         // null num alvo clicável
        }
    }
}
```

Três problemas de acessibilidade: a `Image` é anunciada como um elemento vazio pelo
TalkBack (`contentDescription = ""`); a área de toque tem 24.dp (abaixo do mínimo de
48.dp) e não declara papel semântico; e o `Icon` clicável usa `contentDescription = null`
(que o marca como decorativo, sem rótulo para a ação).

## Depois

```kotlin
@Composable
fun ProfileRow(user: User, onEdit: () -> Unit, modifier: Modifier = Modifier) {
    Row(modifier = modifier) {
        Image(painter = user.avatar, contentDescription = "Foto de ${user.name}")
        Text(user.name)
        Box(
            modifier = Modifier
                .minimumInteractiveComponentSize()
                .clickable(role = Role.Button, onClickLabel = "Editar perfil") { onEdit() }
        ) {
            Icon(Icons.Default.Edit, contentDescription = null)  // decorativo: o rótulo está no clickable
        }
    }
}
```

## Por quê

`contentDescription` informativo faz o TalkBack anunciar o que a imagem representa;
`minimumInteractiveComponentSize()` garante os 48.dp de área de toque (o ícone visual
continua com 24.dp); e `role = Role.Button` + `onClickLabel` dão ao leitor de tela o
papel e a ação — com o rótulo no `clickable`, o `Icon` interno pode legitimamente ser
`contentDescription = null` (decorativo), já que a semântica está no container clicável.
