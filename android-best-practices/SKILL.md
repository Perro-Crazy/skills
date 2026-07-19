---
name: android-best-practices
description: Analisa e refatora código Android (Kotlin/Java + AndroidManifest.xml) em direção a boas práticas gerais de mercado — segurança de manifest e segredos, vazamento de Context/View/Handler, uso de coroutines, tratamento de exceção e null-safety, higiene de recursos, e separação de camadas (ViewModel/UI/dados) — guiado por um scanner heurístico próprio que espelha checagens conhecidas de Android Lint e do ruleset padrão do detekt, sem exigir que o projeto-alvo tenha nenhuma dessas ferramentas configurada. Use quando o usuário pedir para revisar, auditar ou corrigir boas práticas gerais de um app Android; investigar vazamento de memória/Context; revisar AndroidManifest.xml por segurança; modernizar uso de coroutines/AsyncTask; ou limpar tratamento de exceção, segredos hardcoded, strings/cores fora de recurso. Para refatoração específica de Jetpack Compose (state hoisting, Modifier, recomposição), use o skill irmão `jetpack-compose-refactor` em vez deste.
version: 0.1.0
---

# Android Best Practices

Analisa e refatora código Android (Kotlin/Java + `AndroidManifest.xml`) seguindo boas
práticas gerais de mercado — segurança de manifest, vazamento de memória por
Context/View/Handler, uso de coroutines, tratamento de exceção, higiene de recursos e
separação de camadas — guiado por um scanner próprio que espelha checagens conhecidas de
Android Lint e do ruleset padrão do detekt, sem depender de nenhuma das duas estar
configurada no projeto-alvo. Não cobre Jetpack Compose especificamente — para isso, use
o skill irmão `jetpack-compose-refactor`.

## Filosofia

Toda refatoração feita por este skill deve ser rastreável a um finding concreto do
scanner (`scripts/scan_android_best_practices.py`). Nunca introduza mudanças
estilísticas soltas só porque "parecem melhores", e nunca reporte como "problema
encontrado" algo que não veio do scanner — se não há um finding, não é escopo desta
análise. Isso mantém os diffs revisáveis, evita misturar refactor com gosto pessoal, e
garante que rodar o scanner duas vezes no mesmo código sempre produz a mesma lista de
problemas (o script já é determinístico).

Ler o código-fonte é permitido e esperado, mas só para **confirmar ou descartar** um
finding do scanner antes de aplicar a correção (ver limitações conhecidas do parser
heurístico, seção "Não confie cegamente no scanner" mais abaixo) — nunca para
"descobrir" problemas adicionais por conta própria. Isso importa especialmente aqui:
várias checagens deste skill (`static-field-leaks-context`,
`viewmodel-holds-android-ui-reference`, `hardcoded-secret-literal`) sinalizam pelo
**tipo/nome declarado**, não pelo valor real em runtime — confirmar antes de corrigir
não é opcional, é como esses findings específicos devem ser tratados sempre. Se, lendo
o código, você notar algo que parece um problema real mas não tem finding
correspondente, não o inclua na lista de problemas nem aplique a correção — trate como
observação e siga o passo opcional "Revisão manual" abaixo.

## Workflow

### 1. Resolver o alvo e o modo

O alvo pode ser um arquivo específico (`.kt`/`.java`/`AndroidManifest.xml`), uma lista
de classes/arquivos citados pelo usuário, ou um diretório/raiz de projeto inteiro a
varrer recursivamente — os três modos são suportados igualmente pelo scanner. Se o
usuário não deixar claro qual dos dois quer, pergunte antes de escolher um escopo
grande por conta própria.

Além do alvo, há dois **modos de operação**:

- **Aplicação (padrão)** — as refatorações são escritas direto nos arquivos conforme o
  passo 5 avança.
- **Sugestão** — nenhum arquivo é tocado; para cada finding, proponha o diff (antes/depois)
  e pare, aguardando o usuário aprovar quais aplicar. Use este modo quando o usuário
  pedir explicitamente algo como "só sugere", "não edita ainda", "me mostra antes de
  aplicar" — ou sempre que o escopo for grande o bastante (muitos arquivos/findings) que
  aplicar tudo de uma vez sem revisão prévia seria arriscado; nesse caso, pergunte qual
  modo o usuário prefere em vez de assumir aplicação direta. **Prefira sugestão por
  padrão** para findings do tópico `security-and-manifest` especificamente (ver seção
  "O que sempre perguntar antes de fazer" abaixo) — mudanças de manifest afetam
  segurança do app e merecem revisão explícita mesmo em modo aplicação geral.

