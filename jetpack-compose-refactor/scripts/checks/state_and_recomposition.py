"""Checagens de estado e recomposição.

Ver references/state-and-recomposition.md para o racional completo de cada regra.
"""
import re

from . import make_finding, find_matching, line_number

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

COROUTINE_BUILDER_RE = re.compile(r'\b(launch|async)\s*[({]')
FLOW_OPERATOR_RE = re.compile(
    r'\.(map|mapLatest|filter|filterNot|onEach|combine|zip|flowOn|distinctUntilChanged|'
    r'debounce|transform|flatMapLatest|flatMapConcat|flatMapMerge|scan|drop|take|'
    r'conflate|buffer|sample)\s*[({]'
)
COLLECT_AS_STATE_RE = re.compile(r'\.collectAsState\s*\(')
MUTABLE_COLLECTION_IN_STATE_RE = re.compile(
    r'mutableStateOf\s*\(\s*(mutableListOf|mutableSetOf|mutableMapOf|arrayListOf|'
    r'hashMapOf|hashSetOf|linkedMapOf|linkedSetOf|ArrayList|HashMap|HashSet|'
    r'LinkedList|LinkedHashMap|LinkedHashSet)\b'
)
UNREMEMBERED_OBJECT_RE = re.compile(
    r'(?<![.\w])(Animatable|MutableInteractionSource|movableContentOf|'
    r'movableContentWithReceiverOf|TextFieldState|FocusRequester|BringIntoViewRequester)\s*\('
)

# Tipos de parâmetro instáveis para o compilador do Compose (módulos externos onde o
# compilador Compose não roda) — lista conservadora de tipos claramente mutáveis/externos.
UNSTABLE_PARAM_TYPES = {
    'Date', 'Calendar', 'GregorianCalendar', 'LocalDateTime', 'LocalDate', 'LocalTime',
    'Instant',
}
# Tipos de estado do runtime do Compose que não deveriam ser parâmetros de composable
# (posse dividida do estado — prefira value: T + onValueChange: (T) -> Unit).
MUTABLE_STATE_PARAM_TYPES = {
    'MutableState', 'MutableIntState', 'MutableLongState', 'MutableFloatState',
    'MutableDoubleState', 'SnapshotStateList', 'SnapshotStateMap',
}

COMPOSITION_LOCAL_DECL_RE = re.compile(
    r'\bval\s+(\w+)\s*(?::[^=\n]*)?=\s*'
    r'(?:staticCompositionLocalOf|compositionLocalOf|compositionLocalWithComputedDefaultOf)\b'
)
STABILITY_ANNOTATION_RE = re.compile(r'@(Immutable|Stable)\b')

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


def _brace_depth(text, pos):
    """Profundidade de chaves de text[:pos] por contagem simples de '{'/'}' (mesmo nível
    de precisão dos outros heurísticos deste módulo — não ignora strings/comentários)."""
    prefix = text[:pos]
    return prefix.count('{') - prefix.count('}')


