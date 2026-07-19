# Recursos e higiene de UI

Checagens do scanner que caem neste tópico: `hardcoded-user-facing-string`,
`hardcoded-hex-color`, `println-instead-of-log`.

## String voltada ao usuário hardcoded

**Finding: `hardcoded-user-facing-string`.** Uma string literal passada direto para uma
chamada de exibição — `setText("...")`, `setTitle("...")`, `setMessage("...")`,
`Toast.makeText(ctx, "...", ...)` — em vez de vir de um recurso `strings.xml`.

Duas consequências práticas: impede localização (o app não pode ser traduzido para outro
idioma sem editar código-fonte Kotlin/Java, algo que times de tradução tipicamente não
têm acesso para fazer) e espalha texto de produto pelo código em vez de centralizá-lo em
um único lugar revisável.

- Fix: `<string name="erro_carregar_dados">Falha ao carregar dados</string>` em
  `res/values/strings.xml`, referenciado via `getString(R.string.erro_carregar_dados)`
  (Activity/Fragment com Context), `context.getString(...)`, ou `stringResource(...)` em
  Compose (ver o skill irmão `jetpack-compose-refactor` para checagens específicas de
  Compose).
- **Limitação**: o scanner cobre um conjunto fixo de chamadas comuns (`setText`,
  `setTitle`, `setMessage`, `Toast.makeText`) — strings passadas para APIs menos comuns
  (ex.: uma lib de terceiros) não são detectadas. Exclui deliberadamente strings com `%`
  ou `{`/`}` no meio (prováveis format strings já parametrizadas, mais prováveis de já
  virem de um recurso em algum nível acima).
- **Mirrors**: Android Lint `HardcodedText`/`SetTextI18n` — ids documentados
  publicamente, não executados neste ambiente (ver `scripts/README.md`).

## Cor hexadecimal hardcoded

**Finding: `hardcoded-hex-color`** (severidade `info`). Uma string hex literal
(`"#RRGGBB"`/`"#AARRGGBB"`) passada para `Color.parseColor(...)` em vez de vir de um
recurso de cor.

Mesma motivação de `hardcoded-user-facing-string`, aplicada a cor: dificulta reaproveitar
a mesma cor de forma consistente em outro lugar do app, ou trocá-la de uma vez (rebrand,
suporte a dark mode) sem caçar cada ocorrência literal pelo código.

- Fix: `<color name="erro_vermelho">#FF00FF00</color>` em `res/values/colors.xml`,
  referenciado via `ContextCompat.getColor(context, R.color.erro_vermelho)`; em um app
  que já usa Material 3, prefira um token de tema
  (`MaterialTheme.colorScheme.error`, no mundo Compose) a uma cor fixa nova.
- **Mirrors**: sem id formal de Android Lint/detekt conhecido — checagem própria, mesma
  família de guidance que `HardcodedText` (Android Lint) aplicada a cor em vez de texto.

## `println`/`System.out.print` em vez de `Log`

**Finding: `println-instead-of-log`** (severidade `info`). `println(...)` ou
`System.out.print(...)`/`System.out.println(...)` fora de código de teste.

Em um dispositivo Android real, saída em stdout não aparece no logcat com tag/nível
filtráveis — não dá pra `adb logcat | grep MinhaTag` nela — e um build de release
tipicamente não tem ninguém monitorando stdout do processo.

- **Não dispara** para arquivos sob `/test/`, `/androidTest/` ou `/sharedTest/` no
  caminho — `println` em teste é uma prática comum e aceita, sem motivo pra trocar por
  `Log` (que exige um Android runtime real ou um mock, ao contrário de `println`).
- Fix: `android.util.Log` (`Log.d`/`Log.i`/`Log.w`/`Log.e`) com uma `TAG` consistente por
  classe, que integra com logcat e com qualquer ferramenta de observabilidade
  configurada.
- **Mirrors**: sem id formal de Android Lint/detekt — guidance geral de observabilidade
  em Android, não uma regra específica de alguma ferramenta.
