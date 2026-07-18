# scripts/

Ferramentas de apoio ao skill `jetpack-compose-refactor`. Nenhuma delas depende de
configuração de build do projeto-alvo (sem necessidade de `build.gradle*`, sem precisar
que detekt/ktlint/Android Lint estejam configurados) — todas operam diretamente sobre
arquivos `.kt`. Não há dependências externas além de `python3` (stdlib apenas) e,
opcionalmente, `bash` + ktlint/detekt já instalados no ambiente.

## Ordem de uso

1. **`scan_compose_components.py`** — ferramenta principal. Varre um arquivo `.kt` ou
   um diretório inteiro (recursivo) em busca de funções `@Composable` e roda as
   checagens definidas em `checks/*.py`, retornando findings em JSON ou texto:

   ```bash
   python3 scan_compose_components.py --path caminho/para/Componente.kt
   python3 scan_compose_components.py --path caminho/para/modulo/ --format json
   python3 scan_compose_components.py --path caminho/para/modulo/ --topics modifier-conventions,state-and-recomposition
   ```

2. **`try_external_linters.sh`** *(opcional)* — se o ambiente já tiver `ktlint` e/ou
   `detekt`/`detekt-cli` instalados de forma standalone (no `PATH`, ou no cache local
   deste skill — ver item 3), esse script os roda diretamente contra o mesmo caminho só
   para dar uma segunda opinião real, lida com os jars de compose-rules se conseguir
   localizá-los. Nunca falha o fluxo principal: se nada estiver instalado, sugere o
   comando de instalação e sai com status 0.

   ```bash
   ./try_external_linters.sh caminho/para/modulo/
   ```

3. **`install_external_linters.sh`** *(opcional, requer confirmação explícita)* — baixa
   ktlint e/ou detekt-cli standalone, mais os jars do ruleset compose-rules, para um
   cache local do usuário (`~/.cache/jetpack-compose-refactor/tools/`) — nunca toca no
   projeto-alvo. **Nunca baixa nada sem a flag `--yes`** (sem ela, só mostra o que faria
   — dry-run). Baixar e executar um binário de terceiros é uma ação com risco real:
   sempre confirme explicitamente com quem pediu a refatoração antes de rodar com
   `--yes`.

   ```bash
   ./install_external_linters.sh                    # dry-run, não baixa nada
   ./install_external_linters.sh --yes               # instala ktlint + detekt
   ./install_external_linters.sh --only ktlint --yes
   ```

## Como o `scan_compose_components.py` funciona

É um heurístico textual, não um parser Kotlin completo:

1. Localiza cada `@Composable fun Nome(...)` no arquivo (incluindo genéricos
   `fun <T> Nome(...)`), capturando assinatura, lista de parâmetros e — quando o
   corpo é um bloco `{ ... }` — o texto do corpo via um contador de profundidade de
   chaves que ignora chaves dentro de strings/comentários.
2. Localiza também cada `class Nome(...) : ...ViewModel...` (androidx `ViewModel`,
   `AndroidViewModel`, ou uma base própria como `BaseViewModel` — via
   `find_viewmodel_classes`), capturando o corpo da classe da mesma forma. Esse é o
   único caminho de código que analisa uma classe em vez de uma função `@Composable`
   — usado só pelas duas checagens de nível de classe em `viewmodel_architecture.py`
   (`viewmodel-exposes-compose-state`, `viewmodel-multiple-state-holders`), via
   `run_class(cls)` em vez do `run(fn)` usado por todas as outras checagens.
3. Além das duas varreduras por-declaração acima, computa dois contextos de nível de
   arquivo: `find_unstable_classes` (nomes de classes com propriedade `var` no
   construtor, injetados em cada `ComposableFunction.sibling_unstable_classes` para a
   checagem `mutable-class-param`) e os imports (para `material2-usage`).
4. Cada módulo em `checks/` roda contra essas representações (`ComposableFunction`/
   `ViewModelClass`) via `run(fn)`/`run_class(cls)`, e alguns módulos também expõem um
   `run_file(text, file_path, offsets)` para checagens de nível de arquivo que não vivem
   dentro de um composable (naming de CompositionLocal, `@Immutable`+`var`, naming de
   annotation classes, Material 2). Todos devolvem findings crus
   `{file, line, checkId, message}`.
