# Tratamento de exceção e null-safety

Checagens do scanner que caem neste tópico: `not-null-assertion-operator`,
`empty-catch-block`, `generic-exception-caught`, `swallowed-exception`,
`printstacktrace-usage`.

Diferente dos outros tópicos deste skill, estas cinco checagens não são específicas de
Android — são práticas gerais de Kotlin que o detekt já cobre nos seus rulesets padrão
(`potential-bugs`/`empty-blocks`/`exceptions`, todos built-in, sem plugin extra). Elas
entram neste skill porque a combinação "exceção engolida silenciosamente" +
"crash reporting ausente" é uma causa comum de bugs de produção difíceis de
diagnosticar especificamente em apps Android (sem um terminal para observar stdout,
diferente de um servidor).

## Operador `!!`

**Finding: `not-null-assertion-operator`** (severidade `info`). `!!` converte um valor
potencialmente nulo em uma `NullPointerException` explícita caso ele seja nulo em tempo
de execução — descarta o benefício do null-safety do Kotlin exatamente no ponto de uso,
trocando um erro de compilação (se o tipo não fosse nullable) por um crash em runtime.

- Fix: `?.let { }` quando a ausência do valor é um caminho válido a ignorar; o operador
  Elvis `?: fallback` quando há um valor default razoável; `checkNotNull(x) { "mensagem
  explicando por quê este valor não deveria ser nulo aqui" }` quando a não-nulidade é
  uma invariante conhecida (produz uma mensagem de erro útil em vez de um NPE genérico
  sem contexto).
- **Limitação textual**: o scanner não distingue uma ocorrência de `!!` dentro de uma
  string literal/comentário de uma ocorrência real de código — raro na prática, mas
  confirme antes de aplicar em massa.
- **Mirrors**: detekt, ruleset `potential-bugs` (built-in) — `UnsafeCallOnNullableType`.
  Não executado neste ambiente (ver `scripts/README.md`).

## Bloco `catch` vazio

**Finding: `empty-catch-block`.** Um `catch (e: Tipo) { }` sem nenhum código no corpo —
a exceção é descartada silenciosamente, o que costuma esconder um bug real (a operação
falhou e ninguém sabe) em vez de tratá-lo.

- Fix: se ignorar for realmente intencional, deixe um comentário explicando por quê
  (`// esperado quando X, seguro ignorar`) — um bloco vazio comentado é indistinguível de
  "esqueci de tratar isso" para quem lê depois.
- **Mirrors**: detekt, ruleset `empty-blocks` (built-in) — `EmptyCatchBlock`. Não
  executado neste ambiente.

## Exceção capturada e nunca referenciada (`swallowed-exception`)

**Finding: `swallowed-exception`.** Um `catch (e: Tipo) { ... }` com corpo não-vazio,
mas que nunca referencia a variável da exceção capturada (`e`, no exemplo) em lugar
nenhum do corpo. Diferente de `empty-catch-block`, aqui o bloco *faz* algo (ex.: mostra
um fallback na UI) — só não usa a informação da exceção real para logar, decidir o
comportamento, ou relançar.

- Fix: ao menos logue a exceção (`Log.e(TAG, "mensagem", e)`) antes de seguir com
  qualquer fallback — sem isso, quando o comportamento de fallback aparecer em produção,
  não há como saber qual foi a causa raiz real.
- **Mirrors**: detekt, ruleset `exceptions` (built-in) — `SwallowedException`. Não
  executado neste ambiente.

## Exceção genérica demais capturada

**Finding: `generic-exception-caught`** (severidade `info`). Um `catch` para `Exception`,
`Throwable` ou `RuntimeException` — tipos genéricos demais que engolem junto qualquer
subclasse inesperada, incluindo erros de **programação** (`IllegalStateException`,
`NullPointerException`, `ClassCastException`) que provavelmente deveriam propagar e ser
corrigidos no código, não tratados como uma falha de runtime recuperável igual a, por
exemplo, uma `IOException` de rede.

- Fix: capture o(s) tipo(s) específico(s) que o bloco realmente sabe tratar
  (`IOException`, `SocketTimeoutException` etc.); se múltiplos tipos precisam do mesmo
  tratamento, `catch (e: IOException | SerializationException)` (multi-catch, Kotlin
  2.0+) ou blocos separados.
- **Mirrors**: detekt, ruleset `exceptions` (built-in) — `TooGenericExceptionCaught`.
  Não executado neste ambiente.

## `.printStackTrace()`

**Finding: `printstacktrace-usage`** (severidade `info`). `.printStackTrace()` escreve o
stack trace em stderr — em um dispositivo Android real, isso não vai para lugar nenhum
observável: não aparece no logcat com tag/nível filtráveis, e um build de release não
tem ninguém monitorando stderr do processo.

- Fix: `Log.e(TAG, "mensagem descrevendo o contexto", exception)` (integra com logcat e
  com qualquer ferramenta de crash reporting configurada, ex.: Crashlytics/Sentry, que
  tipicamente hookam no `Log`/em um `Thread.UncaughtExceptionHandler`).
- **Mirrors**: detekt, ruleset `exceptions` (built-in) — `PrintStackTrace`. Não
  executado neste ambiente.
