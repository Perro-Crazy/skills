# GlobalScope, runBlocking e escopo manual em ViewModel

## Antes

```kotlin
class SyncViewModel : ViewModel() {
    private val scope = CoroutineScope(Dispatchers.IO)

    fun syncNow() {
        GlobalScope.launch {
            val result = runBlocking { repository.fetchLatest() }
            _state.value = result
        }
    }

    fun scheduleBackground() {
        scope.launch {
            repository.syncPending()
        }
    }
}
```

## Depois

```kotlin
class SyncViewModel : ViewModel() {
    fun syncNow() {
        viewModelScope.launch {
            val result = repository.fetchLatest()  // já é suspend — sem runBlocking
            _state.value = result
        }
    }

    fun scheduleBackground() {
        viewModelScope.launch {
            repository.syncPending()
        }
    }
}
```

## Por quê

`GlobalScope.launch` foi substituído por `viewModelScope.launch` — a coroutine agora é
cancelada automaticamente em `onCleared()`, em vez de sobreviver indefinidamente ao
ViewModel. O `runBlocking` interno desapareceu porque `repository.fetchLatest()` já é
uma função `suspend`: bloquear a thread pra esperar por outra coroutine dentro de uma
coroutine já era redundante, além de já estar comprometendo qualquer ganho de
concorrência real. O `CoroutineScope(Dispatchers.IO)` manual do campo `scope` também
saiu — `viewModelScope` já cobre o caso de uso, sem precisar replicar cancelamento
manualmente em `onCleared()`.
