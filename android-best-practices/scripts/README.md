# scripts/

Ferramentas de apoio ao skill `android-best-practices`. Nenhuma delas depende de
configuração de build do projeto-alvo (sem necessidade de `build.gradle*`, Android SDK
ou Gradle montado) — todas operam diretamente sobre arquivos `.kt`/`.java`/
`AndroidManifest.xml`. Não há dependências externas além de `python3` (stdlib apenas) e,
opcionalmente, `bash` + ktlint/detekt já instalados no ambiente (ou baixáveis via
`install_external_linters.sh`).

## Ordem de uso

1. **`scan_android_best_practices.py`** — ferramenta principal. Varre um arquivo
   `.kt`/`.java`/`AndroidManifest.xml` ou um diretório inteiro (recursivo) e roda as
   checagens definidas em `checks/*.py`, retornando findings em JSON ou texto:

   ```bash
   python3 scan_android_best_practices.py --path caminho/para/Arquivo.kt
   python3 scan_android_best_practices.py --path caminho/para/modulo/ --format json
   python3 scan_android_best_practices.py --path caminho/para/modulo/ --topics coroutines-and-threading,security-and-manifest
   ```

2. **`try_external_linters.sh`** *(opcional)* — se o ambiente já tiver `ktlint` e/ou
   `detekt`/`detekt-cli` instalados de forma standalone (no `PATH`, ou no cache local
   deste skill — ver item 3), esse script os roda diretamente contra o mesmo caminho
   usando só as regras built-in de cada um (nenhum plugin de terceiros é necessário
   aqui — ver "Por que não Android Lint" abaixo). Nunca falha o fluxo principal: se nada
   estiver instalado, sugere o comando de instalação e sai com status 0.

   ```bash
   ./try_external_linters.sh caminho/para/modulo/
   ```

3. **`install_external_linters.sh`** *(opcional, requer confirmação explícita)* — baixa
   ktlint e/ou detekt-cli standalone para um cache local do usuário
   (`~/.cache/android-best-practices/tools/`) — nunca toca no projeto-alvo. **Nunca
   baixa nada sem a flag `--yes`** (sem ela, só mostra o que faria — dry-run). Baixar e
   executar um binário de terceiros é uma ação com risco real: sempre confirme
   explicitamente com quem pediu a análise antes de rodar com `--yes`.

   ```bash
   ./install_external_linters.sh                    # dry-run, não baixa nada
   ./install_external_linters.sh --yes               # instala ktlint + detekt
   ./install_external_linters.sh --only ktlint --yes
   ```

## Como o `scan_android_best_practices.py` funciona

É um heurístico textual, não um parser Kotlin/Java/XML completo:

1. Localiza classes cujo supertipo direto (escrito no próprio arquivo) bate com
   `ViewModel`/`Activity`/`Fragment` (`find_android_classes`), capturando assinatura de
   construtor, corpo e offset de linha — mesma técnica de profundidade de
   chaves/parênteses (`find_matching`) usada no skill irmão `jetpack-compose-refactor`
   para ignorar delimitadores dentro de strings/comentários.
2. Localiza também blocos `object { ... }`/`companion object { ... }`
   (`find_object_blocks`), usados só pela checagem `static-field-leaks-context`.
3. AndroidManifest.xml é tratado à parte: `security_and_manifest.run_manifest` usa
   `xml.parsers.expat` diretamente (não `xml.etree.ElementTree.XMLParser` — o
   acelerador C do `ElementTree` não expõe o parser Expat subjacente de forma estável
   entre versões do Python, então não dá pra recuperar `CurrentLineNumber` através
   dele; `expat` puro contorna isso mantendo tudo em stdlib) para construir uma árvore
   mínima anotada com número de linha por elemento.
4. Cada módulo em `checks/` roda contra essas representações via `run_class(cls)`
   (AndroidClass), `run_object(obj)` (ObjectBlock), `run_file(text, file_path, offsets)`
   (qualquer `.kt`/`.java`, independente de reconhecer uma classe) ou
   `run_manifest(text, file_path)` (só em `security_and_manifest.py`). Todos devolvem
   findings crus `{file, line, checkId, message}`.
5. `rule_topic_map.json` enriquece cada finding com `topic` (para saber qual
   `references/*.md` consultar), `severity`, e `mirrors` (qual regra real de Android
   Lint/detekt inspirou aquela checagem, quando existe uma — ver nota de honestidade
   abaixo).

