# Arquitetura ViewModel <-> Composable

Checagens do scanner que caem neste tópico: `viewmodel-param-forwarding`,
`viewmodel-injection-in-leaf`.

## O princípio unificador: separação stateful/stateless

Num destino de navegação típico, deveria existir **um único** composable "de tela"
(stateful) — o que está diretamente ligado à rota/destino de navegação — responsável
por adquirir o `ViewModel` (via `viewModel()`, `hiltViewModel()`, `koinViewModel()` ou
equivalente) e coletar seu estado (`collectAsStateWithLifecycle()` no Android;
equivalente multiplataforma em Compose Multiplatform). Todo composable **abaixo**
dessa tela deveria ser stateless: recebe apenas `UiState` (dados já prontos para
exibição) + lambdas de callback (`onClick`, `onValueChange`, ...), sem saber que um
`ViewModel` existe.

Isso é hoisting de estado (ver `references/state-and-recomposition.md`) aplicado
especificamente na fronteira do ViewModel. Benefícios diretos: composables internos
ficam testáveis isoladamente, têm `@Preview` fácil de escrever (não dependem de DI),
e não ficam acoplados a qual framework de DI/arquitetura o app usa.

## ViewModel repassado como parâmetro

Passar o `ViewModel` inteiro como parâmetro para um composable que não é a tela raiz
acopla esse composable ao ciclo de vida e ao container de DI do ViewModel, e quebra a
possibilidade de reutilizá-lo/testá-lo/dar preview nele sem montar um ViewModel real.
**Finding: `viewmodel-param-forwarding`** — o scanner sinaliza qualquer parâmetro cujo
tipo termine em algo como `*ViewModel*`.
- Mirrors: detekt/ktlint compose-rules `ComposeViewModelForwarding`.
- Fix: extraia do ViewModel só os dados (`UiState`) e os callbacks que o composable
  realmente usa, e passe esses em vez do ViewModel inteiro.
- **Exceção legítima**: o próprio composable de tela, se por alguma razão intermediária
  precisar repassar o ViewModel para um sub-grafo de navegação aninhado (raro). Ao
  revisar um finding, confirme primeiro se `fn` é de fato a tela raiz antes de decidir
  que é falso positivo — o scanner não tem como distinguir isso automaticamente.

## ViewModel adquirido dentro de um composable "folha"

Chamar `viewModel()`/`hiltViewModel()`/`koinViewModel()` só é apropriado no composable
de tela. Se um composable que **já recebe parâmetros de callback** (indício de não ser
a raiz — a raiz tipicamente não recebe callbacks de fora, ela os define a partir do
ViewModel) também adquire um ViewModel internamente, isso duplica a fonte de estado e
quebra a separação stateful/stateless. **Finding: `viewmodel-injection-in-leaf`**
(severidade `info` — heurística: só dispara quando o composable tem parâmetros E pelo
menos um deles é um callback, como sinal indireto de "não é a tela raiz"; sempre
confirme visualmente).
- Mirrors: detekt/ktlint compose-rules `ComposeViewModelInjection`.
- Fix: mova a aquisição do ViewModel para o composable de tela; repasse o estado e os
  callbacks já resolvidos para este composable.

## Nota para Compose Multiplatform (CMP)

Fora do ecossistema Android/Hilt, a aquisição de ViewModel costuma vir de outra fonte
de DI (Koin é comum em projetos CMP: `koinViewModel()`), mas o princípio é idêntico:
uma única aquisição na tela, estado e callbacks hoisted para baixo. Ao revisar um
projeto CMP, procure pelo equivalente local de "adquirir ViewModel" (pode ser uma
função customizada do projeto) e aplique o mesmo raciocínio de
`viewmodel-injection-in-leaf` mesmo que o scanner não reconheça o nome da função.
