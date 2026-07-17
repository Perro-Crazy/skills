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

Toda refatoração feita por este skill deve ser rastreável a um finding concreto do
scanner (`scripts/scan_compose_components.py`). Nunca introduza mudanças estilísticas
soltas só porque "parecem melhores", e nunca reporte como "problema encontrado" algo
que não veio do scanner — se não há um finding, não é escopo desta refatoração. Isso
mantém os diffs revisáveis, evita misturar refactor com gosto pessoal, e garante que
rodar o scanner duas vezes no mesmo código sempre produz a mesma lista de problemas
(o script já é determinístico — ver `scripts/README.md`).

Ler o código-fonte é permitido e esperado, mas só para **confirmar ou descartar** um
finding do scanner antes de aplicar a correção (ver limitações conhecidas do parser
heurístico, seção "Não confie cegamente no scanner" mais abaixo) — nunca para
"descobrir" problemas adicionais por conta própria. Se, lendo o código, você notar algo
que parece um problema real mas não tem finding correspondente, não o inclua na lista
de problemas nem aplique a correção — trate como observação e siga o passo opcional
"Revisão manual" abaixo.

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

### 3. Corroboração externa (obrigatório)

```bash
./scripts/try_external_linters.sh <alvo>
```

Se `ktlint`/`detekt` ainda não estiverem disponíveis (nem no `PATH`, nem no cache local
deste skill), instale-os automaticamente **sem pedir confirmação**, e então rode
`try_external_linters.sh` de novo:

```bash
./scripts/install_external_linters.sh --yes
./scripts/try_external_linters.sh <alvo>
```

`install_external_linters.sh --yes` baixa ktlint/detekt-cli + os jars do ruleset
compose-rules para um cache local do usuário (`~/.cache/jetpack-compose-refactor/tools/`)
— nunca toca no projeto-alvo, e as versões baixadas são fixas (ver constantes no topo
do script), então o resultado é reproduzível entre execuções. Esse download roda uma
única vez por máquina; runs seguintes já encontram tudo em cache e pulam direto para
`try_external_linters.sh`.

Nunca bloqueia o fluxo principal do skill: mesmo que o download falhe (rede
indisponível, etc.), siga em frente com os findings do scanner só. A saída de
`try_external_linters.sh` é bruta, direto do stdout de cada ferramenta — não é fundida
com o JSON do scanner (ver passo 8, ela vai numa seção própria do relatório).

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

### 7. Revisão manual (opcional, só sob pedido explícito)

Isso é um passo à parte, não uma extensão silenciosa do passo 4. Só execute se o
usuário pedir explicitamente algo como "revise esse arquivo manualmente também" ou
"tem mais alguma coisa que o scanner não pegaria". Ao fazer isso:

- Deixe claro, antes de começar, que essa parte é leitura livre de código, não uma
  checagem automatizada — logo **não é reproduzível** (rodar de novo pode notar coisas
  diferentes), diferente da lista do scanner.
- No relatório final, mantenha essa lista **separada e rotulada** (ver passo 8) —
  nunca misturada com a contagem de findings do scanner.
- Não aplique correção alguma baseada só nisso sem confirmar com o usuário primeiro.

### 8. Resumir

Ao final, reporte em duas listas sempre separadas:

1. **Findings do scanner (determinístico)** — contagem antes/depois por tópico, lista
   de arquivos alterados, e qualquer item propositalmente adiado com o motivo (ex.:
   "`unstable-collection-param` em `Foo.tags: List<String>` exigiria adicionar
   `kotlinx-collections-immutable` — não adicionei a dependência sem confirmar, ver
   seção abaixo"). Essa lista é a mesma se o scanner rodar de novo no mesmo código.
2. **Corroboração externa (ktlint/detekt, saída bruta do passo 3)** — sempre inclua,
   já que o passo 3 agora é obrigatório; se nenhuma ferramenta estava disponível e o
   download falhou, diga isso explicitamente em vez de omitir a seção.
3. **Observações manuais (só se o passo 7 foi executado)** — rotulada explicitamente
   como não determinística, sem entrar na contagem acima.

## Índice de referências

| Tópico | Arquivo | Quando abrir |
|---|---|---|
| Estado e recomposição | `references/state-and-recomposition.md` | findings: `unremembered-mutable-state`, `autoboxing-state-creation`, `unstable-collection-param`, `launched-effect-key-risk`, `composition-local-overuse` |
| Convenções de Modifier | `references/modifier-conventions.md` | findings: `modifier-param-missing`, `modifier-param-no-default`, `modifier-param-wrong-name`, `modifier-reused`, `modifier-composed-deprecated` |
| Naming e forma de API | `references/naming-and-api-shape.md` | findings: `composable-naming`, `event-callback-naming`, `param-ordering`, `multiple-content-emitters`, `preview-naming-visibility` |
| Arquitetura ViewModel | `references/viewmodel-architecture.md` | findings: `viewmodel-param-forwarding`, `viewmodel-injection-in-leaf` |
| Performance de listas preguiçosas | `references/lazy-list-performance.md` | findings: `lazy-items-missing-key`, `lazy-items-missing-content-type` — essas duas checagens só existem no scanner deste skill (nenhum Android Lint/ktlint/detekt cobre isso hoje); abra este arquivo sempre que o scanner reportar um desses dois findings, mesmo que ferramentas externas não tenham achado nada |
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
