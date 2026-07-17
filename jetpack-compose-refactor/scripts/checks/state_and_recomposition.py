"""Checagens de estado e recomposição.

Ver references/state-and-recomposition.md para o racional completo de cada regra.
"""
import re

from . import make_finding, find_matching

MUTABLE_STATE_RE = re.compile(r'mutableStateOf\s*(<[^>]*>)?\s*\(')
TYPED_NUMERIC_RE = re.compile(r'mutableStateOf\s*<\s*(Int|Float|Long)\s*>\s*\(')
BARE_INT_LITERAL_RE = re.compile(r'mutableStateOf\s*\(\s*(-?\d+)\s*\)')
UNSTABLE_COLLECTION_RE = re.compile(r'^(List|MutableList|Map|MutableMap|Set|MutableSet)\s*<')
LAUNCHED_EFFECT_RE = re.compile(r'LaunchedEffect\s*\(\s*(Unit|true)\s*\)')
COMPOSITION_LOCAL_RE = re.compile(r'\b(Local[A-Z]\w*)\.current\b')
DISPOSABLE_EFFECT_RE = re.compile(r'\bDisposableEffect\s*\(')
ONDISPOSE_RE = re.compile(r'\bonDispose\s*[{(]')
STATE_DELEGATE_RE = re.compile(r'\bvar\s+(\w+)\s+by\s+(?:remember|rememberSaveable)\b')
STATE_OF_HINT_RE = re.compile(r'mutable\w*StateOf\s*\(')
WRITE_OP_RE = re.compile(r'\s*(=(?!=)|\+\+|--|\+=|-=|\*=|/=)')
COLLECTION_TRANSFORM_RE = re.compile(r'\.(sortedWith|sortedBy|sorted|filter|map|groupBy)\s*[({]')
EFFECT_WRAPPER_NAMES = {'LaunchedEffect', 'produceState'}

# CompositionLocals de plataforma cujo uso é uma preocupação transversal legítima
# (tema, densidade, lifecycle) — não vale a pena sinalizar esses.
SAFE_COMPOSITION_LOCALS = {
    'LocalContext', 'LocalConfiguration', 'LocalDensity', 'LocalLifecycleOwner',
    'LocalView', 'LocalContentColor', 'LocalTextStyle', 'LocalLayoutDirection',
    'LocalFocusManager', 'LocalSoftwareKeyboardController', 'LocalClipboardManager',
    'LocalInspectionMode', 'LocalUriHandler',
}


def _prev_nonspace_char(text, pos):
    i = pos - 1
    while i >= 0 and text[i] in ' \t\n':
        i -= 1
    return text[i] if i >= 0 else ''


def _enclosing_call_name(body, pos):
    """Acha o identificador imediatamente antes do '{' não fechado mais próximo que
    envolve `pos` — usado para saber se um trecho está dentro de um LaunchedEffect/
    produceState (onde recalcular a cada execução do efeito não é o mesmo problema de
    recalcular a cada recomposição)."""
    depth = 0
    i = pos - 1
    while i >= 0:
        c = body[i]
        if c == '}':
            depth += 1
        elif c == '{':
            if depth == 0:
                j = i - 1
                while j >= 0 and body[j] in ' \t\n':
                    j -= 1
                if j >= 0 and body[j] == ')':
                    # pula os parênteses balanceados da lista de argumentos antes do '{'
                    # trailing (ex.: 'LaunchedEffect(products) {' / 'remember(key) {')
                    paren_depth = 1
                    j -= 1
                    while j >= 0 and paren_depth > 0:
                        if body[j] == ')':
                            paren_depth += 1
                        elif body[j] == '(':
                            paren_depth -= 1
                        j -= 1
                    while j >= 0 and body[j] in ' \t\n':
                        j -= 1
                k = j
                while k >= 0 and (body[k].isalnum() or body[k] == '_'):
                    k -= 1
                return body[k + 1:j + 1]
            depth -= 1
        i -= 1
    return None


