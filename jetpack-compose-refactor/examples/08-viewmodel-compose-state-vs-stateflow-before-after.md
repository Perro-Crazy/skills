# ViewModel expondo estado do Compose em vez de `StateFlow`

## Antes

```kotlin
class ProfileViewModel : ViewModel() {
    val name = mutableStateOf("")
    val avatarUrl = mutableStateOf("")
    val isLoading = mutableStateOf(false)

    fun load(userId: String) {
        isLoading.value = true
        viewModelScope.launch {
            val profile = repository.fetchProfile(userId)
            name.value = profile.name
            avatarUrl.value = profile.avatarUrl
            isLoading.value = false
        }
    }
}
```

Dois problemas independentes: as três properties usam `State`/`MutableState` do
runtime do Compose diretamente (acoplando o ViewModel ao Compose e dificultando testar
fora dele), e são três streams separados em vez de um único `UiState` — quem consome
precisa combinar os três manualmente para saber quando a tela está pronta para exibir.

## Depois

```kotlin
data class ProfileUiState(
    val name: String = "",
    val avatarUrl: String = "",
    val isLoading: Boolean = false,
)

class ProfileViewModel : ViewModel() {
    private val _uiState = MutableStateFlow(ProfileUiState())
    val uiState: StateFlow<ProfileUiState> = _uiState.asStateFlow()

    fun load(userId: String) {
        _uiState.update { it.copy(isLoading = true) }
        viewModelScope.launch {
            val profile = repository.fetchProfile(userId)
            _uiState.update {
                it.copy(name = profile.name, avatarUrl = profile.avatarUrl, isLoading = false)
            }
        }
    }
}
```

No composable de tela:

```kotlin
@Composable
fun ProfileScreen(viewModel: ProfileViewModel = hiltViewModel()) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    ProfileHeader(uiState = uiState)
}
```

## Por quê

`MutableStateFlow`/`StateFlow` mantêm o ViewModel testável em Kotlin puro (sem
precisar de uma composição ativa para ler o estado em um teste de unidade) e
desacoplado do runtime do Compose. Consolidar as três properties num único
`data class ProfileUiState` dá à tela uma única fonte de verdade — não existe mais um
estado intermediário em que `name` já mudou mas `isLoading` ainda não, porque a
atualização é sempre atômica via `.copy(...)`.