O modo escolhido vale para toda a sessão de análise corrente; não alterne entre os dois
modos no meio do processo sem o usuário pedir.

### 2. Rodar o scanner

```bash
python3 scripts/scan_android_best_practices.py --path <alvo> --format json
```

Isso produz uma lista de findings, cada um já com `topic`, `severity`, `mirrors` (qual
regra real de linter/guia oficial aquela checagem espelha, quando existe) e o
`referencesFile`/`examplesFile` a consultar. O scanner reconhece `AndroidManifest.xml`
pelo nome de arquivo exato e classes Activity/Fragment/ViewModel pelo nome do supertipo
— não precisa (e não deve tentar) rodar `./gradlew lint`/`detekt` do projeto-alvo para
esta etapa; esse scanner é a fonte primária e funciona mesmo sem nenhum Gradle
configurado, inclusive contra uma pasta solta de `.kt`/`.java`.

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

`install_external_linters.sh --yes` baixa ktlint/detekt-cli (regras built-in, sem
plugin extra necessário aqui) para um cache local do usuário
(`~/.cache/android-best-practices/tools/`) — nunca toca no projeto-alvo, e as versões
baixadas são fixas (ver constantes no topo do script), então o resultado é reproduzível
entre execuções. Esse download roda uma única vez por máquina; runs seguintes já
encontram tudo em cache e pulam direto para `try_external_linters.sh`.

Nem ktlint nem detekt reproduzem as checagens Android-específicas deste skill
(manifest, Context leaks, arquitetura) — eles só corroboram o subconjunto com
equivalente genérico Kotlin (ver `references/detekt-glossary.md`). Se o projeto-alvo já
tiver `./gradlew lint` configurado, rodá-lo de forma **oportunista** (nunca obrigatória
— nunca configure isso do zero num projeto que não o tenha) corrobora com mais
fidelidade os tópicos `security-and-manifest` e `context-and-lifecycle-leaks`
especificamente.

Nunca bloqueia o fluxo principal do skill: mesmo que o download falhe (rede
indisponível, etc.), siga em frente com os findings do scanner só. A saída de
`try_external_linters.sh` é bruta, direto do stdout de cada ferramenta — não é fundida
com o JSON do scanner (ver passo 8, ela vai numa seção própria do relatório).

### 4. Carregar as referências relevantes

Para cada tópico com findings, abra **apenas** o `references/*.md` correspondente
(tabela abaixo) — não carregue todos de uma vez. Cada arquivo de referência explica o
racional completo, o que o real linter/guia oficial checaria (`mirrors`), e aponta para
o `examples/*.md` com o padrão antes/depois correspondente.

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
- Se uma refatoração mudou a assinatura pública de uma classe/construtor (ex.: remover
  o parâmetro `Context` de um `ViewModel` para resolver
  `viewmodel-holds-android-ui-reference` muda quem instancia esse ViewModel), avise
  isso explicitamente no resumo — é uma mudança visível para quem consome, não algo
  para passar despercebido.
