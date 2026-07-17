# Glossário: detekt compose-rules

O ruleset de compose-rules para detekt (projeto `mrmans0n/compose-rules`, mesma nota de
group id da versão ktlint — `io.nlopez.compose.rules` atual, `com.twitter.compose.rules`
legado) é o mais completo em termos de nomes de regra citáveis, e é a fonte principal
de proveniência para a maioria das checagens deste scanner.

Este skill não depende de detekt estar configurado no projeto-alvo. Para corroboração
opcional, `scripts/try_external_linters.sh` procura o detekt-cli standalone (PATH ou
cache local) e, se disponível, roda a checagem de verdade — `scripts/install_external_linters.sh`
(sempre com confirmação explícita antes de `--yes`) baixa o jar do detekt-cli e o
plugin compose-rules para o cache local, sem tocar no projeto-alvo.

**Nota de arquitetura**: ao contrário do ktlint, o detekt carrega múltiplos jars de
`--plugins` num único classloader compartilhado — então basta passar o jar do ruleset
(`io.nlopez.compose.rules:detekt`) e sua dependência (`io.nlopez.compose.rules:common`)
separados por vírgula: `--plugins ruleset.jar,common.jar`. Não precisa mesclar jars
como no caso do ktlint. Isso foi confirmado rodando a ferramenta de verdade.

| Regra (detekt compose-rules, id real confirmado) | Checagem correspondente no scanner | Tópico |
|---|---|---|
| `ModifierMissing` | `modifier-param-missing` | `modifier-conventions` |
| `ModifierNaming` | `modifier-param-wrong-name` | `modifier-conventions` |
| `ModifierWithoutDefault` | `modifier-param-no-default` | `modifier-conventions` |
| `ComposableNaming` | `composable-naming` | `naming-and-api-shape` |
| `PreviewPublic` | `preview-naming-visibility` | `naming-and-api-shape` |
| `RememberMissing` | `unremembered-mutable-state` | `state-and-recomposition` |
| `ViewModelInjection` | `viewmodel-injection-in-leaf` | `viewmodel-architecture` |
| (sem id confirmado ainda) | `modifier-reused`, `unstable-collection-param`, `composition-local-overuse`, `multiple-content-emitters`, `viewmodel-param-forwarding`, `param-ordering`, `event-callback-naming` | vários |

Os ids acima foram confirmados rodando `detekt-cli --plugins ruleset.jar,common.jar`
de verdade contra os arquivos de teste deste skill — não são suposição. As regras sem
id confirmado na tabela não apareceram nos arquivos de teste usados na verificação (o
ruleset provavelmente as cobre com um nome diferente do assumido originalmente); ao
expandir a cobertura deste skill, vale rodar o detekt standalone de novo com arquivos
que exercitem esses casos e/ou consultar o `default-config.yml` do ruleset instalado
como fonte autoritativa da lista completa de regras.

Junto com as regras de compose-rules, o detekt sempre roda suas regras padrão
(`InvalidPackageDeclaration`, `FunctionNaming`, `UnusedParameter`,
`UnusedPrivateProperty` etc.) — essas não são específicas de Compose e ficam fora do
escopo deste skill.
