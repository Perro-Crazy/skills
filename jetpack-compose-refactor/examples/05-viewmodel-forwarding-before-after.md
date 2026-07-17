# Forwarding de ViewModel

## Antes

```kotlin
@Composable
fun ProfileScreen(viewModel: ProfileViewModel = hiltViewModel()) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    ProfileHeader(viewModel = viewModel)
}

@Composable
fun ProfileHeader(viewModel: ProfileViewModel) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    Text(state.userName)
    Button(onClick = { viewModel.onEditClick() }) {
        Text("Editar")
    }
}
```

`ProfileHeader` não é a tela — é um componente interno — mas recebe o `ViewModel`
inteiro e coleta o state de novo por conta própria. Isso o torna impossível de testar
sem montar um `ProfileViewModel` real, impossível de dar `@Preview` sem mockar o
ViewModel, e acopla esse componente à escolha de DI/arquitetura do app.

## Depois

```kotlin
@Composable
fun ProfileScreen(viewModel: ProfileViewModel = hiltViewModel()) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    ProfileHeader(
        userName = state.userName,
        onEditClick = viewModel::onEditClick,
    )
}

@Composable
fun ProfileHeader(userName: String, onEditClick: () -> Unit, modifier: Modifier = Modifier) {
    Column(modifier = modifier) {
        Text(userName)
        Button(onClick = onEditClick) {
            Text("Editar")
        }
    }
}
```

## Por quê

Só `ProfileScreen` (a tela, ligada ao destino de navegação) adquire o `ViewModel` e
coleta o estado. `ProfileHeader` vira um composable puramente stateless: recebe os
dados já prontos (`userName`) e um callback (`onEditClick`) — pode ser testado com
qualquer string, ter `@Preview` sem nenhum mock, e ser reaproveitado em outra tela que
tenha uma fonte de dados diferente.