- Se uma refatoração tocou `AndroidManifest.xml` (qualquer finding do tópico
  `security-and-manifest`), resuma explicitamente **o que mudou e o efeito de
  segurança/comportamento** (ex.: "componente X deixou de ser alcançável por outros
  apps do dispositivo") — não deixe essa mudança implícita dentro de uma lista genérica
  de findings corrigidos.

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
   "`hardcoded-secret-literal` em `ApiClient.apiKey` exigiria decidir onde mover o
   segredo — não movi sem confirmar o mecanismo com o usuário, ver seção abaixo"). Essa
   lista é a mesma se o scanner rodar de novo no mesmo código.
2. **Corroboração externa (ktlint/detekt, saída bruta do passo 3)** — sempre inclua, já
   que o passo 3 agora é obrigatório; se nenhuma ferramenta estava disponível e o
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
| Segurança e manifest | `references/security-and-manifest.md` | findings: `manifest-allow-backup-enabled`, `manifest-debuggable-enabled`, `manifest-cleartext-traffic-enabled`, `manifest-component-exported-without-permission`, `hardcoded-secret-literal`, `hardcoded-http-url` |
| Context, View e vazamentos de ciclo de vida | `references/context-and-lifecycle-leaks.md` | findings: `static-field-leaks-context`, `fragment-view-binding-not-cleared`, `handler-inner-class-leak`, `livedata-observeforever-not-removed` |
| Coroutines e threading | `references/coroutines-and-threading.md` | findings: `globalscope-launch-usage`, `runblocking-outside-tests`, `viewmodel-manual-coroutinescope`, `asynctask-subclass-deprecated` |
| Tratamento de exceção e null-safety | `references/error-handling-and-null-safety.md` | findings: `not-null-assertion-operator`, `empty-catch-block`, `generic-exception-caught`, `swallowed-exception`, `printstacktrace-usage` |
| Recursos e higiene de UI | `references/resource-and-ui-hygiene.md` | findings: `hardcoded-user-facing-string`, `hardcoded-hex-color`, `println-instead-of-log` |
| Arquitetura e separação de camadas | `references/architecture-and-di.md` | findings: `viewmodel-holds-android-ui-reference`, `ui-layer-instantiates-network-or-db-client` |
| Glossário Android Lint | `references/android-lint-glossary.md` | proveniência — qual regra real de Android Lint cada checagem espelha (não executado neste ambiente, ver o próprio arquivo) |
| Glossário detekt | `references/detekt-glossary.md` | proveniência — qual regra real de detekt cada checagem espelha |

## Índice de scripts

- `scripts/scan_android_best_practices.py` — scanner principal (ver `scripts/README.md`
  para uso detalhado e limitações conhecidas do parser heurístico).
- `scripts/try_external_linters.sh` — corroboração opcional via ktlint/detekt
  standalone (PATH ou cache local), se disponíveis no ambiente.
- `scripts/install_external_linters.sh` — instala ktlint/detekt-cli no cache local do
  usuário; **dry-run por padrão**, só baixa de fato com `--yes` explícito.
- `scripts/rule_topic_map.json` — fonte de verdade mapeando cada `checkId` a
  tópico/severidade/arquivo de referência/exemplo/regra espelhada.

Não confie cegamente no scanner em casos extremos: ele não é um parser Kotlin/Java/XML
completo (ver limitações documentadas no topo de `scan_android_best_practices.py`) —
em particular, `static-field-leaks-context`, `viewmodel-holds-android-ui-reference` e
`hardcoded-secret-literal` sinalizam pelo **tipo/nome declarado**, não pelo valor real
em runtime, então falsos positivos existem (ex.: um campo `Context` que sempre recebe
`.applicationContext`, seguro de reter). Sempre leia o código real antes de aplicar uma
refatoração baseada só no texto de um finding.

## O que sempre perguntar antes de fazer

- **Qualquer edição em `AndroidManifest.xml`** — mesmo resolvendo um finding real do
  tópico `security-and-manifest`, mudanças de manifest afetam segurança/comportamento
  visível do app (o que fica exportado, o que aceita tráfego não criptografado, o que é
  incluído em backup) e merecem confirmação explícita antes de escrever, mesmo em modo
  aplicação — prefira mostrar o diff proposto e perguntar, nunca aplique
  silenciosamente uma mudança de manifest junto com um lote maior de outras
  refatorações.
- **Mover ou introduzir um mecanismo novo para segredos** (`hardcoded-secret-literal`)
  — proponha o destino (BuildConfig/local.properties, um secrets manager específico) e
  confirme com o usuário antes de mover; não presuma qual mecanismo o time já usa ou
  prefere.
- **Adicionar uma dependência nova** ao projeto-alvo (ex.: um framework de DI para
  resolver `ui-layer-instantiates-network-or-db-client`) — proponha a alternativa sem
  dependência nova primeiro (um container manual simples), e só adicione a dependência
  se o usuário confirmar que quer isso.
- **Editar `build.gradle*`/version catalogs** do projeto-alvo por qualquer motivo,
  incluindo configurar detekt/ktlint — este skill deliberadamente não depende disso
  para funcionar, e mudar configuração de build/CI é uma decisão que afeta o time todo.
- **Mudar a assinatura pública de uma classe/construtor** (parâmetros
  adicionados/removidos, ex.: tirar `Context` de um `ViewModel`) — sinalize antes de
  aplicar quando a mudança afeta quem instancia essa classe fora do arquivo sendo
  refatorado.
