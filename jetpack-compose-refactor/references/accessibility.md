# Acessibilidade

Checagens do scanner que caem neste tópico: `image-missing-content-description`,
`empty-content-description`, `touch-target-too-small`, `null-content-description-clickable`,
`clickable-without-semantics`.

Nenhuma dessas tem uma regra de linter dedicada habilitada por padrão no Android Lint/
ktlint/detekt — são checagens próprias inspiradas diretamente no guia oficial de
acessibilidade do Compose (`developer.android.com/develop/ui/compose/accessibility`).
Como todas operam sobre o corpo de composables (chamadas a `Image`/`Icon` e cadeias de
`Modifier`), composables com corpo em forma de expressão não são cobertos.

## `contentDescription` em `Image`/`Icon`

O leitor de tela (TalkBack) usa `contentDescription` para anunciar o que uma imagem/
ícone representa. As três situações que o scanner sinaliza:

- **Sem `contentDescription` nomeado** — a chamada não passa o parâmetro de forma
  explícita (uso posicional ou omitido). **Finding: `image-missing-content-description`**
  (severidade `info` — pode ser um argumento posicional legítimo). Ao revisar: declare
  a intenção explicitamente — um texto significativo se o elemento é informativo, ou
  `contentDescription = null` se é puramente decorativo.
- **`contentDescription = ""` (string vazia)** — quase sempre um bug: o elemento é
  anunciado como "vazio" em vez de ignorado. **Finding: `empty-content-description`**
  (severidade `warning`). Fix: use um texto real (informativo) ou `null` (decorativo).
- **`contentDescription = null` num elemento clicável** — `null` marca o elemento como
  decorativo (ignorado pelo TalkBack), o que é incompatível com um alvo clicável, que
  precisa de rótulo. **Finding: `null-content-description-clickable`** (severidade
  `info` — o scanner sinaliza quando o próprio `Icon`/`Image` tem `clickable` na
  chamada, ou está dentro de um `IconButton`/`IconToggleButton`). Fix: descreva a ação
  (ex.: `contentDescription = "Editar perfil"`).

## Alvo de toque mínimo (48.dp)

O guia fixa o alvo de toque mínimo em **48.dp** (constante
`minimumInteractiveComponentSize`). Um elemento interativo (`clickable`/`toggleable`/
`selectable` na mesma cadeia de `Modifier`) com `size`/`width`/`height` fixo abaixo
disso é difícil de acertar, especialmente para quem tem dificuldade motora. **Finding:
`touch-target-too-small`** (severidade `warning` — só dispara com literal numérico
`< 48.dp`; se o tamanho vem de uma variável, o scanner não sinaliza).
- Fix: `Modifier.minimumInteractiveComponentSize()` ou
  `Modifier.sizeIn(minWidth = 48.dp, minHeight = 48.dp)`. O ícone visual pode continuar
  menor; o que precisa de 48.dp é a área de toque.

## `clickable` sem papel/rótulo semântico

`Modifier.clickable` num elemento que não é um componente semântico (um `Box`/`Row`
custom, não um `Button`) não informa ao TalkBack o papel do elemento nem o que a ação
faz. **Finding: `clickable-without-semantics`** (severidade `info` — o scanner sinaliza
`clickable` sem `onClickLabel`/`role` e sem `Modifier.semantics` associado; gera algum
ruído em elementos triviais, por isso é `info` e deve ser confirmado).
- Fix: passe `role = Role.Button` (ou o papel apropriado) e/ou `onClickLabel = "..."`
  descrevendo a ação — ou use um componente que já carrega semântica (`Button`, etc.).
