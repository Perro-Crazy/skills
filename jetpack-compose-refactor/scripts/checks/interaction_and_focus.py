"""Checagens de interação e foco.

Ver references/interaction-and-focus.md para o racional completo de cada regra.

Nenhuma das checagens deste módulo tem equivalente direto em Android Lint, ktlint
compose-rules ou detekt compose-rules hoje — são regras próprias inspiradas na
API pública do Compose (`InteractionSource` é o signal idiomático para estado
de interação em Material3; `onFocusEvent` só dispara se o composable for
`.focusable()`, e nem `Card` nem `Surface` são focusable por padrão).
"""
import re

from . import find_matching, make_finding

# Componentes Compose que aceitam parâmetro `onClick` e cuja observabilidade de
# interação do usuário deve ser feita via InteractionSource (não via onFocusEvent,
# que precisa de Modifier.focusable() que esses componentes não trazem por padrão).
CLICKABLE_SURFACE_RE = re.compile(r'\b(Card|ElevatedCard|OutlinedCard|Surface)\s*\(')
# Modifier.clickable{} é a outra porta de entrada: alguém que define um wrapper
# clicável custom (.clickable(onClick = …) ou a forma trailing-lambda
# .clickable { onClick() }, já que `onClick` é o último parâmetro) também cai
# na mesma regra. Sem exigir `(` logo em seguida, para cobrir as duas formas
# (mesmo padrão usado em accessibility.py:CLICKABLE_RE).
MODIFIER_CLICKABLE_RE = re.compile(r'\.\s*clickable\b')
# onClick como rótulo de argumento nomeado é o sinal que confirma a presença do
# callback de toque (descarta Card/Surface decorativos sem onClick, que não são
# interativos).
HAS_ON_CLICK_RE = re.compile(r'\bonClick\b')
# onFocusEvent dentro de Modifier é a heurística que sinaliza "está tentando
# observar interação via foco". Aceita tanto a forma de chamada (onFocusEvent(...))
# quanto a forma trailing lambda (onFocusEvent { state -> ... }) — as duas
# formas são equivalentes em Kotlin.
ON_FOCUS_EVENT_RE = re.compile(r'\.onFocusEvent\s*[\({]')
# Presença de InteractionSource (qualquer uma das três formas mais comuns) confirma
# que o composable já está usando o signal idiomático — não é um finding.
INTERACTION_SOURCE_RE = re.compile(
    r'\b(MutableInteractionSource|InteractionSource)\b|\binteractionSource\b'
)

# `.interactions` é o Flow<Interaction> exposto por InteractionSource; coletá-lo
# manualmente com `.collect { ... }` é o sinal de "observação direta" — quando o
# bloco só distingue eventos de um único eixo (só press, só foco, só drag, só
# hover), existe um helper declarativo 1:1 que substitui a coroutine inteira.
INTERACTIONS_COLLECT_RE = re.compile(r'\.interactions\.collect\s*\{')
LAUNCHED_EFFECT_RE = re.compile(r'\bLaunchedEffect\s*\(')
MUTABLE_INTERACTION_SOURCE_CTOR_RE = re.compile(r'\bMutableInteractionSource\s*\(\s*\)')
REMEMBER_UPDATED_STATE_RE = re.compile(r'\brememberUpdatedState\s*\(')

# Cada família agrupa os subtipos de Interaction que um único helper
# `collectIsXAsState()` cobre por completo — ver
# androidx.compose.foundation.interaction.
INTERACTION_FAMILIES = {
    'pressed': (r'PressInteraction\.Press\b', r'PressInteraction\.Release\b', r'PressInteraction\.Cancel\b'),
    'focused': (r'FocusInteraction\.Focus\b', r'FocusInteraction\.Unfocus\b'),
    'dragged': (r'DragInteraction\.Start\b', r'DragInteraction\.Stop\b', r'DragInteraction\.Cancel\b'),
    'hovered': (r'HoverInteraction\.Enter\b', r'HoverInteraction\.Exit\b'),
}
HELPER_BY_FAMILY = {
    'pressed': 'collectIsPressedAsState()',
    'focused': 'collectIsFocusedAsState()',
    'dragged': 'collectIsDraggedAsState()',
    'hovered': 'collectIsHoveredAsState()',
}


