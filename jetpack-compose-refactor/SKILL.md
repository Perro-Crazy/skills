---
name: jetpack-compose-refactor
description: Refactors Jetpack Compose and Compose Multiplatform UI code toward community best practices, guided by a built-in scanner that mirrors Android Lint's Compose checks, ktlint compose-rules, and detekt compose-rules — without requiring those tools to be configured in the target project. Use when the user asks to refactor, clean up, or modernize Composable functions; fix Compose lint/detekt/ktlint-style warnings; improve recomposition/stability; hoist state; fix Modifier parameter usage; fix ViewModel-in-composable anti-patterns; or audit a file, directory, or whole project for Compose best-practice violations.
version: 0.1.0
---

# Jetpack Compose Refactor

Refatora componentes Jetpack Compose (Android e Compose Multiplatform) seguindo boas
práticas de mercado, guiado por um scanner próprio que espelha as checagens mais
relevantes de Android Lint (Compose), ktlint compose-rules e detekt compose-rules —
sem depender de nenhuma dessas ferramentas estar configurada no projeto-alvo.

## Filosofia

Toda refatoração feita por este skill deve ser rastreável a algo concreto: um finding
do scanner (`scripts/scan_compose_components.py`) ou uma checagem nomeada
explicitamente em `references/*.md`. Nunca introduza mudanças estilísticas soltas só
porque "parecem melhores" — se não há um finding ou uma regra documentada por trás,
não é escopo desta refatoração. Isso mantém os diffs revisáveis e evita misturar
refactor com gosto pessoal.

## Workflow

### 1. Resolver o alvo

O alvo pode ser um arquivo específico, uma lista de composables citados pelo usuário,
ou um diretório/raiz de projeto inteiro a varrer recursivamente — os dois modos são
suportados igualmente pelo scanner. Se o usuário não deixar claro qual dos dois quer,
pergunte antes de escolher um escopo grande por conta própria.

### 2. Rodar o scanner

```bash
python3 scripts/scan_compose_components.py --path <alvo> --format json
```

Isso produz uma lista de findings, cada um já com `topic`, `severity`, `mirrors` (qual
regra real de linter aquela checagem espelha, quando existe) e o `referencesFile`/
`examplesFile` a consultar. Não precisa (e não deve tentar) rodar `./gradlew lint`/
`detekt`/`ktlintCheck` do projeto-alvo — esse scanner é a fonte primária e funciona
mesmo sem nenhum Gradle configurado, inclusive contra uma pasta solta de `.kt`.

### 3. (Opcional) Corroboração externa

Se quiser uma segunda opinião real:

```bash
./scripts/try_external_linters.sh <alvo>
```

Nunca bloqueia o fluxo. Se `ktlint`/`detekt` já estiverem disponíveis (no `PATH` ou no
cache local deste skill), roda-os de verdade e mostra a saída bruta — não tenta fundir
com o JSON do scanner, é só leitura complementar. Se nenhuma ferramenta estiver
disponível, o script imprime o comando exato de instalação (ex.:
`scripts/install_external_linters.sh --only ktlint --yes`) e segue em frente sem
bloquear. **Nunca rode esse comando de instalação por conta própria** — pergunte ao
usuário primeiro (ver seção "O que sempre perguntar antes de fazer"). Se o usuário
confirmar, `install_external_linters.sh` baixa os binários para um cache local
(`~/.cache/jetpack-compose-refactor/tools/`) sem tocar no projeto-alvo; rode
`try_external_linters.sh` de novo em seguida para usar as ferramentas recém-instaladas.

### 4. Carregar as referências relevantes

Para cada tópico com findings, abra **apenas** o `references/*.md` correspondente
(tabela abaixo) — não carregue todos de uma vez. Cada arquivo de referência explica o
racional completo, o que o real linter checaria (`mirrors`), e aponta para o
`examples/*.md` com o padrão antes/depois correspondente.

### 5. Aplicar as refatorações

Incrementalmente, um tópico/arquivo por vez — não misture múltiplos tópicos não
relacionados num único diff grande. Para cada finding, use o exemplo em `examples/`
como modelo de padrão, mas adapte ao código real (nomes, tipos, contexto) em vez de
copiar literalmente.

### 6. Verificar

- Re-rode o scanner no mesmo alvo e confirme que os findings-alvo desapareceram e
  nenhum finding novo (de outra checagem) surgiu como efeito colateral.
- Se houver um projeto Gradle real por trás do alvo, compile o módulo tocado
  (`./gradlew :modulo:compileDebugKotlin` ou equivalente) e rode os testes existentes
  que cobrem os arquivos alterados — isso é oportunista, não obrigatório: o scanner e o
  workflow de refatoração funcionam mesmo sem projeto Gradle nenhum montado.