def _root_type(type_str):
    """Extrai o nome-raiz de um tipo: remove nullability, argumentos genéricos e o
    qualificador de pacote — ex.: 'java.util.Date?' -> 'Date', 'List<Foo>' -> 'List'."""
    t = type_str.strip().rstrip('?').strip()
    t = t.split('<', 1)[0].strip()
    t = t.split('.')[-1].strip()
    return t


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

    for m in COROUTINE_BUILDER_RE.finditer(body):
        if _brace_depth(body, m.start()) != 0:
            continue  # dentro de um bloco (onClick, LaunchedEffect, if, ...) — não é o corpo direto
        findings.append(make_finding(
            fn, 'coroutine-in-composition',
            f"'{m.group(1)}(...)' chamado diretamente no corpo do composable — criar uma "
            f"corrotina na composição a lança de novo a cada recomposição. Use "
            f"'LaunchedEffect(key) {{ ... }}' para trabalho atrelado à composição, ou "
            f"'rememberCoroutineScope()' + 'scope.{m.group(1)} {{ }}' dentro de um callback "
            f"de evento (ex.: onClick).",
            offset=m.start(),
        ))

    for m in COLLECT_AS_STATE_RE.finditer(body):
        window_before = body[max(0, m.start() - 200):m.start()]
        if FLOW_OPERATOR_RE.search(window_before):
            findings.append(make_finding(
                fn, 'flow-operator-in-composition',
                "Operador de Flow (map/filter/combine/...) encadeado com collectAsState no "
                "corpo — o Flow é recriado a cada recomposição. Mova a transformação para "
                "fora da composição (no ViewModel, ou em 'remember { fluxo.map { } }').",
                offset=m.start(),
            ))
        findings.append(make_finding(
            fn, 'collect-as-state-not-lifecycle-aware',
            "'.collectAsState()' coleta o Flow enquanto o composable estiver em composição, "
            "mesmo com o app em background. Em código Android, prefira "
            "'collectAsStateWithLifecycle()' (respeita o lifecycle, economiza recursos). "
            "Em código multiplataforma/commonMain, mantenha 'collectAsState()'.",
            offset=m.start(),
        ))

    for m in MUTABLE_COLLECTION_IN_STATE_RE.finditer(body):
        findings.append(make_finding(
            fn, 'mutable-collection-in-state',
            f"mutableStateOf({m.group(1)}(...)) — uma coleção mutável dentro de um "
            f"MutableState não notifica o Compose quando é mutada no lugar (ex.: .add()), "
            f"então a UI não recompõe. Use 'mutableStateListOf'/'mutableStateMapOf', ou "
            f"substitua a coleção inteira por uma imutável a cada mudança.",
            offset=m.start(),
        ))

    for m in UNREMEMBERED_OBJECT_RE.finditer(body):
        # prefixo do statement atual (até a última quebra de linha/';' antes) — mais preciso
        # que uma janela fixa, que pegaria um 'remember' de um statement anterior.
        stmt_start = max(body.rfind('\n', 0, m.start()), body.rfind(';', 0, m.start()))
        window = body[stmt_start + 1:m.start()]
        if 'remember' in window:
            continue
        findings.append(make_finding(
            fn, 'unremembered-object',
            f"'{m.group(1)}(...)' criado sem remember — o objeto é recriado a cada "
            f"recomposição, perdendo seu estado. Envolva em 'remember {{ {m.group(1)}(...) }}' "
            f"(ou use a factory 'remember{m.group(1)}(...)' quando existir).",
            offset=m.start(),
        ))

    for p in fn.params:
        root = _root_type(p['type'])
        if root in MUTABLE_STATE_PARAM_TYPES:
            findings.append(make_finding(
                fn, 'mutable-state-param',
                f"Parâmetro '{p['name']}: {p['type']}' expõe um tipo de estado mutável do "
                f"Compose — isso divide a posse do estado entre quem chama e o composable. "
                f"Prefira o padrão stateless: 'value: T' + 'onValueChange: (T) -> Unit'."
            ))
        elif root in UNSTABLE_PARAM_TYPES:
            findings.append(make_finding(
                fn, 'unstable-type-param',
                f"Parâmetro '{p['name']}: {p['type']}' usa um tipo de biblioteca externa "
                f"(não compilado com o compilador do Compose), tratado como instável — "
                f"quebra a skippability. Prefira um tipo próprio anotado @Immutable, ou "
                f"passe os campos já formatados (ex.: uma String) em vez do objeto cru."
            ))
        elif root in fn.sibling_unstable_classes:
            findings.append(make_finding(
                fn, 'mutable-class-param',
                f"Parâmetro '{p['name']}: {p['type']}' usa uma classe com propriedade 'var' "
                f"no construtor (declarada neste arquivo) — o compilador do Compose a trata "
                f"como instável, quebrando a skippability. Torne as propriedades 'val' e "
                f"anote a classe @Immutable, ou marque-a @Stable se há mutação observável."
            ))

    return findings


def run_file(text, file_path, offsets):
    """Checagens de nível de arquivo (declarações fora de corpos de @Composable):
    naming de CompositionLocal e contradição @Immutable/@Stable + 'var'."""
    findings = []

    for m in COMPOSITION_LOCAL_DECL_RE.finditer(text):
        name = m.group(1)
        if not name.startswith('Local'):
            findings.append({
                'file': file_path,
                'line': line_number(offsets, m.start()),
                'checkId': 'composition-local-naming',
                'message': f"CompositionLocal '{name}' deveria usar o prefixo 'Local' "
                           f"(ex.: 'Local{name[0].upper() + name[1:]}') — é a convenção que "
                           f"distingue CompositionLocals de valores/estados comuns.",
            })

    for m in STABILITY_ANNOTATION_RE.finditer(text):
        annotation = m.group(1)
        after = text[m.end():m.end() + 200]
        class_m = re.search(r'\b(?:data\s+|value\s+)?class\s+(\w+)\s*(?:<[^>]*>)?\s*\(', after)
        if not class_m:
            continue
        # só considera se não há outra declaração/quebra estrutural entre a anotação e o class
        between = after[:class_m.start()]
        if any(kw in between for kw in ('fun ', 'val ', 'var ', 'object ', ';')):
            continue
        open_paren = m.end() + class_m.end() - 1
        close_paren = find_matching(text, open_paren, '(', ')')
        if close_paren == -1:
            continue
        ctor = text[open_paren + 1:close_paren]
        if re.search(r'\bvar\s+\w+', ctor):
            findings.append({
                'file': file_path,
                'line': line_number(offsets, m.start()),
                'checkId': 'immutable-annotation-with-var',
                'message': f"@{annotation} em '{class_m.group(1)}', que tem propriedade 'var' "
                           f"no construtor — a anotação promete estabilidade/imutabilidade "
                           f"que a classe não cumpre (o Compose pode pular recomposições "
                           f"incorretamente). Torne as propriedades 'val', ou remova a anotação.",
            })

    return findings