def _has_clickable_surface(body):
    """True se o corpo contém um Card/Surface/Modifier.clickable com `onClick` em
    algum lugar — sinaliza uma superfície interativa que precisa de InteractionSource."""
    has_surface = bool(CLICKABLE_SURFACE_RE.search(body)) and bool(HAS_ON_CLICK_RE.search(body))
    has_clickable_modifier = bool(MODIFIER_CLICKABLE_RE.search(body))
    return has_surface or has_clickable_modifier


def _brace_blocks_after(body, open_regex):
    """Para cada match de `open_regex` que termina bem antes de um `{`, retorna
    (posição do '{', posição do '}' correspondente, texto do bloco). Usado para
    extrair o corpo de uma trailing lambda (`.collect { ... }`)."""
    blocks = []
    for m in open_regex.finditer(body):
        open_brace = m.end() - 1
        close_brace = find_matching(body, open_brace, '{', '}')
        if close_brace == -1:
            continue
        blocks.append((open_brace, close_brace, body[open_brace + 1:close_brace]))
    return blocks


def _launched_effect_blocks(body):
    """Para cada `LaunchedEffect(keys...) { ... }`, retorna (posição do '{' do
    bloco, texto das keys, texto do corpo). Pula o `(...)` de keys antes de achar
    o `{` do lambda — LaunchedEffect sempre tem parênteses de key(s) antes."""
    blocks = []
    for m in LAUNCHED_EFFECT_RE.finditer(body):
        open_paren = m.end() - 1
        close_paren = find_matching(body, open_paren, '(', ')')
        if close_paren == -1:
            continue
        keys_text = body[open_paren + 1:close_paren]
        rest = body[close_paren + 1:]
        ws_len = len(rest) - len(rest.lstrip(' \t\r\n'))
        open_brace = close_paren + 1 + ws_len
        if open_brace >= len(body) or body[open_brace] != '{':
            continue
        close_brace = find_matching(body, open_brace, '{', '}')
        if close_brace == -1:
            continue
        blocks.append((open_brace, keys_text, body[open_brace + 1:close_brace]))
    return blocks


def _callback_param_names(fn):
    """Nomes dos parâmetros do composable cujo tipo é uma lambda (contém '->') —
    candidatos a stale closure quando referenciados dentro de um effect."""
    return [p['name'] for p in fn.params if p.get('name') and '->' in (p.get('type') or '')]


def _has_interaction_source_param(fn):
    for p in fn.params:
        if p.get('name') == 'interactionSource':
            return True
        if 'InteractionSource' in (p.get('type') or ''):
            return True
    return False


def _check_interaction_source_in_clickable(fn, findings):
    if not ON_FOCUS_EVENT_RE.search(fn.body):
        return
    if not _has_clickable_surface(fn.body):
        return
    if INTERACTION_SOURCE_RE.search(fn.body):
        return

    findings.append(make_finding(
        fn, 'interaction-source-in-clickable',
        f"'{fn.name}' usa Card/Surface/Modifier.clickable (com onClick) mas observa "
        f"interação via Modifier.onFocusEvent — para detectar toque/press/foco o "
        f"idiomático em Compose é MutableInteractionSource (passado ao Card via "
        f"parâmetro 'interactionSource', ou a Modifier.clickable via "
        f"'interactionSource = ...') e a coleta de 'interactions' num LaunchedEffect. "
        f"onFocusEvent em Card/Surface não dispara sem Modifier.focusable() na chain, "
        f"que esses componentes não trazem por padrão.",
    ))


