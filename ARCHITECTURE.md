# Padrão de arquitetura: skills de refatoração guiadas por scanner

Este documento generaliza o padrão de arquitetura usado em `jetpack-compose-refactor/`
para que outras skills com propósito parecido — "escanear código-fonte contra um
conjunto de boas práticas conhecidas de um ecossistema, e refatorar com base nisso" —
sejam construídas de forma consistente. Não é uma skill em si; é um guia de design para
quando formos criar a próxima (ex.: uma skill equivalente para SwiftUI, para React,
para SQL, para Terraform etc.).

Leia isto **antes** de desenhar uma nova skill deste tipo. Depois, use
`jetpack-compose-refactor/` como referência de implementação concreta — este documento
explica o *porquê* de cada decisão; o código-fonte daquela skill mostra o *como*.

## Quando este padrão se aplica

Este padrão serve para skills onde:

1. Existe um ecossistema com convenções de "boas práticas" já estabelecidas e
   documentadas por ferramentas reais (linters, analisadores estáticos, guias oficiais)
   — o objetivo da skill é aplicar essas convenções, não inventar novas.
2. É desejável que a skill funcione **sem exigir que o projeto-alvo tenha essas
   ferramentas configuradas** — ou porque configurá-las é caro, ou porque nem sempre é
   possível (arquivo avulso, projeto sem Gradle/npm/etc. montado, ambiente restrito).
3. As refatorações precisam ser **auditáveis**: alguém revisando o diff deve conseguir
   perguntar "por que essa mudança?" e receber uma resposta rastreável a uma regra
   conhecida, não a uma preferência estética do agente.

Não é o padrão certo para: skills que fazem uma única transformação mecânica sem
ambiguidade (ex.: "renomeie X para Y em todo o projeto" — não precisa de scanner nem de
julgamento), ou skills que geram código novo do zero (não há "achado" para rastrear).

## Princípio central: a skill nunca inventa problemas

Este é o contrato mais importante do padrão, e vale a pena repetir com todas as letras:
**toda refatoração deve ser rastreável a um finding concreto emitido pelo scanner da
própria skill.** Duas consequências diretas:

- Se o scanner não sinalizou algo, não é escopo da refatoração — mesmo que, lendo o
  código, pareça um problema real. Ler o código é permitido e esperado, mas só para
  **confirmar ou descartar** um finding antes de corrigi-lo (o scanner é heurístico,
  então falsos positivos existem e devem ser filtrados por julgamento humano/do agente).
- Revisão manual além dos findings do scanner é sempre um passo **opcional, separado, e
  só sob pedido explícito do usuário** — nunca uma extensão silenciosa do fluxo
  principal. Ela produz observações não determinísticas (rodar de novo pode notar coisas
  diferentes), o que é fundamentalmente diferente da lista do scanner (mesmo código de
  entrada → sempre os mesmos findings de saída).

Esse contrato é o que torna os diffs revisáveis e reprodutíveis, e é o que separa esta
família de skills de um agente genérico "arrumando código à vontade".

## Estrutura de diretório

```
<nome-da-skill>/
├── SKILL.md                          # workflow, filosofia, índice de referências
├── scripts/
│   ├── <scanner-principal>.py        # CLI: descobre declarações-alvo, roda checagens
│   ├── rule_topic_map.json           # checkId -> topic/severity/references/examples/mirrors
│   ├── try_external_linters.sh       # opcional: corrobora com ferramenta(s) real(is)
│   ├── install_external_linters.sh   # opcional: instala essas ferramentas (dry-run por padrão)
│   ├── README.md                     # uso detalhado + limitações do scanner
│   └── checks/
│       ├── __init__.py               # utilidades compartilhadas (parsing, findings)
│       ├── <topico_1>.py
│       ├── <topico_2>.py
│       └── ...
├── references/
│   ├── <topico_1>.md                 # racional completo por tópico, aponta pro example
│   ├── ...
│   └── <glossario-de-proveniencia>.md  # ex.: "qual regra real cada checkId espelha"
└── examples/
    ├── 01-<padrao>-before-after.md
    └── ...
```

