# ViewModel retendo Context e Activity instanciando cliente de rede

## Antes

```kotlin
class ProfileViewModel(private val context: Context) : ViewModel() {
    private val client = OkHttpClient()
    private val api = Retrofit.Builder()
        .baseUrl("https://api.exemplo.com")
        .client(client)
        .build()
        .create(ProfileApi::class.java)

    fun load() {
        viewModelScope.launch {
            val profile = api.fetchProfile()
            Toast.makeText(context, "Perfil carregado", Toast.LENGTH_SHORT).show()
            _state.value = profile
        }
    }
}

class ProfileActivity : AppCompatActivity() {
    private val db = Room.databaseBuilder(this, AppDatabase::class.java, "app.db").build()
    private val viewModel = ProfileViewModel(this)
}
```

## Depois

```kotlin
// ProfileRepository.kt — camada de dados, injetada, não instanciada pela UI
class ProfileRepository(private val api: ProfileApi, private val db: AppDatabase) {
    suspend fun fetchProfile(): Profile = api.fetchProfile()
}

// ProfileViewModel.kt — sem Context, sem cliente de rede/DB direto
class ProfileViewModel(private val repository: ProfileRepository) : ViewModel() {
    private val _state = MutableStateFlow<Profile?>(null)
    val state: StateFlow<Profile?> = _state

    private val _events = MutableSharedFlow<ProfileEvent>()
    val events: SharedFlow<ProfileEvent> = _events

    fun load() {
        viewModelScope.launch {
            val profile = repository.fetchProfile()
            _events.emit(ProfileEvent.ShowMessage("Perfil carregado"))
            _state.value = profile
        }
    }
}

// ProfileActivity.kt — só observa o ViewModel, não constrói dependência nenhuma
class ProfileActivity : AppCompatActivity() {
    private val viewModel: ProfileViewModel by viewModels { AppContainer.profileViewModelFactory }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        lifecycleScope.launch {
            viewModel.events.collect { event ->
                when (event) {
                    is ProfileEvent.ShowMessage -> Toast.makeText(this@ProfileActivity, event.text, Toast.LENGTH_SHORT).show()
                }
            }
        }
    }
}
```

## Por quê

`ProfileViewModel` deixou de receber um `Context` e de construir `OkHttpClient`/
`Retrofit` diretamente — passou a depender só de `ProfileRepository`, uma abstração da
camada de dados. Para notificar a UI ("Perfil carregado"), em vez de chamar `Toast`
diretamente (que exigiria o `Context` retido), o ViewModel emite um evento
(`ProfileEvent.ShowMessage`) via `SharedFlow`, que a Activity observa e reage — o fluxo
de dependência passou a ser só UI → ViewModel, nunca o contrário. `ProfileActivity` não
constrói mais `Room.databaseBuilder(...)` nem passa `this` para o ViewModel; a
composição de dependências (`AppContainer`, aqui simplificado — poderia ser Hilt/Koin)
fica centralizada em um único lugar, testável isoladamente.
