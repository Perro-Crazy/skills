# Arquitetura e separação de camadas

Checagens do scanner que caem neste tópico: `viewmodel-holds-android-ui-reference`,
`ui-layer-instantiates-network-or-db-client`.

Ambas as checagens seguem o mesmo racional do [Guide to App Architecture
oficial](https://developer.android.com/topic/architecture): a camada de UI
(Activity/Fragment/Composable) deveria depender só de um ViewModel exibindo estado
observável, e o ViewModel deveria depender só de fontes de dados abstratas (repositório),
nunca o contrário nas duas pontas.

## `ViewModel` retendo uma referência Android de ciclo de vida curto

**Finding: `viewmodel-holds-android-ui-reference`.** Uma classe `ViewModel`/
`AndroidViewModel` com uma propriedade (via construtor `val`/`var` ou declarada no corpo)
tipada `Context`, `Activity` (ou subtipo), `View` ou `Fragment` (ou subtipo) —
deliberadamente **exclui** `Application` (o padrão oficial suportado via
`AndroidViewModel(application: Application)`).

Um `ViewModel` sobrevive a mudanças de configuração (rotação de tela, mudança de idioma
em runtime etc.) e pode sobreviver à Activity/Fragment/View original inteiramente — é
literalmente o motivo de existir da classe (preservar estado além do ciclo de vida da
UI). Segurar uma referência direta a um tipo de vida curta é a causa mais comum de
"Activity leaked" relatada por LeakCanary em apps reais: a Activity antiga (já destruída
pelo sistema) continua presa na memória via o campo do ViewModel, que sobrevive.

- Fix: se o ViewModel genuinamente precisa de um `Context` (ex.: para checar
  conectividade, acessar `Resources`), use `AndroidViewModel` + `getApplication()` — o
  único `Context` seguro de reter pela vida inteira do ViewModel. Se o ViewModel precisa
  notificar a UI de algo (navegação, um Snackbar, um diálogo), **não** referencie a UI
  diretamente — exponha estado observável (`StateFlow`/`LiveData`/eventos one-shot via
  `SharedFlow`) que a UI observa e reage, mantendo o fluxo de dependência numa única
  direção (UI → ViewModel, nunca o contrário).
- **Detecção em duas partes**: o scanner varre tanto o construtor primário
  (`class Foo(private val context: Context) : ViewModel()`) quanto propriedades
  declaradas no corpo da classe — um finding originado do construtor aponta para a
  linha de cabeçalho da classe (o scanner não tem offset exato dentro da lista de
  parâmetros do construtor primário nesta versão), enquanto um finding do corpo aponta
  para a linha exata da propriedade.
- **Mirrors**: sem id formal de Android Lint/detekt — guidance oficial do Guide to App
  Architecture ("ViewModels should not reference to Views or Activity/Fragment
  Lifecycle").

## Camada de UI instanciando cliente de rede/banco diretamente

**Finding: `ui-layer-instantiates-network-or-db-client`** (severidade `info`). Uma classe
Activity/Fragment cujo corpo constrói diretamente `Retrofit.Builder()`, `OkHttpClient()`
ou `Room.databaseBuilder(...)`.

Segundo o Guide to App Architecture, a camada de UI não deveria conhecer **como** os
dados são obtidos (qual biblioteca HTTP, qual URL base, qual configuração de banco) — só
deveria depender de um ViewModel que expõe dados já prontos para exibição. Instanciar o
cliente direto na Activity/Fragment acopla a tela a uma implementação concreta:
dificulta testar a UI isoladamente (não dá pra trocar por um fake sem tocar na tela),
dificulta trocar a fonte de dados depois, e tipicamente resulta em múltiplas instâncias
do mesmo cliente espalhadas pelo app em vez de uma única compartilhada.

- Fix: mova a criação para uma camada de repositório/data source, injetada no ViewModel
  (via um framework de DI como Hilt/Koin, ou construção manual num container simples) —
  a Activity/Fragment passa a depender só do ViewModel.
- **Limitação**: a checagem procura literalmente `Retrofit.Builder()`/`OkHttpClient()`/
  `Room.databaseBuilder(...)` no corpo da classe — não detecta padrões equivalentes com
  outras bibliotecas (Ktor, SQLDelight direto etc.) nem uma fábrica própria que esconda a
  instanciação (ex.: `NetworkModule.buildClient()` chamado da Activity ainda é o mesmo
  problema arquitetural, mas não bate no regex).
- **Mirrors**: sem id formal de Android Lint/detekt — guidance oficial do Guide to App
  Architecture sobre separação de camadas UI/dados.