Cada peça tem um papel específico — não é boilerplate arbitrário:

- **`SKILL.md`** é a única coisa carregada sempre. Deve ser curto o bastante para caber
  no contexto sem custar caro, e delega detalhe pesado para `references/*.md` (carregado
  sob demanda, só os tópicos com findings) e `scripts/README.md` (raramente precisa ser
  lido pelo agente — é para humanos mantendo a skill).
- **`scripts/`** é onde vive toda a lógica determinística. Nada aqui deve depender de
  julgamento do agente para produzir a lista de findings — julgamento entra só depois,
  ao decidir *como* corrigir cada finding.
- **`references/`** é conhecimento de domínio, um arquivo por tópico. Não é para ser
  carregado inteiro de uma vez; é indexado por tópico no `SKILL.md` para carregamento
  seletivo.
- **`examples/`** são pares antes/depois concretos, um por padrão de refatoração — não
  para copiar literalmente, mas para servir de modelo de forma ao adaptar para o código
  real do usuário.

## Arquitetura do scanner

### 1. Descoberta

O scanner localiza as unidades de código relevantes ao domínio (no caso do Compose:
funções `@Composable`; em outro domínio poderia ser componentes React, queries SQL,
recursos Terraform etc.) via regex/parsing heurístico — **não** um parser completo da
linguagem-alvo. Essa é uma decisão deliberada: um parser real (ex.: compilador Kotlin)
adicionaria uma dependência pesada e provavelmente indisponível no ambiente do agente;
um heurístico textual bem testado cobre a grande maioria dos casos reais com uma fração
do custo de implementação, desde que suas limitações sejam **documentadas
explicitamente** (ver seção abaixo) em vez de escondidas.

Para cada unidade descoberta, capture o suficiente para todas as checagens rodarem sem
reprocessar o texto: assinatura/parâmetros, corpo (quando aplicável), anotações,
visibilidade, offset de linha. Se a unidade puder ter uma forma "sem corpo" (ex.: função
em forma de expressão `fun Foo() = ...`), documente que checagens baseadas em corpo não
rodam para ela — não finja cobertura que não existe.

Considere também **contextos de nível de arquivo** que mais de uma checagem possa
precisar (no Compose: imports do arquivo, classes irmãs instáveis) — compute uma vez por
arquivo e injete na representação de cada unidade, em vez de recomputar por checagem.

### 2. Módulos de checagem (`checks/*.py`)

Um módulo por tópico, cada um expondo uma ou mais destas funções conforme fizer sentido
para o domínio:

- `run(unit) -> list[finding]` — checagem que opera sobre uma unidade individual
  (a maioria dos casos).
- `run_class(cls)` / equivalente — quando o domínio tem uma segunda categoria de unidade
  com semântica própria (no Compose: classes `ViewModel`, analisadas separadamente das
  funções composable).
- `run_file(text, file_path, offsets)` — checagens que não vivem dentro de uma unidade
  única (naming de algo no nível de arquivo, uso de uma API deprecada em qualquer lugar
  do arquivo etc.).

Cada checagem devolve **findings crus**: `{file, line, checkId, message}` — sem
`topic`/`severity`/`mirrors`. Esse enriquecimento é responsabilidade de uma única fonte
de verdade (próxima seção), não espalhado por cada checagem — assim adicionar um tópico
novo ou reclassificar severidade é uma mudança em um arquivo, não em N.

`checks/__init__.py` guarda utilidades genuinamente compartilhadas entre módulos:
parsing de blocos que respeita strings/comentários, cálculo de número de linha a partir
de offset, construtor de finding, e qualquer "vocabulário" de domínio usado por várias
checagens (no Compose: `EMITTING_COMPOSABLES`, o conjunto de nomes de função que emitem
UI). Evite duplicar essas utilidades dentro dos módulos de checagem individuais.