5. `rule_topic_map.json` enriquece cada finding com `topic` (para saber qual
   `references/*.md` consultar), `severity`, e `mirrors` (qual regra real de
   Android Lint/ktlint/detekt inspirou aquela checagem, quando existe uma).

Limitações conhecidas, documentadas também no docstring do próprio script:
- Composables com corpo em forma de expressão (`fun Foo() = ...`) só passam pelas
  checagens de assinatura (naming, ordenação de parâmetros, Modifier), não pelas que
  dependem do corpo (remember, LaunchedEffect, acessibilidade, listas preguiçosas etc.).
- "Emissores de UI no nível raiz" e "reuso de Modifier" são heurísticas textuais —
  sempre revise antes de agir sobre um finding, especialmente os marcados `severity: info`.
- Genéricos aninhados combinando `<...>` com tipos função (`Map<String, () -> Unit>`)
  podem confundir a separação de parâmetros por vírgula em casos raros.
- `find_viewmodel_classes` e `find_unstable_classes` reconhecem os tipos pelo nome
  literal escrito no próprio arquivo — não resolvem herança nem tipos entre arquivos
  (uma classe instável importada de outro módulo não é detectada como parâmetro
  instável, por exemplo).

## Degradação graciosa

- Se o caminho passado não existir: `scan_compose_components.py` sai com status 2 e
  mensagem em stderr.
- Se nenhum arquivo `.kt` for encontrado, ou nenhuma checagem disparar: retorna lista
  vazia (`[]` em JSON, ou "Nenhum finding encontrado." em texto) — não é um erro.
- `try_external_linters.sh` sempre sai com status 0, mesmo sem ktlint/detekt instalados.
- `install_external_linters.sh` sem `--yes` nunca baixa nada (dry-run) e sai com
  status 0.
- Nenhum desses scripts modifica arquivos do projeto-alvo — apenas leem e reportam
  (ou, no caso de `install_external_linters.sh`, escrevem só dentro do cache local do
  usuário). Quem aplica as refatorações é o agente, seguindo `SKILL.md` e `references/*.md`.

## Nota de arquitetura: ktlint vs. detekt ao carregar o ruleset compose-rules

`io.nlopez.compose.rules:ktlint` e `io.nlopez.compose.rules:detekt` dependem de um
terceiro jar (`io.nlopez.compose.rules:common`) para classes compartilhadas. Isso foi
descoberto (e confirmado rodando as ferramentas de verdade) ao implementar
`install_external_linters.sh`:
- **detekt** carrega múltiplos jars de `--plugins` num classloader compartilhado — basta
  passar `--plugins ruleset.jar,common.jar` (separados por vírgula).
- **ktlint** isola cada jar passado via `-R` num classloader próprio — os dois jars
  **precisam** ser mesclados num único jar antes do uso (`install_external_linters.sh`
  faz isso automaticamente, gerando `compose-rules-ktlint-merged-*.jar`). Passar os dois
  jars via `-R` repetido falha com `NoClassDefFoundError` em tempo de execução.
- Além disso, o ktlint interpreta argumentos posicionais como padrões de glob estilo
  `.gitignore` relativos ao diretório de trabalho — um caminho **absoluto de diretório**
  não funciona como esperado (cai no comportamento default e tenta varrer a partir de
  `/`). Um caminho absoluto de **arquivo** funciona bem. `try_external_linters.sh` lida
  com isso automaticamente: para arquivo, passa o caminho direto; para diretório, entra
  nele (`cd`) e roda sem padrão.

## Estrutura

```
scripts/
├── scan_compose_components.py    # CLI principal
├── try_external_linters.sh       # corroboração opcional (best-effort)
├── install_external_linters.sh   # instalação opcional (requer --yes explícito)
├── rule_topic_map.json           # checkId -> topic/severity/references/examples/mirrors
└── checks/
    ├── __init__.py               # utilidades compartilhadas (parsing de chaves, findings)
    ├── state_and_recomposition.py
    ├── modifier_conventions.py
    ├── naming_and_api_shape.py
    ├── viewmodel_architecture.py
    ├── lazy_list_performance.py
    ├── accessibility.py
    └── material3_theming.py
```