- Se uma refatoração mudou a assinatura pública de um composable (ex.: hoisting de
  estado adiciona/remove parâmetros), avise isso explicitamente no resumo — é uma
  mudança visível para quem chama, não algo para passar despercebido.

### 7. Resumir

Ao final, reporte: contagem de findings antes/depois por tópico, lista de arquivos
alterados, e qualquer item propositalmente adiado com o motivo (ex.: "`unstable-collection-param`
em `Foo.tags: List<String>` exigiria adicionar `kotlinx-collections-immutable` — não
adicionei a dependência sem confirmar, ver seção abaixo").

## Índice de referências

| Tópico | Arquivo | Quando abrir |
|---|---|---|
| Estado e recomposição | `references/state-and-recomposition.md` | findings: `unremembered-mutable-state`, `autoboxing-state-creation`, `unstable-collection-param`, `launched-effect-key-risk`, `composition-local-overuse` |
| Convenções de Modifier | `references/modifier-conventions.md` | findings: `modifier-param-missing`, `modifier-param-no-default`, `modifier-param-wrong-name`, `modifier-reused`, `modifier-composed-deprecated` |
| Naming e forma de API | `references/naming-and-api-shape.md` | findings: `composable-naming`, `event-callback-naming`, `param-ordering`, `multiple-content-emitters`, `preview-naming-visibility` |
| Arquitetura ViewModel | `references/viewmodel-architecture.md` | findings: `viewmodel-param-forwarding`, `viewmodel-injection-in-leaf` |
| Performance de listas preguiçosas | `references/lazy-list-performance.md` | findings: `lazy-items-missing-key`, `lazy-items-missing-content-type` — **sempre revise este tópico mesmo com zero findings de linter**, já que nenhuma dessas checagens tem cobertura em Android Lint/ktlint/detekt hoje (ver o arquivo para o porquê) |
| Glossário Android Lint | `references/android-lint-compose-rules.md` | proveniência — qual regra real cada checagem espelha |
| Glossário ktlint compose-rules | `references/ktlint-compose-rules.md` | proveniência |
| Glossário detekt compose-rules | `references/detekt-compose-rules.md` | proveniência |

## Índice de scripts

- `scripts/scan_compose_components.py` — scanner principal (ver `scripts/README.md`
  para uso detalhado e limitações conhecidas do parser heurístico).
- `scripts/try_external_linters.sh` — corroboração opcional via ktlint/detekt
  standalone (PATH ou cache local), se disponíveis no ambiente.
- `scripts/install_external_linters.sh` — instala ktlint/detekt-cli + compose-rules no
  cache local do usuário; **dry-run por padrão**, só baixa de fato com `--yes` explícito.
- `scripts/rule_topic_map.json` — fonte de verdade mapeando cada `checkId` a
  tópico/severidade/arquivo de referência/exemplo/regra espelhada.

Não confie cegamente no scanner em casos extremos: ele não é um parser Kotlin
completo (ver limitações documentadas no topo de `scan_compose_components.py`) —
composables com corpo em forma de expressão, por exemplo, só passam pelas checagens de
assinatura. Sempre leia o código real antes de aplicar uma refatoração baseada só no
texto de um finding.

## O que sempre perguntar antes de fazer

- **Adicionar uma dependência nova** ao projeto-alvo (ex.: `kotlinx-collections-immutable`
  para resolver `unstable-collection-param`) — proponha a alternativa sem dependência
  nova (wrapper `@Immutable`) por padrão, e só adicione a dependência se o usuário
  confirmar que quer isso.
- **Editar `build.gradle*`/version catalogs** do projeto-alvo por qualquer motivo,
  incluindo configurar detekt/ktlint com compose-rules — este skill deliberadamente
  não depende disso para funcionar, e mudar configuração de build/CI é uma decisão que
  afeta o time todo.
- **Mudar a assinatura pública de um composable** (parâmetros adicionados/removidos/
  reordenados) — sinalize antes de aplicar quando a mudança afeta call sites fora do
  arquivo que está sendo refatorado.
- **Baixar/instalar ktlint/detekt/compose-rules externamente** (rodar
  `scripts/install_external_linters.sh --yes`) — mesmo isolado no cache local do
  usuário e sem tocar no projeto-alvo, é execução de binário de terceiros baixado da
  internet. Pergunte antes, mesmo que `try_external_linters.sh` já tenha sugerido o
  comando exato.