### 3. `rule_topic_map.json`: fonte de verdade do enriquecimento

Um dicionário `checkId -> {topic, severity, references_file, examples_file, mirrors}`.
Isso existe como arquivo de dados separado, não hardcoded em cada checagem, por três
razões:

1. **Um lugar para auditar toda a superfície de regras** da skill de uma vez, sem ler
   oito módulos Python.
2. **`mirrors`** documenta proveniência — qual regra real de qual ferramenta (linter,
   analisador estático, guia oficial) aquela checagem espelha, quando existe uma. Isso é
   o que permite ao usuário confiar que a skill não está inventando convenções da
   cabeça: cada checagem é rastreável a uma fonte externa reconhecida, ou marcada
   explicitamente como "checagem própria, sem cobertura em ferramenta real" quando for o
   caso (não force um `mirrors` falso).
3. Permite ao `SKILL.md` construir uma tabela de índice de referências (`checkId` →
   qual `references/*.md` abrir) sem duplicar essa informação em dois lugares.

### 4. Degradação graciosa

O scanner nunca deve tratar "nada encontrado" como erro: caminho sem arquivos
relevantes, ou nenhuma checagem disparando, é uma lista vazia (`[]` em JSON), não uma
falha. Reserve códigos de saída não-zero para erros de uso reais (caminho inexistente).
Isso importa porque o agente roda o scanner repetidamente (antes e depois de cada
refatoração) — um scanner que "erra" em caso vazio quebraria esse loop de verificação.

## Corroboração externa (opcional, mas recomendada quando a ferramenta real existe)

Quando o ecossistema-alvo tem uma ferramenta real e instalável (ktlint, detekt, eslint,
ruff, tflint, sqlfluff...), vale a pena oferecer dois scripts opcionais que rodam a
ferramenta de verdade contra o mesmo alvo, como segunda opinião — nunca como
substituição do scanner próprio (que é o que funciona sem instalação nenhuma):

- **`try_external_*.sh`** — best-effort: procura a ferramenta no `PATH` e no cache local
  da skill, roda se achar, e **sempre sai com status 0** mesmo se nada estiver
  instalado (nesse caso, sugere o comando de instalação). Nunca deve poder quebrar o
  fluxo principal da skill.
- **`install_external_*.sh`** — baixa a(s) ferramenta(s) para um cache do usuário
  específico da skill (ex.: `~/.cache/<nome-da-skill>/tools/`), **nunca** para dentro do
  projeto-alvo. **Dry-run por padrão** — só baixa de fato com uma flag explícita
  (`--yes`), porque baixar e executar um binário de terceiros é uma ação com risco real
  que meritocamente exige confirmação explícita antes de ser automatizada. Versões
  baixadas devem ser fixas (constantes no topo do script), não "latest" — reprodutibilidade
  entre execuções importa tanto quanto no scanner Python.

Documente qualquer peculiaridade de integração descoberta na prática (ex.: no Compose,
como merge de jars de ruleset difere entre ktlint e detekt) no `scripts/README.md` da
skill nova — essas descobertas são caras de refazer e baratas de documentar uma vez.

## `SKILL.md`: forma do workflow

O `SKILL.md` de uma skill deste padrão segue esta sequência de passos (adapte nomes,
mantenha a ordem e as garantias):

1. **Resolver o alvo e o modo** — alvo: arquivo único, lista de unidades citadas, ou
   diretório/projeto inteiro; pergunte antes de escolher um escopo grande por conta
   própria se houver ambiguidade. Modo: aplicação direta (padrão) ou sugestão (ver
   subseção dedicada abaixo) — pergunte quando o usuário pedir explicitamente revisão
   prévia, ou quando o escopo for grande o bastante para tornar aplicação direta
   arriscada sem revisão.
