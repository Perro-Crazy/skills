# Manifest e segredos hardcoded

## Antes

```xml
<!-- AndroidManifest.xml -->
<application
    android:allowBackup="true"
    android:debuggable="true"
    android:usesCleartextTraffic="true"
    android:label="@string/app_name">

    <receiver android:name=".SyncStatusReceiver" android:exported="true" />

</application>
```

```kotlin
// ApiClient.kt
private const val apiSecretKey: String = "sk_live_51H8x9Kabcdef0123456789"

class ApiClient {
    fun baseUrl() = "http://api.exemplo.com/v1"
}
```

## Depois

```xml
<!-- AndroidManifest.xml (src/main) -->
<application
    android:allowBackup="false"
    android:label="@string/app_name">

    <receiver
        android:name=".SyncStatusReceiver"
        android:exported="true"
        android:permission="com.exemplo.app.permission.SYNC_STATUS" />

</application>
```

```xml
<!-- AndroidManifest.xml (src/debug, override só para o build type debug) -->
<application android:debuggable="true" />
```

```kotlin
// ApiClient.kt — a chave vem de BuildConfig, gerada a partir de local.properties
// (fora do controle de versão), não mais de um literal no código-fonte.
class ApiClient {
    private val apiSecretKey: String = BuildConfig.API_SECRET_KEY
    fun baseUrl() = "https://api.exemplo.com/v1"
}
```

## Por quê

`allowBackup="false"` evita que dados sensíveis (se este app os tiver) vazem via backup
extraído; `debuggable="true"` só existe no manifest do build type debug, nunca no
principal, então não há risco de vazar para um build de release; o `receiver` exportado
ganhou uma `permission` restringindo quem pode enviar broadcasts pra ele; o segredo saiu
do código-fonte compilado (onde seria trivial de extrair via descompilação) para
`BuildConfig`, alimentado por `local.properties`; e o endpoint passou a usar `https://`.
Nenhuma dessas mudanças exigiu adicionar dependência nova — só reorganizar configuração
já suportada pelo Android Gradle Plugin.
