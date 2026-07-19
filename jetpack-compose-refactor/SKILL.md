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

### 1. Resolver o alvo e o modo

O alvo pode ser um arquivo específico, uma lista de composables citados pelo usuário,
ou um diretório/raiz de projeto inteiro a varrer recursivamente — os dois modos são
suportados igualmente pelo scanner. Se o usuário não deixar claro qual dos dois quer,
pergunte antes de escolher um escopo grande por conta própria.

Além do alvo, há dois **modos de operação**:

- **Aplicação (padrão)** — as refatorações são escritas direto nos arquivos conforme o
  passo 5 avança.
- **Sugestão** — nenhum arquivo é tocado; para cada finding, proponha o diff (antes/depois)
  e pare, aguardando o usuário aprovar quais aplicar. Use este modo quando o usuário
  pedir explicitamente algo como "só sugere", "não edita ainda", "me mostra antes de
  aplicar" — ou sempre que o escopo for grande o bastante (muitos arquivos/findings) que
  aplicar tudo de uma vez sem revisão prévia seria arriscado; nesse caso, pergunte qual
  modo o usuário prefere em vez de assumir aplicação direta.

O modo escolhido vale para toda a sessão de refatoração corrente; não alterne entre os
dois modos no meio do processo sem o usuário pedir.

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

### 5. Aplicar as refatorações (ou propô-las, no modo sugestão)

Incrementalmente, um tópico/arquivo por vez — não misture múltiplos tópicos não
relacionados num único diff grande. Para cada finding, use o exemplo em `examples/`
como modelo de padrão, mas adapte ao código real (nomes, tipos, contexto) em vez de
copiar literalmente.

- **Modo aplicação**: edite os arquivos diretamente (via `Edit`/`Write`).
- **Modo sugestão**: não use `Edit`/`Write` nesta etapa. Para cada finding, mostre um
  bloco antes/depois (igual ao formato de `examples/*.md`) referenciando `arquivo:linha`,
  sem gravar nada em disco. Agrupe por tópico/arquivo como faria no modo aplicação — a
  única diferença é que o resultado fica em texto, aguardando aprovação, em vez de já
  escrito. Deixe claro ao final de cada bloco que aquele diff ainda não foi aplicado.

### 6. Verificar

No **modo aplicação**:

- Re-rode o scanner no mesmo alvo e confirme que os findings-alvo desapareceram e
  nenhum finding novo (de outra checagem) surgiu como efeito colateral.
- Se houver um projeto Gradle real por trás do alvo, compile o módulo tocado
  (`./gradlew :modulo:compileDebugKotlin` ou equivalente) e rode os testes existentes
  que cobrem os arquivos alterados — isso é oportunista, não obrigatório: o scanner e o
  workflow de refatoração funcionam mesmo sem projeto Gradle nenhum montado.
- Se uma refatoração mudou a assinatura pública de um composable (ex.: hoisting de
  estado adiciona/remove parâmetros), avise isso explicitamente no resumo — é uma
  mudança visível para quem chama, não algo para passar despercebido.

No **modo sugestão**, este passo não roda ainda — nada foi escrito, então não há o que
re-escanear ou compilar. Ele só se aplica depois que o usuário aprovar um ou mais diffs
propostos e você efetivamente escrevê-los (nesse momento, trate como uma passagem pelo
modo aplicação só para os findings aprovados).

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

**Modo aplicação** — reporte em três listas sempre separadas:

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

**Modo sugestão** — reporte, em vez disso:

1. **Findings do scanner com diff proposto** — agrupados por tópico/arquivo, cada um com
   o bloco antes/depois do passo 5, marcados como "aguardando aprovação". Nenhuma
   contagem de "antes/depois" real ainda, já que nada foi aplicado.
2. **Corroboração externa**, igual ao modo aplicação.
3. **Observações manuais**, igual ao modo aplicação, se o passo 7 rodou.
4. Uma pergunta objetiva ao final: quais diffs aplicar (todos, por tópico, ou um a um).
   Depois de aprovados, aplique só os escolhidos e repita o passo 6 (verificar) para
   eles — o restante continua só sugerido até nova instrução.

## Índice de referências