2. **Rodar o scanner** — comando único, saída em JSON preferencialmente (mais fácil de
   processar), já enriquecida com `topic`/`severity`/`mirrors`.
3. **Corroboração externa**, se a skill tiver esse recurso — decida explicitamente se é
   obrigatória (como em `jetpack-compose-refactor`) ou opcional no `SKILL.md` da nova
   skill; se obrigatória, instale automaticamente sem pedir confirmação para esse passo
   específico (isso deve estar documentado como comportamento deliberado), mas nunca deixe
   a instalação silenciosa bloquear o fluxo se falhar.
4. **Carregar só as referências relevantes** aos tópicos com findings — nunca carregar
   `references/*.md` inteiro de uma vez.
5. **Aplicar as refatorações incrementalmente** (ou propô-las, no modo sugestão), um
   tópico/arquivo por vez, usando o `examples/*.md` correspondente como modelo de forma,
   adaptado ao código real.
6. **Verificar**: no modo aplicação, re-rodar o scanner e confirmar que os findings-alvo
   sumiram sem findings novos colaterais; compilar/testar de forma oportunista se houver
   infraestrutura de build real por trás do alvo (nunca obrigatório — a skill funciona
   sem isso); sinalizar explicitamente qualquer mudança de assinatura/API pública. No
   modo sugestão, este passo fica pendente até o usuário aprovar algo.
7. **Revisão manual** — só sob pedido explícito, rotulada como não determinística,
   nunca misturada à contagem de findings do scanner.
8. **Resumir** sempre em seções separadas, adaptadas ao modo: no modo aplicação, (a)
   findings do scanner antes/depois (determinístico), (b) saída bruta da corroboração
   externa se o passo 3 rodou, (c) observações manuais se o passo 7 rodou; no modo
   sugestão, (a) vira "findings com diff proposto, aguardando aprovação" e o relatório
   termina com uma pergunta objetiva sobre quais diffs aplicar. Nunca fundir essas coisas
   numa lista só.

### Modo aplicação vs. modo sugestão

Toda skill deste padrão deveria oferecer os dois modos, não só aplicação direta —
alguém revisando um escopo grande de findings pela primeira vez frequentemente prefere
ver o diff antes de deixar o agente escrever em disco. O toggle é barato de implementar
porque reaproveita infraestrutura que já existe no padrão (o par antes/depois de
`examples/*.md`, e a separação de seções do relatório final):

- **Aplicação (padrão)** — comportamento descrito nos passos acima sem modificação:
  edita direto via `Edit`/`Write`, verifica, resume com contagens reais.
