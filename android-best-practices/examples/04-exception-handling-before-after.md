# Tratamento de exceção e asserção de não-nulo

## Antes

```kotlin
fun loadUserName(prefs: SharedPreferences): String {
    return prefs.getString("user_name", null)!!
}

fun syncData(repository: SyncRepository) {
    try {
        repository.push()
    } catch (e: Exception) {
    }

    try {
        repository.pull()
    } catch (e: Exception) {
        showErrorToast()
    }

    try {
        repository.cleanup()
    } catch (e: IOException) {
        e.printStackTrace()
    }
}
```

## Depois

```kotlin
fun loadUserName(prefs: SharedPreferences): String {
    return prefs.getString("user_name", null)
        ?: error("user_name deveria ter sido gravado no onboarding — invariante quebrada")
}

fun syncData(repository: SyncRepository) {
    try {
        repository.push()
    } catch (e: IOException) {
        Log.w(TAG, "push falhou, será tentado de novo na próxima sincronização", e)
    }

    try {
        repository.pull()
    } catch (e: IOException) {
        Log.e(TAG, "pull falhou", e)
        showErrorToast()
    }

    try {
        repository.cleanup()
    } catch (e: IOException) {
        Log.w(TAG, "cleanup falhou, não é crítico", e)
    }
}
```

## Por quê

O `!!` virou um `?:` com `error(...)` — se a invariante ("user_name sempre existe depois
do onboarding") for violada, a mensagem de erro agora explica o porquê em vez de um NPE
genérico apontando só para a linha. Os três `catch (e: Exception)` genéricos viraram
`catch (e: IOException)` — o tipo específico que `push`/`pull`/`cleanup` de fato lançam
em uma falha de rede/IO esperada, deixando qualquer outro tipo de exceção (um bug de
programação) propagar em vez de ser engolido. O bloco vazio e o `printStackTrace()`
viraram chamadas a `Log.w`/`Log.e` com uma mensagem contextual — agora um problema real
aparece no logcat (e em qualquer ferramenta de crash/log reporting conectada) em vez de
desaparecer silenciosamente ou ir para um stderr que ninguém observa num dispositivo
Android real.
