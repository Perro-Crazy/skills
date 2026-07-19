# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Propósito do repositório

Este é um repositório de **skills** do Claude Code: cada diretório de nível superior é uma skill autocontida, invocada via um `SKILL.md`. Contém duas skills, ambas seguindo o mesmo padrão de arquitetura documentado em `ARCHITECTURE.md` ("scanner heurístico próprio + refatoração rastreável a findings", sem exigir que o projeto-alvo tenha nenhuma ferramenta real configurada):

- **`jetpack-compose-refactor`** — refatora código de UI Jetpack Compose / Compose Multiplatform seguindo boas práticas de mercado (checagens do Android Lint para Compose, ktlint compose-rules, detekt compose-rules).
- **`android-best-practices`** — analisa/refatora Android em geral, fora do escopo de Compose: segurança de `AndroidManifest.xml` e segredos hardcoded, vazamento de memória por Context/View/Handler, uso de coroutines, tratamento de exceção/null-safety, higiene de recursos, e separação de camadas (ViewModel/UI/dados), espelhando checagens conhecidas de Android Lint e do ruleset padrão do detekt.

Leia `ARCHITECTURE.md` antes de criar uma terceira skill deste padrão (ex.: para SwiftUI, React, outro ecossistema) — ele generaliza as decisões de design tomadas nas duas skills existentes.

## Comandos

### jetpack-compose-refactor

Rodam a partir de `jetpack-compose-refactor/scripts/`.

```bash
# Roda o scanner contra um arquivo ou diretório (recursivo)
python3 scan_compose_components.py --path <arquivo-ou-dir> --format json
python3 scan_compose_components.py --path <arquivo-ou-dir>              # saída em texto
python3 scan_compose_components.py --path <arquivo-ou-dir> --topics modifier-conventions,state-and-recomposition

# Corrobora os findings com ktlint/detekt reais (+ ruleset compose-rules), se instalados localmente ou no PATH (nunca quebra o fluxo)
./try_external_linters.sh <arquivo-ou-dir>

# Instala ktlint/detekt-cli + jars do compose-rules em ~/.cache/jetpack-compose-refactor/tools/
# Dry-run por padrão; só baixa de fato com --yes (exige confirmação explícita do usuário antes)
./install_external_linters.sh --yes
```

### android-best-practices

Rodam a partir de `android-best-practices/scripts/`. Mesma forma de uso, alvo pode incluir `AndroidManifest.xml` além de `.kt`/`.java`; a corroboração externa usa ktlint/detekt só com regras built-in (sem ruleset de terceiros — ver `android-best-practices/scripts/README.md` para o porquê de Android Lint em si não fazer parte deste par de scripts).

```bash
python3 scan_android_best_practices.py --path <arquivo-ou-dir> --format json
./try_external_linters.sh <arquivo-ou-dir>
./install_external_linters.sh --yes   # cache em ~/.cache/android-best-practices/tools/
```

Não há build, manifesto de pacote nem suíte de testes neste repositório — os scanners são Python 3 puro-stdlib (`argparse`, `re`, `dataclasses`, `pathlib`, e `xml.parsers.expat` no caso de `android-best-practices`), e a corretude é validada rodando-os contra fixtures `.kt`/`.xml` reais e inspecionando os findings em JSON, não via testes unitários.

## Arquitetura

### Contrato das skills

Toda refatoração feita por qualquer skill deste repositório deve ser rastreável a um finding concreto do scanner — nunca introduza mudanças estilísticas só porque "parecem melhores", e nunca reporte algo como problema se o scanner não o sinalizou. Isso mantém a saída do scanner como fonte única de verdade e garante diffs revisáveis e reprodutíveis (mesmo código de entrada → mesmos findings de saída, sempre).

### jetpack-compose-refactor

#### Pipeline do scanner (`scripts/scan_compose_components.py`)