- **Sugestão** — nenhum arquivo é tocado. No passo 5, para cada finding, apresente um
  bloco antes/depois (mesmo formato do `examples/*.md` correspondente) referenciando
  `arquivo:linha`, sem gravar nada. O passo 6 (verificar) não roda ainda — não há o que
  re-escanear se nada mudou. O passo 8 vira uma lista de diffs propostos aguardando
  aprovação, terminando com uma pergunta objetiva ("aplicar tudo, por tópico, ou um a
  um?"). Depois que o usuário aprovar algo, aplique só o aprovado e rode o passo 6 só
  para isso — o resto continua como sugestão até nova instrução.

Não alterne entre os dois modos no meio de uma sessão de refatoração sem o usuário
pedir — decida o modo uma vez no passo 1 e mantenha até o fim do escopo corrente.

### O que toda skill deste padrão deve sempre perguntar antes de fazer

- Adicionar uma dependência nova ao projeto-alvo para resolver um finding — proponha a
  alternativa sem dependência nova primeiro, quando existir.
- Editar arquivos de configuração de build/CI do projeto-alvo, por qualquer motivo,
  incluindo configurar a ferramenta real equivalente (linter/analisador) — a skill
  deliberadamente não depende disso para funcionar, e mudar config de build/CI afeta o
  time inteiro, não só quem pediu a refatoração.
- Mudar a assinatura pública de uma unidade (função, componente, endpoint...) sem
  sinalizar — isso é visível para quem consome, mesmo quando tecnicamente correto.

## Padrão de documentação (`references/` e `examples/`)

- **`references/<topico>.md`**: começa listando os `checkId`s cobertos por aquele
  tópico (facilita conferir se a tabela de índice do `SKILL.md` está completa), depois
  explica o racional de cada regra — o quê, por quê, qual `mirrors` (proveniência), e o
  fix esperado. Escreva para alguém que não conhece a convenção, não só para o agente:
  esses arquivos também servem de documentação de referência para humanos mantendo a
  skill.
- **`examples/NN-<padrao>-before-after.md`**: sempre três seções — `## Antes`,
  `## Depois`, `## Por quê`. Sem quarta seção solta; se o padrão precisar de mais
  contexto, isso vai dentro de "Por quê". Numerado sequencialmente só para ordenação
  estável em listagens de diretório, sem significado semântico no número.
- Todo finding do `rule_topic_map.json` deve apontar para um `references_file` e um
  `examples_file` que realmente existem e realmente cobrem aquele `checkId` — trate isso
  como um invariante a conferir manualmente ao adicionar uma checagem nova.

## Convenções de nomenclatura

- `checkId`: `kebab-case`, descritivo o bastante para aparecer sozinho num log de CI
  (ex.: `modifier-param-missing`, não `mod1`).
- `topic`: `kebab-case`, e deve bater exatamente com o nome-base do arquivo
  correspondente em `references/` (ex.: tópico `modifier-conventions` ↔
  `references/modifier-conventions.md`) — isso é o que permite ao `SKILL.md` montar a
  tabela de índice mecanicamente.
- `severity`: um vocabulário pequeno e consistente entre todos os módulos de checagem da
  mesma skill (no Compose: `warning`/`info`) — não invente uma escala nova por módulo.

## Checklist para começar uma skill nova neste padrão

1. O domínio tem convenções de boas práticas já estabelecidas por uma ou mais
   ferramentas reais (linter, analisador estático, guia oficial)? Se não, este padrão
   provavelmente não é o certo — considere se a skill deveria existir sem scanner.
2. Que "unidade" o scanner descobre (função? componente? classe? query? recurso?) e
   qual heurística textual (regex + rastreamento de profundidade de delimitadores) a
   localiza de forma suficientemente confiável, documentando onde ela falha?
3. Quais tópicos agrupam as checagens de forma que cada um vire um `references/*.md`
   coeso (nem tópico demais fragmentado, nem um único arquivo monolítico)?
4. Existe uma ferramenta real instalável para servir de corroboração externa? Se sim,
   vale a pena o par `try_external_*.sh` / `install_external_*.sh`; se não, pule essa
   parte do padrão sem forçar.
5. Escreva `scripts/checks/__init__.py` com as utilidades de parsing compartilhadas
   primeiro — todo o resto do scanner depende delas.
6. Escreva o scanner principal e pelo menos um módulo de checagem completo, valide
   rodando contra uma fixture real do domínio (arquivo de exemplo escrito à mão) e
   inspecionando o JSON de saída — não há suíte de testes unitários neste padrão; a
   validação é rodar o script contra fixtures reais.
7. Preencha `rule_topic_map.json` só depois que os `checkId`s estiverem estáveis —
   mudar um `checkId` depois de publicado quebra o mapeamento silenciosamente se
   esquecido em algum lugar.
8. Escreva `SKILL.md` seguindo a sequência de 8 passos acima, adaptada ao domínio.
9. Documente as limitações heurísticas conhecidas explicitamente, tanto no docstring do
   scanner quanto em `scripts/README.md` — isso não é opcional; é o que permite ao
   agente (e ao usuário) saber quando não confiar cegamente num finding.