Limitações conhecidas, documentadas também no docstring do próprio script:

- Classes só são reconhecidas como Activity/Fragment/ViewModel pelo nome literal do
  supertipo escrito na própria declaração — sem resolução de herança indireta entre
  arquivos. `Service`/`BroadcastReceiver`/`Application` deliberadamente **não** viram um
  "kind" de classe reconhecido (o sufixo é comum demais em nomes de classes de domínio
  não relacionadas ao Android — ex.: `PaymentService`, `NotificationReceiver` genéricos —
  para servir de heurística confiável); checagens sobre esses componentes vivem só no
  manifest, onde a tag XML já desambigua sem ambiguidade nenhuma.
- Checagens por regex sobre texto inteiro do arquivo (`!!`, `printStackTrace()`, blocos
  `catch`, `GlobalScope`, strings hardcoded etc.) não distinguem uma ocorrência dentro de
  uma string literal ou comentário de uma ocorrência real de código — raro na prática,
  mas existe.
- `static-field-leaks-context`/`viewmodel-holds-android-ui-reference` sinalizam pelo
  **tipo declarado**, não pelo valor real atribuído — uma propriedade `Context` que na
  prática sempre recebe `.applicationContext` (seguro de reter) ainda é sinalizada,
  porque o scanner não faz análise de fluxo de dados. Confirme a origem do valor antes
  de "corrigir" um finding destes.
- Manifest malformado (erro de XML) faz `run_manifest` retornar lista vazia
  silenciosamente — degradação graciosa, não é um erro do scanner.

## Por que não Android Lint

Diferente de ktlint/detekt, o Android Lint real não tem um instalador standalone leve —
rodá-lo de verdade exige o Android SDK cmdline-tools completo (`sdkmanager` + aceitar
licenças + vários gigabytes) ou um projeto Gradle com o Android Gradle Plugin já
configurado, nenhum dos dois compatível com a filosofia deste skill de funcionar sem
infraestrutura de build montada. Por isso `try_external_linters.sh`/
`install_external_linters.sh` só cobrem ktlint/detekt: onde uma checagem deste skill
espelha um Android Lint issue ID real (`AllowBackup`, `StaticFieldLeak`,
`HardcodedText` etc.), o campo `mirrors` em `rule_topic_map.json` documenta isso como
proveniência **não verificada neste ambiente** — diferente do skill irmão
`jetpack-compose-refactor`, onde os IDs de ktlint/detekt foram confirmados rodando as
ferramentas de verdade contra fixtures. Se o projeto-alvo já tiver `./gradlew lint`
configurado, rodá-lo de forma oportunista (nunca obrigatória) é uma boa forma de
corroborar os findings de `security-and-manifest`/`context-and-lifecycle-leaks`
especificamente — ver `SKILL.md`, passo 3.

## Degradação graciosa

- Se o caminho passado não existir: `scan_android_best_practices.py` sai com status 2 e
  mensagem em stderr.
- Se nenhum arquivo relevante for encontrado, ou nenhuma checagem disparar: retorna
  lista vazia (`[]` em JSON, ou "Nenhum finding encontrado." em texto) — não é um erro.
- `try_external_linters.sh` sempre sai com status 0, mesmo sem ktlint/detekt instalados.
- `install_external_linters.sh` sem `--yes` nunca baixa nada (dry-run) e sai com status 0.
- Nenhum desses scripts modifica arquivos do projeto-alvo — apenas leem e reportam (ou,
  no caso de `install_external_linters.sh`, escrevem só dentro do cache local do
  usuário). Quem aplica as refatorações é o agente, seguindo `SKILL.md` e
  `references/*.md`.

## Estrutura

```
scripts/
├── scan_android_best_practices.py  # CLI principal
├── try_external_linters.sh         # corroboração opcional (best-effort)
├── install_external_linters.sh     # instalação opcional (requer --yes explícito)
├── rule_topic_map.json             # checkId -> topic/severity/references/examples/mirrors
└── checks/
    ├── __init__.py                 # utilidades compartilhadas (parsing de chaves, findings)
    ├── security_and_manifest.py
    ├── context_and_lifecycle.py
    ├── coroutines_and_threading.py
    ├── error_handling_and_null_safety.py
    ├── resource_and_ui_hygiene.py
    └── architecture_and_di.py
```