| Tópico | Arquivo | Quando abrir |
|---|---|---|
| Estado e recomposição | `references/state-and-recomposition.md` | findings: `unremembered-mutable-state`, `autoboxing-state-creation`, `unstable-collection-param`, `launched-effect-key-risk`, `composition-local-overuse`, `disposable-effect-missing-ondispose`, `backwards-state-write`, `unmemoized-derived-collection`, `coroutine-in-composition`, `flow-operator-in-composition`, `mutable-collection-in-state`, `collect-as-state-not-lifecycle-aware`, `unremembered-object`, `composition-local-naming`, `immutable-annotation-with-var`, `unstable-type-param`, `mutable-state-param`, `mutable-class-param` |
| Convenções de Modifier | `references/modifier-conventions.md` | findings: `modifier-param-missing`, `modifier-param-no-default`, `modifier-param-wrong-name`, `modifier-reused`, `modifier-composed-deprecated`, `multiple-modifier-params`, `modifier-chain-order-risk` |
| Naming e forma de API | `references/naming-and-api-shape.md` | findings: `composable-naming`, `event-callback-naming`, `param-ordering`, `multiple-content-emitters`, `preview-naming-visibility`, `composable-emit-and-return`, `content-slot-param-naming`, `event-trailing-lambda`, `scaffold-padding-ignored`, `boxwithconstraints-unused-scope`, `animatedcontent-unused-target`, `composable-annotation-naming`, `preview-annotation-naming`, `material2-usage`, `material3-deprecated-divider` |
| Arquitetura ViewModel | `references/viewmodel-architecture.md` | findings: `viewmodel-param-forwarding`, `viewmodel-injection-in-leaf`, `viewmodel-exposes-compose-state`, `viewmodel-multiple-state-holders` — as duas últimas analisam o corpo da classe `ViewModel` diretamente, não uma função `@Composable` (ver nota de implementação no arquivo) |
| Performance de listas preguiçosas | `references/lazy-list-performance.md` | findings: `lazy-items-missing-key`, `lazy-items-missing-content-type`, `lazy-item-modifier-not-hoisted` — nenhuma das três tem cobertura em Android Lint/ktlint/detekt hoje; abra este arquivo sempre que o scanner reportar algum desses findings, mesmo que ferramentas externas não tenham achado nada |
| Acessibilidade | `references/accessibility.md` | findings: `image-missing-content-description`, `empty-content-description`, `touch-target-too-small`, `null-content-description-clickable`, `clickable-without-semantics` — checagens próprias inspiradas no guia oficial de acessibilidade do Compose (sem lint dedicado habilitado por padrão) |
| Theming Material 3 | `references/material3-theming.md` | findings: `material3-hardcoded-color` — cor fixa (`Color(...)`/`Color.Red` etc.) em vez de token de `MaterialTheme.colorScheme`; pula composables `@Preview` e o composable que define o próprio `ColorScheme` do app (nome terminando em `Theme`, ou corpo com `lightColorScheme`/`darkColorScheme`/`dynamicLightColorScheme`/`dynamicDarkColorScheme`). `material3-hardcoded-typography` — `Text(...)` com `fontSize`/`fontFamily` inline em vez de `style = MaterialTheme.typography.*`; pula quando deriva de `MaterialTheme.typography` via `.copy(...)`. Ambas checagens próprias, sem lint dedicado |
| Interação e foco | `references/interaction-and-focus.md` | findings: `interaction-source-in-clickable` — composable que tem `Card`/`Surface`/`Modifier.clickable` (com `onClick`) mas observa interação via `Modifier.onFocusEvent` em vez de `MutableInteractionSource` (passado ao componente como `interactionSource`); `onFocusEvent` em `Card`/`Surface` não dispara sem `Modifier.focusable()` na chain. `interaction-source-manual-collect` — `.interactions.collect { }` manual que só distingue eventos de um único eixo (press/foco/drag/hover), quando um `collectIsXAsState()` declarativo resolveria. `interaction-source-not-hoisted` — `MutableInteractionSource()` criado internamente num composable com parâmetro de callback (wrapper reutilizável) em vez de recebido via parâmetro hoisted. `interaction-source-callback-not-stable` — parâmetro de callback referenciado dentro de um `LaunchedEffect` que observa interação, sem `rememberUpdatedState` nem ser key do effect (risco de stale closure). Todas com severidade `info` (detecção de intenção é frágil). Checagens próprias, sem lint dedicado |
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
