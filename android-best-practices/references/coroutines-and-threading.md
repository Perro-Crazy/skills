# Coroutines e threading

Checagens do scanner que caem neste tópico: `globalscope-launch-usage`,
`runblocking-outside-tests`, `viewmodel-manual-coroutinescope`,
`asynctask-subclass-deprecated`.

O fio condutor: concorrência estruturada (coroutines vinculadas a um escopo com ciclo de
vida conhecido) é o padrão recomendado pela documentação oficial de Android há vários
anos; as quatro checagens deste tópico sinalizam os desvios mais comuns desse padrão.

## `GlobalScope.launch`/`GlobalScope.async`

**Finding: `globalscope-launch-usage`.** `GlobalScope` inicia uma coroutine sem vínculo
com nenhum ciclo de vida do app — ela roda até completar (ou o processo morrer),
independente de a Activity/Fragment/ViewModel que a criou ainda existir. Isso causa dois
problemas: trabalho desperdiçado (a coroutine continua rodando depois que ninguém mais
precisa do resultado) e, pior, potenciais crashes ou comportamento incorreto se o
resultado for usado para atualizar uma UI já destruída.

- Fix: use um escopo estruturado — `viewModelScope` (dentro de `ViewModel`,
  cancelado automaticamente em `onCleared()`), `lifecycleScope` (dentro de
  Activity/Fragment, cancelado quando o `Lifecycle` correspondente é destruído), ou um
  `CoroutineScope` próprio, injetado e explicitamente cancelado quando o dono morre.
- **Mirrors**: detekt, ruleset `coroutines` (built-in, não precisa de plugin extra) —
  `GlobalCoroutineUsage`. Não executado neste ambiente (ver `scripts/README.md`).

## `runBlocking { ... }` fora de testes

**Finding: `runblocking-outside-tests`.** `runBlocking` bloqueia a thread chamadora até
a coroutine interna terminar — em testes isso é aceitável (a thread de teste bloquear é
o próprio propósito, permitir asserções síncronas sobre código suspenso). Fora de
testes, se a thread chamadora for a main thread — o caso comum dentro de código de
Activity/Fragment/ViewModel — bloqueá-la é exatamente o que coroutines existem para
evitar: a UI trava até a operação suspensa terminar.

- **Não dispara** para arquivos sob `/test/`, `/androidTest/` ou `/sharedTest/` no
  caminho (source sets padrão de teste do Gradle) — nesses, `runBlocking` é o padrão
  aceito para testar `suspend fun`.
- Fix: se o chamador já é uma função `suspend`, apenas remova `runBlocking` e faça a
  chamada direto (suspensão real, sem bloquear thread nenhuma); se o chamador não é
  `suspend` mas roda dentro de um escopo de coroutine, use `launch`/`async` no lugar de
  bloquear.
- **Mirrors**: sem id formal de Android Lint/detekt conhecido — checagem própria,
  baseada na guidance oficial de coroutines sobre bloqueio de thread.

## `CoroutineScope(...)` manual dentro de um `ViewModel`

**Finding: `viewmodel-manual-coroutinescope`** (severidade `info`). Dentro do corpo de
uma classe `ViewModel`/`AndroidViewModel`, uma construção `CoroutineScope(...)` manual em
vez de usar `viewModelScope` (fornecido por
`androidx.lifecycle:lifecycle-viewmodel-ktx`).

`viewModelScope` já é cancelado automaticamente em `onCleared()` — um escopo construído
manualmente precisa desse cancelamento sendo replicado à mão (tipicamente sobrescrevendo
`onCleared()` e chamando `scope.cancel()`), fácil de esquecer, o que deixa coroutines
rodando além da vida útil do ViewModel.

- Fix: substitua o `CoroutineScope(...)` manual por `viewModelScope` diretamente nas
  chamadas `.launch { ... }`.
- **Mirrors**: sem id formal de Android Lint/detekt — guidance oficial da biblioteca
  `lifecycle-viewmodel-ktx`.

## Subclasse de `AsyncTask`

**Finding: `asynctask-subclass-deprecated`** (severidade `info`). `AsyncTask` está
formalmente `@Deprecated` na API Android desde o nível 30 (Android 11) — o próprio
compilador Kotlin já emite um warning `DEPRECATION` nesse uso, então esta checagem só
reforça a recomendação de migração, não descobre algo que o compilador já não avisasse.

Duas armadilhas conhecidas motivaram a depreciação: vazamento de memória (uma subclasse
não estática retém implicitamente a Activity/Fragment que a criou, mesma classe de
problema que `handler-inner-class-leak`) e um modelo de execução (serial por padrão
dentro do mesmo `Executor`) que surpreende quem espera paralelismo real entre tasks.

- Fix: migre para coroutines — `viewModelScope.launch(Dispatchers.IO) { ... }` para
  trabalho enquanto a UI está viva, ou `WorkManager` para trabalho que precisa sobreviver
  ao processo/à Activity que o agendou.
- **Mirrors**: depreciação oficial da API Android (não é uma regra de linter externa,
  mas uma anotação `@Deprecated` real na própria plataforma).
