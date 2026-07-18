# Theming do Material 3

Checagens do scanner que caem neste tópico: `material3-hardcoded-color`,
`material3-hardcoded-typography`.

## Cor fixa em vez de token de `MaterialTheme.colorScheme`

Um composable de UI que constrói uma cor inline (`Color(0xFF6650A4)`, `Color(red = ...,
green = ..., blue = ...)`) ou usa uma constante fixa (`Color.Red`, `Color.White`, etc.) em
vez de ler um token de `MaterialTheme.colorScheme` (`primary`, `onSurface`,
`surfaceVariant`, ...) quebra o contrato de theming do Material 3:

- **Dark theme**: a cor fixa não inverte com o tema do sistema — o componente fica com a
  cor errada (ou ilegível, se for um texto sobre um fundo que mudou de tom) quando o
  usuário troca de tema.
- **Dynamic color** (Android 12+, `dynamicColorScheme`): a paleta é extraída do wallpaper
  do usuário em tempo de execução — uma cor fixa nunca vai combinar com o resto da UI
  nesse modo.
- **Consistência entre telas**: se cada composable declara sua própria cor "parecida com
  a de marca", pequenas divergências de tom se acumulam pelo app inteiro.

**Finding: `material3-hardcoded-color`** (severidade `info`; checagem própria — nenhuma
regra de Android Lint/ktlint/detekt cobre isso hoje). O scanner varre o corpo de cada
composable (que não seja `@Preview`) por `Color(...)` e pelas constantes nomeadas mais
comuns (`Color.Red`, `Color.Blue`, `Color.Black`, `Color.White`, `Color.Gray`,
`Color.DarkGray`, `Color.LightGray`, `Color.Green`, `Color.Yellow`, `Color.Cyan`,
`Color.Magenta`).

### Exceções que o scanner já trata

- **`Color.Transparent`/`Color.Unspecified`** não disparam — não têm equivalente em
  `colorScheme` e costumam ser usos legítimos (ex.: fade num `Brush.verticalGradient`,
  ou "deixe o valor default fluir").
- **Composables `@Preview`** são ignorados — dados de exemplo num preview não afetam o app
  real.
- **Composables que definem o próprio `ColorScheme`** — qualquer função cujo corpo chame
  `lightColorScheme(...)`, `darkColorScheme(...)`, `dynamicLightColorScheme(...)` ou
  `dynamicDarkColorScheme(...)`, ou cujo nome termine em `Theme` (convenção usual:
  `AppTheme`, `MyAppTheme`) — é exatamente o lugar certo para declarar as cores fixas da
  paleta do app, então o scanner pula a função inteira.

### O que o scanner **não** sabe distinguir

- Uma `val` de nível de arquivo em `Color.kt` (`val Purple80 = Color(0xFFD0BCFF)`) nunca é
  varrida, porque o scanner só olha para dentro de corpos de função `@Composable` — o que
  já é o comportamento desejado, já que esse é o lugar correto para o literal existir.
- Uma cor fixa que é genuinamente correta fora do fluxo de tema (ex.: a cor de uma marca
  de terceiro incorporada visualmente, como o vermelho oficial de um logo de parceiro) —
  confirme a intenção antes de trocar por um token; nem toda cor fixa é um bug.

## Fix

1. Se a cor já existe como token em `colorScheme` (ou deveria existir), troque o literal
   pela referência: `MaterialTheme.colorScheme.primary`, `.onPrimaryContainer`, etc.
2. Se é uma cor de marca que ainda não tem token — e faz sentido ter um —, declare-a uma
   vez em `Color.kt` e exponha via `MaterialTheme.colorScheme` (custom color scheme) ou
   via um `CompositionLocal` próprio, em vez de repetir o literal em cada call site.
3. Não decida sozinho qual token semântico substitui a cor fixa quando não é óbvio pelo
   contexto (ex.: um vermelho que pode ser `error` ou pode ser uma cor de marca) — pergunte
   antes de aplicar a correção.

## Tipografia fixa em vez de `MaterialTheme.typography`

Um `Text(...)` que define `fontSize`/`fontFamily` diretamente, em vez de aplicar
`style = MaterialTheme.typography.*` (`bodyLarge`, `titleMedium`, `headlineSmall`, ...),
reinventa a escala tipográfica do design system caso a caso:

- Cada `Text` vira uma fonte independente de verdade sobre tamanho/família de fonte — se o
  time decide ajustar a escala do app (ex.: `bodyLarge` de 16sp para 15sp), esse `Text` não
  acompanha, e a inconsistência visual se acumula.
- Perde a adaptação automática que `MaterialTheme.typography` dá de graça em temas
  customizados (ex.: um "modo compacto" que troca a escala tipográfica inteira via
  `CompositionLocalProvider(LocalTypography provides ...)` não afeta esse `Text`).

**Finding: `material3-hardcoded-typography`** (severidade `info`; checagem própria — sem
regra de linter dedicada). O scanner localiza cada chamada `Text(...)` no corpo de um
composable (que não seja `@Preview`) e sinaliza quando os argumentos contêm `fontSize =`
ou `fontFamily =` como parâmetro nomeado.

### Exceção que o scanner já trata

- Se os argumentos da chamada também contêm `MaterialTheme.typography` (ex.:
  `style = MaterialTheme.typography.bodyLarge.copy(fontSize = 18.sp)`), o finding **não**
  dispara — é um ajuste pontual derivado de um estilo do tema, não tipografia reinventada
  do zero.

### O que o scanner **não** sabe distinguir

- `fontWeight` sozinho (sem `fontSize`/`fontFamily`) não dispara — usar `fontWeight =
  FontWeight.Bold` em cima do estilo default é um ajuste pontual comum e geralmente
  aceitável, não coberto por esta checagem.
- Um `TextStyle(...)` construído inline e passado via `style = TextStyle(fontSize = ...)`
  também é pego (o `fontSize` aparece nos argumentos do `Text(...)` de fora para dentro),
  mas o scanner não analisa `TextStyle`s definidos fora do `Text(...)` (ex.: numa `val`
  separada) — mesma limitação de escopo por-função das outras checagens.

### Fix

1. Troque `fontSize`/`fontFamily` inline por `style = MaterialTheme.typography.<escala>`
   apropriada ao papel do texto (título, corpo, label, ...).
2. Se o app precisa de uma fonte customizada, declare-a uma vez no `Typography` do tema
   (`Theme.kt`), não em cada `Text(...)` que usa aquela fonte.
3. Se é um ajuste pontual legítimo (ex.: um preço em destaque um pouco maior que
   `titleMedium`), prefira `MaterialTheme.typography.titleMedium.copy(fontSize = ...)` a
   partir de um estilo existente, em vez de um `fontSize` solto sem base nenhuma.