1. **Descoberta**: localiza cada `@Composable fun Nome(...)` (incluindo genéricos `fun <T> Nome(...)`) nos arquivos `.kt` alvo, capturando assinatura, lista de parâmetros e — quando o corpo é um bloco `{ ... }` — o texto do corpo via um contador de profundidade de chaves que ignora chaves dentro de strings/comentários. Composables com corpo em forma de expressão (`fun Foo() = ...`) só passam pelas checagens baseadas em assinatura; não há corpo para varrer.
2. Também localiza classes `class Nome(...) : ...ViewModel...` (androidx `ViewModel`, `AndroidViewModel`, ou uma base própria como `BaseViewModel`, via `find_viewmodel_classes`) — o único caminho que analisa o corpo de uma classe em vez de uma função composable, usado só pelas duas checagens de nível de classe em `viewmodel_architecture.py` (`viewmodel-exposes-compose-state`, `viewmodel-multiple-state-holders`), via `run_class(cls)` em vez do `run(fn)` usado por todas as outras checagens.
3. Computa dois contextos de nível de arquivo além das varreduras por-declaração: `find_unstable_classes` (propriedades `var` no construtor, injetadas em `ComposableFunction.sibling_unstable_classes` para a checagem `mutable-class-param`) e os imports do arquivo (para `material2-usage`).
4. Cada módulo em `scripts/checks/` roda contra essas representações via `run(fn)` / `run_class(cls)`, e alguns também expõem `run_file(text, file_path, offsets)` para checagens de nível de arquivo que não vivem dentro de um único composable (naming de CompositionLocal, `@Immutable`+`var`, naming de annotation classes, uso de Material 2). Todos devolvem findings crus `{file, line, checkId, message}`.
5. `scripts/rule_topic_map.json` é a fonte de verdade que enriquece cada finding cru com `topic` (qual `references/*.md` consultar), `severity`, e `mirrors` (qual regra real de Android Lint/ktlint/detekt aquela checagem espelha, quando existe).

Limitações heurísticas conhecidas (documentadas no docstring do script e em `scripts/README.md`): não é um parser Kotlin real, então composables com corpo em forma de expressão pulam as checagens baseadas em corpo; genéricos aninhados combinados com tipos função (`Map<String, () -> Unit>`) podem confundir a separação de parâmetros; "emissores de UI no nível raiz" e "reuso de Modifier" são heurísticas textuais, não uma análise de fluxo de dados real; `find_viewmodel_classes`/`find_unstable_classes` reconhecem pelo nome literal do supertipo escrito no próprio arquivo, sem resolver herança entre arquivos.

#### Módulos de checagem (`scripts/checks/`)

Sete módulos por tópico (`state_and_recomposition.py`, `modifier_conventions.py`, `naming_and_api_shape.py`, `viewmodel_architecture.py`, `lazy_list_performance.py`, `accessibility.py`, `material3_theming.py`, `interaction_and_focus.py`), cada um expondo `run(fn)`/`run_class(cls)`/`run_file(...)` conforme aplicável. `checks/__init__.py` guarda utilidades compartilhadas: `find_matching` (casamento de chaves/parênteses que ignora strings/comentários), `build_line_offsets`/`line_number`, e `EMITTING_COMPOSABLES` (o conjunto de nomes de funções emissoras de UI do Compose conhecidas, usado por várias heurísticas).

#### Workflow em nível de skill (ver `jetpack-compose-refactor/SKILL.md` para o detalhe completo)

1. Resolver o escopo do alvo (arquivo único, composables citados, ou diretório inteiro) — perguntar antes de escanear um escopo grande se houver ambiguidade.
2. Rodar o scanner (comando acima).
3. Corroboração externa **obrigatória** via `try_external_linters.sh`, instalando as ferramentas automaticamente via `install_external_linters.sh --yes` se estiverem ausentes (sem precisar de confirmação para esse passo específico de instalação — isso já é uma parte documentada e deliberada do workflow).
4. Carregar apenas os `references/*.md` relevantes aos tópicos com findings (ver a tabela de tópicos em `SKILL.md`) — não carregar todos de uma vez.
5. Aplicar as refatorações incrementalmente, um tópico/arquivo por vez, usando o antes/depois correspondente em `examples/*.md` como modelo (não como cópia literal).
6. Verificar: re-rodar o scanner para confirmar que os findings-alvo desapareceram sem novos findings colaterais; compilar/testar de forma oportunista se houver um projeto Gradle real por trás do alvo; sinalizar explicitamente se uma refatoração mudou a assinatura pública de um composable.
7. Revisão manual além dos findings do scanner é estritamente opcional, só sob pedido explícito do usuário, e deve ser reportada separadamente como não determinística.
8. O relatório final sempre separa: (1) findings determinísticos do scanner antes/depois, (2) saída bruta da corroboração externa dos linters, (3) observações manuais, se o passo 7 tiver rodado.

