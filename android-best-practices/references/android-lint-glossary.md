# Glossário Android Lint

Proveniência: qual regra real do Android Lint cada `checkId` deste skill espelha,
quando existe uma. **Nenhum destes IDs foi confirmado rodando o Android Lint de
verdade neste ambiente** — diferente do skill irmão `jetpack-compose-refactor`, que
confirmou os IDs de ktlint/detekt compose-rules executando as ferramentas contra
fixtures reais. Aqui, os IDs vêm de documentação pública do Android Lint
(`AllowBackup`, `StaticFieldLeak` etc. são nomes de issue estáveis e bem conhecidos na
comunidade Android), mas não foram verificados executando `./gradlew lint` contra um
projeto real neste processo de construção do skill — ver `scripts/README.md`, seção
"Por que não Android Lint", para o porquê disso não ser prático de automatizar aqui
(requer Android SDK cmdline-tools completo).

Se o projeto-alvo já tiver `./gradlew lint` configurado, rodá-lo de forma oportunista
(nunca obrigatória) é a forma correta de confirmar estes IDs com o próprio Android Lint
de verdade — ver `SKILL.md`, passo 3.

| checkId deste skill | Android Lint issue ID | Categoria oficial |
|---|---|---|
| `manifest-allow-backup-enabled` | `AllowBackup` | Security |
| `manifest-debuggable-enabled` | `HardcodedDebugMode` | Security |
| `manifest-cleartext-traffic-enabled` | `UsesCleartextTraffic` | Security |
| `manifest-component-exported-without-permission` | `ExportedReceiver` / `ExportedService` / `ExportedContentProvider` | Security |
| `static-field-leaks-context` | `StaticFieldLeak` | Performance |
| `handler-inner-class-leak` | `HandlerLeak` | Performance |
| `hardcoded-user-facing-string` | `HardcodedText` / `SetTextI18n` | Internationalization |

Checagens deste skill **sem** id de Android Lint conhecido — marcadas como "checagem
própria" em `rule_topic_map.json`: `hardcoded-secret-literal`, `hardcoded-http-url`,
`fragment-view-binding-not-cleared`, `livedata-observeforever-not-removed`,
`runblocking-outside-tests`, `viewmodel-manual-coroutinescope`,
`asynctask-subclass-deprecated` (depreciação da própria API, não uma regra de linter
externa), `hardcoded-hex-color`, `println-instead-of-log`,
`viewmodel-holds-android-ui-reference`, `ui-layer-instantiates-network-or-db-client`.
