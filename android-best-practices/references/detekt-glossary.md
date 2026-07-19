# Glossário detekt

Proveniência: qual regra real do detekt (rulesets padrão, built-in — nenhum plugin de
terceiros necessário) cada `checkId` deste skill espelha. Assim como no glossário de
Android Lint, **estes IDs não foram confirmados rodando o detekt de verdade neste
ambiente** durante a construção do skill — vêm de documentação pública do detekt. Ao
contrário de Android Lint, porém, detekt **é** trivial de baixar e rodar de fato via
`scripts/install_external_linters.sh` + `scripts/try_external_linters.sh` (não precisa
de Android SDK, só de um jar + `java`) — rode esse par de scripts para corroborar estes
IDs com o detekt de verdade contra o alvo real, em vez de confiar só nesta tabela.

| checkId deste skill | Regra detekt | Ruleset (built-in) |
|---|---|---|
| `globalscope-launch-usage` | `GlobalCoroutineUsage` | `coroutines` |
| `not-null-assertion-operator` | `UnsafeCallOnNullableType` | `potential-bugs` |
| `empty-catch-block` | `EmptyCatchBlock` | `empty-blocks` |
| `generic-exception-caught` | `TooGenericExceptionCaught` | `exceptions` |
| `swallowed-exception` | `SwallowedException` | `exceptions` |
| `printstacktrace-usage` | `PrintStackTrace` | `exceptions` |

Checagens deste skill sem regra detekt conhecida — são Android-específicas demais
(manifest, ViewModel, Context) para um linter Kotlin genérico cobrir; ver
`references/android-lint-glossary.md` para as que têm equivalente em Android Lint, e
`rule_topic_map.json` para a lista completa marcada "checagem própria".
