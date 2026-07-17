# Glossário: ktlint compose-rules

O ruleset de compose-rules para ktlint (projeto `mrmans0n/compose-rules`, publicado
sob o group id `io.nlopez.compose.rules` — houve uma renomeação a partir do group id
legado `com.twitter.compose.rules`) cobre essencialmente o mesmo conjunto semântico de
regras que a variante para detekt (ver `references/detekt-compose-rules.md`), só que
com ids em formato diferente (kebab-case com prefixo `compose:`, em vez de PascalCase).

Este skill não depende de ktlint estar configurado no projeto-alvo. Para corroboração
opcional, `scripts/try_external_linters.sh` procura o ktlint standalone (PATH ou cache
local) e, se disponível, roda a checagem de verdade — `scripts/install_external_linters.sh`
(sempre com confirmação explícita antes de `--yes`) baixa o binário do ktlint e o
ruleset compose-rules para o cache local, sem tocar no projeto-alvo.

**Nota de arquitetura**: `io.nlopez.compose.rules:ktlint` depende de um segundo jar,
`io.nlopez.compose.rules:common`, para classes compartilhadas. O ktlint isola cada jar
passado via `-R` num classloader próprio, então os dois jars **precisam** ser
mesclados num único jar antes do uso — é exatamente isso que
`install_external_linters.sh` faz automaticamente (gera `compose-rules-ktlint-merged-*.jar`).
Passar os dois jars separados via `-R` repetido **não funciona** (erro
`NoClassDefFoundError` em tempo de execução) — isso foi confirmado rodando a
ferramenta de verdade, não é suposição.

| Regra (ktlint compose-rules, id real confirmado) | Checagem correspondente no scanner | Tópico |
|---|---|---|
| `compose:naming-check` | `composable-naming` | `naming-and-api-shape` |
| `compose:parameter-naming` | `event-callback-naming` | `naming-and-api-shape` |
| `compose:modifier-missing-check` | `modifier-param-missing` | `modifier-conventions` |
| `compose:modifier-without-default-check` | `modifier-param-no-default` | `modifier-conventions` |
| `compose:modifier-naming` | `modifier-param-wrong-name` | `modifier-conventions` |
| `compose:modifier-composed-check` | `modifier-composed-deprecated` | `modifier-conventions` |
| `compose:multiple-emitters-check` | `multiple-content-emitters` | `naming-and-api-shape` |
| `compose:preview-public-check` | `preview-naming-visibility` | `naming-and-api-shape` |
| `compose:remember-missing-check` | `unremembered-mutable-state` | `state-and-recomposition` |
| `compose:mutable-state-autoboxing` | `autoboxing-state-creation` | `state-and-recomposition` |
| `compose:compositionlocal-allowlist` | `composition-local-overuse` | `state-and-recomposition` |
| `compose:vm-injection-check` | `viewmodel-injection-in-leaf` | `viewmodel-architecture` |
| (sem id de compose-rules confirmado ainda) | `viewmodel-param-forwarding`, `param-ordering`, `unstable-collection-param`, `lazy-items-missing-key`, `lazy-items-missing-content-type` | vários |

Os ids acima foram confirmados rodando `ktlint -R <jar mesclado>` de verdade contra os
arquivos de teste deste skill — não são suposição. Os checks do scanner sem id
confirmado na tabela não apareceram nos arquivos de teste usados na verificação (ou
correspondem a regras equivalentes do detekt sem uma contraparte 1:1 exercitada do
lado ktlint); ao expandir a cobertura deste skill, vale rodar o ktlint standalone de
novo com arquivos que exercitem esses casos para completar a tabela.

Junto com as regras de compose-rules, o ktlint sempre roda suas regras padrão de
formatação/estilo Kotlin (`standard:*`, ex. `standard:function-signature`,
`standard:function-naming`) — essas não são específicas de Compose e ficam fora do
escopo deste skill.
