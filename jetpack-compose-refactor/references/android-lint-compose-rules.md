# Glossário: Android Lint (checks de Compose)

Este arquivo **não** é usado para configurar ou rodar o Android Lint — `scan_compose_components.py`
é o mecanismo primário e não depende do build do projeto-alvo (ver Contexto no `SKILL.md`).
Ele existe só para registrar a proveniência: de qual regra real de linter cada checagem
do scanner foi inspirada, para quem quiser cross-checar contra a ferramenta de verdade
rodando `./gradlew lint`/`lintDebug` num projeto Android real que já tenha essas
checagens habilitadas (elas vêm junto com os artefatos de runtime/UI do Compose na
maioria das versões atuais de AGP/Compose — não costuma ser necessário opt-in
separado, mas confirme isso na versão do projeto em questão, já que o mecanismo de
empacotamento já mudou entre versões).

| Regra (Android Lint) | Checagem correspondente no scanner | Tópico |
|---|---|---|
| `ComposableNaming` | `composable-naming` | `naming-and-api-shape` |
| `ComposableParametersOrdering` | `param-ordering` | `naming-and-api-shape` |
| `ModifierParameter` | `modifier-param-missing` | `modifier-conventions` |
| `UnrememberedMutableState` | `unremembered-mutable-state` | `state-and-recomposition` |
| `AutoboxingStateCreation` | `autoboxing-state-creation` | `state-and-recomposition` |
| `FrequentlyChangingValue` | (sem checagem própria ainda — ver nota abaixo) | `state-and-recomposition` |
| `CoroutineCreationDuringComposition` | (sem checagem própria ainda) | `state-and-recomposition` |
| `ProduceStateDoesNotAssignValue` | (sem checagem própria ainda) | `state-and-recomposition` |

**Nota**: esta lista foi compilada a partir do conhecimento de domínio disponível no
momento em que o skill foi escrito, não de uma execução real do Android Lint contra um
projeto de referência. Antes de tratá-la como exaustiva, rode `./gradlew lint` num
módulo Compose real e confira contra o relatório gerado (`**/build/reports/lint-results-*.xml`)
— o conjunto de checagens de Compose do Android Lint cresce a cada versão de AGP/Compose.
As três regras marcadas "sem checagem própria ainda" são candidatas óbvias para uma
próxima iteração deste skill.