Coisas que esta skill sempre deve perguntar antes de fazer: adicionar uma dependência nova ao projeto-alvo (ex.: `kotlinx-collections-immutable`), editar `build.gradle*`/version catalogs, ou mudar a assinatura pública de um composable sem sinalizar isso.

Tudo acima é o contrato de operação da própria skill, não uma orientação genérica — leia `jetpack-compose-refactor/SKILL.md` diretamente antes de fazer julgamentos não mecânicos (ex.: quando um finding é ambíguo ou a natureza heurística do scanner torna um finding suspeito).

### android-best-practices

#### Pipeline do scanner (`scripts/scan_android_best_practices.py`)

1. **Descoberta**: `find_android_classes` localiza classes cujo supertipo direto bate com `ViewModel`/`Activity`/`Fragment` (heurística por nome, sem resolução de herança entre arquivos — deliberadamente **não** classifica `Service`/`BroadcastReceiver`/`Application` por nome de classe, já que esses sufixos são comuns demais em código de domínio não-Android; checagens sobre esses componentes vivem só no manifest). `find_object_blocks` localiza `object`/`companion object { ... }`, usado só pela checagem de campo estático segurando Context.
2. `AndroidManifest.xml` é tratado à parte de `.kt`/`.java`: `security_and_manifest.run_manifest` usa `xml.parsers.expat` diretamente (não `xml.etree.ElementTree.XMLParser` — o acelerador C não expõe o parser Expat subjacente de forma estável entre versões do Python) para construir uma árvore mínima anotada com número de linha via `CurrentLineNumber`.
3. Cada módulo em `scripts/checks/` roda contra essas representações via `run_class(cls)` (AndroidClass), `run_object(obj)` (ObjectBlock), `run_file(text, file_path, offsets)` (qualquer `.kt`/`.java`) ou `run_manifest(text, file_path)` (só em `security_and_manifest.py`). Todos devolvem findings crus `{file, line, checkId, message}`.
4. `scripts/rule_topic_map.json` enriquece cada finding com `topic`, `severity`, e `mirrors` — aqui, diferente de `jetpack-compose-refactor`, nenhum `mirrors` foi confirmado rodando a ferramenta real neste ambiente (Android Lint não tem instalador standalone leve; detekt/ktlint são instaláveis via `install_external_linters.sh` mas os IDs no `rule_topic_map.json` vêm de documentação pública, não de execução — ver `references/android-lint-glossary.md`/`references/detekt-glossary.md`).

Limitações heurísticas conhecidas (documentadas no docstring do script e em `scripts/README.md`): checagens por regex sobre texto inteiro do arquivo (`!!`, `printStackTrace()`, `GlobalScope`, strings/segredos hardcoded etc.) não distinguem uma ocorrência dentro de string/comentário de código real; `static-field-leaks-context`/`viewmodel-holds-android-ui-reference`/`hardcoded-secret-literal` sinalizam pelo tipo/nome **declarado**, não pelo valor real em runtime (ex.: um campo `Context` sempre atribuído a `.applicationContext` é um falso positivo que exige confirmação humana antes de "corrigir").

#### Módulos de checagem (`scripts/checks/`)

Seis módulos por tópico (`security_and_manifest.py`, `context_and_lifecycle.py`, `coroutines_and_threading.py`, `error_handling_and_null_safety.py`, `resource_and_ui_hygiene.py`, `architecture_and_di.py`), cada um expondo `run_class`/`run_object`/`run_file`/`run_manifest` conforme aplicável. `checks/__init__.py` reaproveita a mesma técnica de `find_matching`/`build_line_offsets`/`line_number` de `jetpack-compose-refactor`.

#### Workflow em nível de skill (ver `android-best-practices/SKILL.md` para o detalhe completo)

Mesma sequência de 8 passos do `jetpack-compose-refactor` (resolver alvo/modo → rodar scanner → corroboração externa obrigatória → carregar referências → aplicar/propor → verificar → revisão manual opcional → resumir em seções separadas), com duas diferenças específicas deste domínio: (1) qualquer edição em `AndroidManifest.xml` exige confirmação explícita mesmo em modo aplicação, por afetar segurança/comportamento visível do app; (2) a corroboração externa do passo 3 não cobre Android Lint (sem instalador standalone leve — ver `scripts/README.md`), só ktlint/detekt com regras built-in.

Tudo acima é o contrato de operação da própria skill — leia `android-best-practices/SKILL.md` diretamente antes de fazer julgamentos não mecânicos.
