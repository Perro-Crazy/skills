# Context, View e vazamentos de ciclo de vida

Checagens do scanner que caem neste tópico: `static-field-leaks-context`,
`fragment-view-binding-not-cleared`, `handler-inner-class-leak`,
`livedata-observeforever-not-removed`.

Esta é a classe de bug mais comum e mais cara de diagnosticar em apps Android — a
existência de ferramentas inteiras (LeakCanary) dedicadas só a detectar isso em runtime
é evidência de quão fácil é introduzir sem perceber. O padrão comum a todas as quatro
checagens: alguma coisa que deveria ter vida curta (uma Activity, um Fragment, a view
hierarchy de um Fragment) acaba retida por algo de vida mais longa (um campo estático,
um `Handler` com mensagens pendentes, um observer nunca removido).

## Campo estático segurando Context/Activity/View

**Finding: `static-field-leaks-context`.** Uma propriedade `var`/`val` dentro de um
`object`/`companion object` tipada `Context`, `Activity` (ou subtipo), `View` ou
`Fragment` (ou subtipo) — deliberadamente **exclui** `Application` (o único Context
seguro de reter estaticamente, já que vive tanto quanto o processo).

Do ponto de vista da JVM, uma propriedade de `object`/`companion object` Kotlin é
essencialmente um campo estático: existe uma única instância, viva pela duração inteira
do processo. Se o valor atribuído for uma Activity (ou uma View que referencia sua
Activity via `view.context`), essa Activity nunca é coletada pelo garbage collector
enquanto o processo estiver rodando — mesmo depois do usuário sair da tela e o sistema
achar que deveria estar livre para liberar aquela memória.

- Fix: não retenha a referência; se for genuinamente necessário guardar algo
  relacionado, use `WeakReference<Activity>` (permite ao GC coletar mesmo com a
  referência pendurada) ou, melhor ainda, guarde só o dado necessário (não o objeto
  inteiro).
- **Limitação importante**: o scanner sinaliza pelo **tipo declarado**, não pelo valor
  real atribuído. Uma propriedade `Context` que sempre recebe `.applicationContext` é
  segura de reter — mas o scanner não faz essa distinção (não há análise de fluxo de
  dados). Confirme a origem do valor antes de tratar como bug real.
- **Mirrors**: Android Lint `StaticFieldLeak` — não executado neste ambiente.

## ViewBinding de Fragment não limpo em `onDestroyView`

**Finding: `fragment-view-binding-not-cleared`.** Um Fragment com um campo
`private var _binding: FooBinding?` (o padrão oficial de nulling de ViewBinding em
Fragments) cujo `onDestroyView()` — se existir — não atribui `_binding = null` (ou não
existe override de `onDestroyView()` nenhum no arquivo).

A view hierarchy de um Fragment é destruída em `onDestroyView()`, mas a **instância do
Fragment** pode continuar viva por mais tempo (voltando de um back stack de navegação,
por exemplo — o Fragment não é recriado, só a view). Sem nulling explícito do binding, a
referência à `View` antiga (já removida da hierarquia, mas ainda referenciada pelo
binding) fica presa até o Fragment em si ser destruído — um vazamento pequeno, mas
sistemático em qualquer app com Fragments reaproveitados via back stack.

- Fix (padrão oficial):
  ```kotlin
  override fun onDestroyView() {
      super.onDestroyView()
      _binding = null
  }
  ```
- **Mirrors**: sem id formal de Android Lint/detekt — guidance oficial do Android sobre
  [View Binding em
  Fragments](https://developer.android.com/topic/libraries/view-binding#fragments).

## `Handler` como inner class não estática

**Finding: `handler-inner-class-leak`** (severidade `info` — a checagem mais heurística
deste tópico). Uma `inner class` (Kotlin exige a palavra-chave explícita `inner` para
reter referência à instância externa — sem ela, é equivalente a uma classe estática
Java) estendendo `Handler`, declarada dentro de uma Activity ou Fragment.

Uma `inner class` retém uma referência implícita à instância externa. Combinado com
mensagens/Runnables pendentes na fila de um `Handler` (ex.: um `postDelayed` agendado
para daqui a alguns segundos), isso pode manter a Activity/Fragment externa viva além do
seu ciclo de vida enquanto a mensagem não é processada ou cancelada.

- Fix: prefira uma classe top-level, ou uma classe aninhada **sem** `inner`, recebendo
  uma `WeakReference` explícita à Activity/Fragment se precisar chamar de volta nela; e
  sempre cancele mensagens pendentes em `onDestroy()`/`onDestroyView()`
  (`handler.removeCallbacksAndMessages(null)`).
- **Mirrors**: Android Lint `HandlerLeak` — historicamente documentado, majoritariamente
  voltado a Java (onde não existe a distinção `inner`/não-`inner` do Kotlin, então a
  regra original olha para "non-static inner class" de forma equivalente); heurística
  deste scanner adaptada para a sintaxe `inner class` do Kotlin. Não executado neste
  ambiente.

## `.observeForever(...)` sem `.removeObserver(...)` correspondente

**Finding: `livedata-observeforever-not-removed`** (severidade `info`). Uma chamada
`.observeForever { ... }` em um arquivo onde nenhum `.removeObserver(...)` aparece.

Ao contrário de `.observe(lifecycleOwner) { ... }` (lifecycle-aware — remove o observer
automaticamente quando o `LifecycleOwner` é destruído), `observeForever` mantém o
observer registrado indefinidamente até `removeObserver` ser chamado manualmente. Se o
componente que registrou o observer for destruído sem essa chamada, o observer (e
qualquer coisa que ele capture via closure) vaza.

- Fix: prefira `.observe(lifecycleOwner, ...)` sempre que houver um `LifecycleOwner`
  disponível (a esmagadora maioria dos casos dentro de Activity/Fragment/ViewModel com
  `viewLifecycleOwner`); se `observeForever` for genuinamente necessário (ex.: um
  observer que precisa sobreviver à UI), pareie com `removeObserver` no ponto certo do
  ciclo de vida (ex.: `onCleared()` de um ViewModel).
- **Limitação**: a checagem é por arquivo inteiro, não por observer individual — um
  arquivo com múltiplos `observeForever` e ao menos um `removeObserver` em qualquer
  lugar do arquivo não dispara o finding para nenhuma das ocorrências, mesmo que só uma
  delas esteja de fato pareada. Confirme individualmente antes de aplicar a correção.
- **Mirrors**: sem id formal de Android Lint/detekt — guidance oficial de LiveData
  sobre `observeForever` exigir `removeObserver` manual.
