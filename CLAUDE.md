# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Propósito do repositório

Este é um repositório de **skills** do Claude Code: cada diretório de nível superior é uma skill autocontida, invocada via um `SKILL.md`. Atualmente contém uma única skill, `jetpack-compose-refactor`, que refatora código de UI Jetpack Compose / Compose Multiplatform seguindo boas práticas de mercado (checagens do Android Lint para Compose, ktlint compose-rules, detekt compose-rules) usando um scanner heurístico próprio, sem exigir que o projeto-alvo tenha nenhuma dessas ferramentas configurada.

## Comandos

Todos os comandos abaixo rodam a partir de `jetpack-compose-refactor/scripts/`.

```bash
# Roda o scanner contra um arquivo ou diretório (recursivo)
python3 scan_compose_components.py --path <arquivo-ou-dir> --format json
python3 scan_compose_components.py --path <arquivo-ou-dir>              # saída em texto
python3 scan_compose_components.py --path <arquivo-ou-dir> --topics modifier-conventions,state-and-recomposition

# Corrobora os findings com ktlint/detekt reais, se instalados localmente ou no PATH (nunca quebra o fluxo)
./try_external_linters.sh <arquivo-ou-dir>

# Instala ktlint/detekt-cli + jars do compose-rules em ~/.cache/jetpack-compose-refactor/tools/
# Dry-run por padrão; só baixa de fato com --yes (exige confirmação explícita do usuário antes)
./install_external_linters.sh --yes
```

Não há build, manifesto de pacote nem suíte de testes neste repositório — o scanner é Python 3 puro-stdlib (`argparse`, `re`, `dataclasses`, `pathlib`), e a corretude é validada rodando-o contra fixtures `.kt` reais e inspecionando os findings em JSON, não via testes unitários.

## Arquitetura

### Contrato da skill

Toda refatoração feita por esta skill deve ser rastreável a um finding concreto do scanner — nunca introduza mudanças estilísticas só porque "parecem melhores", e nunca reporte algo como problema se o scanner não o sinalizou. Isso mantém a saída do scanner como fonte única de verdade e garante diffs revisáveis e reprodutíveis (mesmo código de entrada → mesmos findings de saída, sempre).

### Pipeline do scanner (`scripts/scan_compose_components.py`)

1. **Descoberta**: localiza cada `@Composable fun Nome(...)` (incluindo genéricos `fun <T> Nome(...)`) nos arquivos `.kt` alvo, capturando assinatura, lista de parâmetros e — quando o corpo é um bloco `{ ... }` — o texto do corpo via um contador de profundidade de chaves que ignora chaves dentro de strings/comentários. Composables com corpo em forma de expressão (`fun Foo() = ...`) só passam pelas checagens baseadas em assinatura; não há corpo para varrer.
2. Também localiza classes `class Nome(...) : ...ViewModel...` (androidx `ViewModel`, `AndroidViewModel`, ou uma base própria como `BaseViewModel`, via `find_viewmodel_classes`) — o único caminho que analisa o corpo de uma classe em vez de uma função composable, usado só pelas duas checagens de nível de classe em `viewmodel_architecture.py` (`viewmodel-exposes-compose-state`, `viewmodel-multiple-state-holders`), via `run_class(cls)` em vez do `run(fn)` usado por todas as outras checagens.
3. Computa dois contextos de nível de arquivo além das varreduras por-declaração: `find_unstable_classes` (propriedades `var` no construtor, injetadas em `ComposableFunction.sibling_unstable_classes` para a checagem `mutable-class-param`) e os imports do arquivo (para `material2-usage`).
4. Cada módulo em `scripts/checks/` roda contra essas representações via `run(fn)` / `run_class(cls)`, e alguns também expõem `run_file(text, file_path, offsets)` para checagens de nível de arquivo que não vivem dentro de um único composable (naming de CompositionLocal, `@Immutable`+`var`, naming de annotation classes, uso de Material 2). Todos devolvem findings crus `{file, line, checkId, message}`.
5. `scripts/rule_topic_map.json` é a fonte de verdade que enriquece cada finding cru com `topic` (qual `references/*.md` consultar), `severity`, e `mirrors` (qual regra real de Android Lint/ktlint/detekt aquela checagem espelha, quando existe).

Limitações heurísticas conhecidas (documentadas no docstring do script e em `scripts/README.md`): não é um parser Kotlin real, então composables com corpo em forma de expressão pulam as checagens baseadas em corpo; genéricos aninhados combinados com tipos função (`Map<String, () -> Unit>`) podem confundir a separação de parâmetros; "emissores de UI no nível raiz" e "reuso de Modifier" são heurísticas textuais, não uma análise de fluxo de dados real; `find_viewmodel_classes`/`find_unstable_classes` reconhecem pelo nome literal do supertipo escrito no próprio arquivo, sem resolver herança entre arquivos.

### Módulos de checagem (`scripts/checks/`)

Sete módulos por tópico (`state_and_recomposition.py`, `modifier_conventions.py`, `naming_and_api_shape.py`, `viewmodel_architecture.py`, `lazy_list_performance.py`, `accessibility.py`, `material3_theming.py`, `interaction_and_focus.py`), cada um expondo `run(fn)`/`run_class(cls)`/`run_file(...)` conforme aplicável. `checks/__init__.py` guarda utilidades compartilhadas: `find_matching` (casamento de chaves/parênteses que ignora strings/comentários), `build_line_offsets`/`line_number`, e `EMITTING_COMPOSABLES` (o conjunto de nomes de funções emissoras de UI do Compose conhecidas, usado por várias heurísticas).

### Workflow em nível de skill (ver `jetpack-compose-refactor/SKILL.md` para o detalhe completo)

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