def _check_manual_interaction_collect(fn, findings):
    for open_brace, _close_brace, collect_body in _brace_blocks_after(fn.body, INTERACTIONS_COLLECT_RE):
        families_touched = [
            family for family, markers in INTERACTION_FAMILIES.items()
            if any(re.search(marker, collect_body) for marker in markers)
        ]
        if len(families_touched) != 1:
            continue  # mistura eixos (ex.: press + foco) -> collect manual é justificado
        family = families_touched[0]
        findings.append(make_finding(
            fn, 'interaction-source-manual-collect',
            f"'{fn.name}' coleta '.interactions' manualmente só para distinguir eventos de "
            f"{family} — como nenhum outro eixo (press/foco/drag/hover) é observado neste "
            f"bloco, '{HELPER_BY_FAMILY[family]}' (androidx.compose.foundation.interaction) "
            f"cobre o mesmo caso sem precisar de LaunchedEffect nem coroutine manual.",
            offset=open_brace,
        ))


def _check_interaction_source_not_hoisted(fn, findings):
    if not MUTABLE_INTERACTION_SOURCE_CTOR_RE.search(fn.body):
        return
    if _has_interaction_source_param(fn):
        return
    if not _callback_param_names(fn):
        return  # sem parâmetro de callback -> não parece um componente reutilizável
    if not _has_clickable_surface(fn.body):
        return

    findings.append(make_finding(
        fn, 'interaction-source-not-hoisted',
        f"'{fn.name}' cria seu próprio 'MutableInteractionSource()' internamente em vez de "
        f"recebê-lo como parâmetro — quem chama este composable não consegue observar nem "
        f"customizar (ripple, animação, testes de estado de press/foco) a interação da "
        f"superfície clicável. Adicione 'interactionSource: MutableInteractionSource = "
        f"remember {{ MutableInteractionSource() }}' como parâmetro hoisted.",
    ))


def _check_callback_not_stable(fn, findings):
    callback_names = _callback_param_names(fn)
    if not callback_names:
        return
    if REMEMBER_UPDATED_STATE_RE.search(fn.body):
        return  # já existe rememberUpdatedState em algum lugar do corpo

    for open_brace, keys_text, block_body in _launched_effect_blocks(fn.body):
        is_interaction_scope = (
            INTERACTIONS_COLLECT_RE.search(block_body)
            or 'interactionSource' in block_body
            or 'InteractionSource' in block_body
        )
        if not is_interaction_scope:
            continue  # fora do escopo deste módulo (foco em interaction source/foco)

        for name in callback_names:
            if not re.search(rf'\b{re.escape(name)}\b', block_body):
                continue
            if re.search(rf'\b{re.escape(name)}\b', keys_text):
                continue  # já é key do LaunchedEffect -> reinicia o effect, sem stale closure
            findings.append(make_finding(
                fn, 'interaction-source-callback-not-stable',
                f"'{fn.name}' referencia o parâmetro '{name}' dentro de um LaunchedEffect que "
                f"observa interação, mas '{name}' não é key do effect nem passa por "
                f"'rememberUpdatedState' — se o composable recompor com uma nova lambda "
                f"'{name}' antes do effect reiniciar, a coroutine ainda segura a referência "
                f"antiga (stale closure). Capture com "
                f"'val current{name[0].upper()}{name[1:]} by rememberUpdatedState({name})' e "
                f"chame 'current{name[0].upper()}{name[1:]}()' dentro do effect.",
                offset=open_brace,
            ))
            break  # um finding por LaunchedEffect já é suficiente


def run(fn):
    findings = []
    if not fn.body:
        return findings

    _check_interaction_source_in_clickable(fn, findings)
    _check_manual_interaction_collect(fn, findings)
    _check_interaction_source_not_hoisted(fn, findings)
    _check_callback_not_stable(fn, findings)
    return findings