def run(fn):
    findings = []
    body = fn.body or ''

    for m in MUTABLE_STATE_RE.finditer(body):
        window = body[max(0, m.start() - 80):m.start()]
        if 'remember' not in window:
            findings.append(make_finding(
                fn, 'unremembered-mutable-state',
                "mutableStateOf(...) usado sem remember { } — o estado é recriado a cada "
                "recomposição em vez de sobreviver a ela.",
                offset=m.start(),
            ))

    for m in TYPED_NUMERIC_RE.finditer(body):
        kind = m.group(1)
        replacement = {
            'Int': 'mutableIntStateOf', 'Float': 'mutableFloatStateOf', 'Long': 'mutableLongStateOf',
        }[kind]
        findings.append(make_finding(
            fn, 'autoboxing-state-creation',
            f"mutableStateOf<{kind}>(...) faz autoboxing a cada escrita — prefira {replacement}(...).",
            offset=m.start(),
        ))

    for m in BARE_INT_LITERAL_RE.finditer(body):
        if '<' in body[max(0, m.start() - 30):m.start()]:
            continue  # já coberto pelo TYPED_NUMERIC_RE acima
        findings.append(make_finding(
            fn, 'autoboxing-state-creation',
            "mutableStateOf(<literal inteiro>) faz autoboxing a cada escrita — prefira "
            "mutableIntStateOf(...).",
            offset=m.start(),
        ))

    for p in fn.params:
        if UNSTABLE_COLLECTION_RE.match(p['type'].strip()):
            findings.append(make_finding(
                fn, 'unstable-collection-param',
                f"Parâmetro '{p['name']}: {p['type']}' usa uma coleção mutável/instável — quebra "
                f"a skippability do Compose. Prefira ImmutableList/ImmutableMap/ImmutableSet "
                f"(kotlinx.collections.immutable) ou um wrapper anotado com @Immutable/@Stable."
            ))

    for m in LAUNCHED_EFFECT_RE.finditer(body):
        findings.append(make_finding(
            fn, 'launched-effect-key-risk',
            f"LaunchedEffect({m.group(1)}) encontrado — confirme manualmente que nenhum valor "
            f"externo mutável lido dentro do efeito deveria fazer parte da key (senão o efeito "
            f"não é relançado quando deveria).",
            offset=m.start(),
        ))

    for m in COMPOSITION_LOCAL_RE.finditer(body):
        local_name = m.group(1)
        if local_name in SAFE_COMPOSITION_LOCALS:
            continue
        findings.append(make_finding(
            fn, 'composition-local-overuse',
            f"Uso de {local_name}.current — confirme que é uma preocupação transversal genuína "
            f"(tema, layout direction, etc.) e não um atalho para passar dados de negócio que "
            f"deveriam ser parâmetros explícitos.",
            offset=m.start(),
        ))

    for m in DISPOSABLE_EFFECT_RE.finditer(body):
        open_paren = body.find('(', m.start())
        if open_paren == -1:
            continue
        close_paren = find_matching(body, open_paren, '(', ')')
        if close_paren == -1:
            continue
        after = body[close_paren + 1:]
        ws_len = len(after) - len(after.lstrip())
        if ws_len >= len(after) or after[ws_len] != '{':
            continue  # não é um DisposableEffect(...) { ... } com lambda trailing (raro)
        open_brace = close_paren + 1 + ws_len
        close_brace = find_matching(body, open_brace, '{', '}')
        if close_brace == -1:
            continue
        effect_body = body[open_brace + 1:close_brace]
        if not ONDISPOSE_RE.search(effect_body):
            findings.append(make_finding(
                fn, 'disposable-effect-missing-ondispose',
                "DisposableEffect(...) sem onDispose { } no corpo — todo efeito descartável "
                "precisa terminar devolvendo um DisposableEffectResult via onDispose { }, "
                "chamado quando o efeito sai de composição ou é relançado (troca de key). "
                "Sem isso, recursos registrados (listeners, observers) nunca são liberados.",
                offset=m.start(),
            ))

    for m in STATE_DELEGATE_RE.finditer(body):
        name = m.group(1)
        window = body[m.end():m.end() + 120]
        if not STATE_OF_HINT_RE.search(window):
            continue
        decl_end = m.end()
        name_re = re.compile(rf'[{{}}]|\b{re.escape(name)}\b')
        depth = 0
        read_pos = None
        for tok in name_re.finditer(body, decl_end):
            c = tok.group()
            if c == '{':
                depth += 1
                continue
            if c == '}':
                depth = max(0, depth - 1)
                continue
            if depth != 0:
                continue
            abs_pos = tok.start()
            if _prev_nonspace_char(body, abs_pos) in '(,':
                continue  # rótulo de argumento nomeado (ex.: 'Slider(value = value, ...)')
            write_match = WRITE_OP_RE.match(body, tok.end())
            if write_match:
                if read_pos is not None:
                    findings.append(make_finding(
                        fn, 'backwards-state-write',
                        f"'{name}' é lido e depois escrito de novo no mesmo nível do corpo "
                        f"de '{fn.name}' (fora de uma lambda de evento/efeito) — cada "
                        f"escrita dispara uma recomposição, e se ela não estiver "
                        f"condicionada a um evento do usuário, isso pode causar um loop de "
                        f"recomposição infinito. Mova a escrita para dentro de um callback "
                        f"(ex.: onClick).",
                        offset=abs_pos,
                    ))
                break
            read_pos = abs_pos

    for m in COLLECTION_TRANSFORM_RE.finditer(body):
        window = body[max(0, m.start() - 80):m.start()]
        if 'remember' in window:
            continue
        if _enclosing_call_name(body, m.start()) in EFFECT_WRAPPER_NAMES:
            continue  # dentro de LaunchedEffect/produceState — não roda a cada recomposição
        findings.append(make_finding(
            fn, 'unmemoized-derived-collection',
            f"'.{m.group(1)}(...)' chamado diretamente no corpo sem remember — a coleção é "
            f"recalculada a cada recomposição. Se a entrada não mudou, envolva em "
            f"'remember(chave) {{ ... }}'.",
            offset=m.start(),
        ))

    return findings
