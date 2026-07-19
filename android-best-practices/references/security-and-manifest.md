# Segurança e AndroidManifest.xml

Checagens do scanner que caem neste tópico: `manifest-allow-backup-enabled`,
`manifest-debuggable-enabled`, `manifest-cleartext-traffic-enabled`,
`manifest-component-exported-without-permission`, `hardcoded-secret-literal`,
`hardcoded-http-url`.

As quatro primeiras operam sobre `AndroidManifest.xml`; as duas últimas sobre literais
em código Kotlin/Java. Todas compartilham o mesmo racional: configuração insegura por
omissão/padrão, ou segredo exposto onde não deveria estar.

## `android:allowBackup="true"` explícito

**Finding: `manifest-allow-backup-enabled`.** Com `allowBackup="true"` (que também é o
default do Android quando o atributo é omitido), o sistema pode fazer backup completo do
app — via `adb backup`, ou automaticamente para a nuvem em versões mais antigas do
Android — sem que o app tenha controle granular sobre o que é incluído, a menos que
`android:fullBackupContent` (backup baseado em regras) ou
`android:dataExtractionRules` (API 31+) também estejam configurados para excluir dados
sensíveis. Um backup extraído (ex.: de um dispositivo com acesso físico, ou via `adb
backup` sem senha em versões antigas) pode expor tokens de sessão, credenciais em
SharedPreferences, ou bancos de dados locais inteiros.

- Fix: se o app não lida com dado sensível nenhum, o backup padrão é aceitável — não é
  necessariamente um bug, mas vale a decisão ser **explícita** (`allowBackup="false"`,
  ou uma `dataExtractionRules`/`fullBackupContent` restritiva) em vez de acidental.
- **Mirrors**: Android Lint `AllowBackup` — id documentado publicamente, não executado
  neste ambiente (sem Android SDK disponível para rodar `./gradlew lint` de verdade —
  ver `scripts/README.md`, seção "Por que não Android Lint").

## `android:debuggable="true"` hardcoded no manifest

**Finding: `manifest-debuggable-enabled`.** O Android Gradle Plugin já define este
atributo automaticamente por build type (`debug` → `true`, `release` → `false`) — se ele
aparece hardcoded como `true` no `AndroidManifest.xml` principal (não num
`debug/AndroidManifest.xml` de override específico do build type debug), o risco é essa
configuração vazar para um build de release por engano, deixando o app instalável com
debug habilitado em produção.

- Fix: remova o atributo do manifest principal e deixe o build type controlar; se
  precisar de um override só para debug, coloque em `src/debug/AndroidManifest.xml`, não
  em `src/main/AndroidManifest.xml`.
- **Mirrors**: Android Lint `HardcodedDebugMode` — não executado neste ambiente.

## `android:usesCleartextTraffic="true"` global

**Finding: `manifest-cleartext-traffic-enabled`.** Libera tráfego HTTP não criptografado
para **qualquer host**, não só o(s) que realmente precisam disso (ex.: um servidor de
desenvolvimento local). Desde a API 28 o default do Android já é `false`; reverter isso
globalmente expõe qualquer chamada de rede do app (incluindo para hosts de terceiros que
o time nem controla) a interceptação/adulteração em trânsito.

- Fix: prefira uma [Network Security
  Config](https://developer.android.com/training/articles/security-config) com
  exceções pontuais por domínio (`<domain-config cleartextTrafficPermitted="true">`
  restrito a um host específico) em vez do atributo global no manifest.
- **Mirrors**: Android Lint `UsesCleartextTraffic` — não executado neste ambiente.

## Componente exportado sem permissão

**Finding: `manifest-component-exported-without-permission`.** Aplica-se só a
`<receiver>`, `<service>` e `<provider>` com `android:exported="true"` e sem
`android:permission` — **deliberadamente não inclui `<activity>`**, já que activities são
comumente exportadas de propósito (launcher, deep links via `<intent-filter>`) e exigir
permission nelas geraria ruído desproporcional. Para receiver/service/provider, exportar
sem restrição significa que **qualquer app instalado no dispositivo** pode invocar o
componente diretamente — enviar um broadcast malicioso, iniciar o service com dados
arbitrários, ou consultar o provider — sem ter sido convidado a interagir com o app.

- Fix: restrinja com `android:permission` (tipicamente uma permission
  `protectionLevel="signature"` se o consumidor pretendido for outro app do mesmo
  fabricante) — ou, se a exposição não for de fato intencional, mude para
  `exported="false"`.
- **Mirrors**: família Android Lint `ExportedReceiver`/`ExportedService`/
  `ExportedContentProvider` — não executado neste ambiente.

## Segredo hardcoded em literal de string

**Finding: `hardcoded-secret-literal`.** Uma propriedade cujo nome sugere segredo
(`apiKey`, `secret`, `token`, `password`, `clientSecret` etc., case-insensitive)
inicializada com uma string literal fixa. Se o valor for de fato um segredo, ele fica
embutido no APK/AAB — bytecode Kotlin/Java é trivial de descompilar (`apktool`,
`jadx`), então "não está no controle de versão" não é suficiente: o valor também não
deveria estar compilado no binário distribuído.

- Fix: mova para fora do controle de versão e fora do binário compilado quando possível
  — `local.properties` + `BuildConfig` (ainda extraível do binário, mas ao menos fora do
  git), um secrets manager consultado em runtime, ou uma API própria que emita
  tokens de vida curta em vez de embutir uma chave de longa duração.
- **Sempre confirme antes de agir**: o scanner sinaliza pelo **nome da variável**, não
  pelo valor real — um nome como `apiKeyHeader` inicializado com `"Authorization"` (o
  nome do header, não uma chave) é um falso positivo típico.
- **Mirrors**: sem id formal de Android Lint/detekt equivalente — checagem própria, na
  mesma classe de problema que scanners de segredo genéricos (gitleaks, trufflehog)
  cobrem em outros ecossistemas.

## URL HTTP hardcoded

**Finding: `hardcoded-http-url`** (severidade `info`). Uma string literal
`"http://..."` (excluindo `localhost`/`127.0.0.1`/`10.0.2.2`, endereços comuns de
desenvolvimento local) em vez de `https://`. Complementa
`manifest-cleartext-traffic-enabled`: mesmo com a Network Security Config restrita, um
endpoint específico hardcoded em `http://` ainda transmite sem criptografia para aquele
host.

- Fix: confirme se o endpoint tem suporte a TLS antes de trocar para `https://` — times
  de integração às vezes hardcoded um endpoint de homologação `http://` de propósito, e
  trocar sem confirmar pode quebrar a chamada.
- **Mirrors**: relacionado a Android Lint `UsesCleartextTraffic`, mas aplicado no nível
  de literal de código em vez do manifest — checagem própria.
