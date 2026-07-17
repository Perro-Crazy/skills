"""Checagens de naming, ordenação de parâmetros e forma de API de composables.

Ver references/naming-and-api-shape.md para o racional completo de cada regra.
"""
import re

from . import make_finding, find_matching, line_number, EMITTING_COMPOSABLES

PASCAL_CASE_RE = re.compile(r'^[A-Z][A-Za-z0-9]*$')
FUNCTION_TYPE_UNIT_RE = re.compile(r'^\(.*\)\s*->\s*Unit$')
FUNCTION_TYPE_ANY_RE = re.compile(r'^\(.*\)\s*->\s*\S')
CONTENT_PARAM_NAMES = {
    'content', 'label', 'icon', 'leadingIcon', 'trailingIcon', 'leadingContent',
    'trailingContent', 'placeholder', 'text', 'title', 'topBar', 'bottomBar',
    'floatingActionButton', 'snackbarHost', 'actions', 'navigationIcon',
}

SCAFFOLD_CALL_RE = re.compile(r'\b(Scaffold|BottomSheetScaffold)\s*\(')
BOX_CONSTRAINTS_RE = re.compile(r'\bBoxWithConstraints\s*[({]')
ANIMATED_CONTENT_RE = re.compile(r'\bAnimatedContent\s*\(')
CONSTRAINTS_SCOPE_TOKENS = ('constraints', 'maxWidth', 'maxHeight', 'minWidth', 'minHeight')
LAMBDA_HEADER_RE = re.compile(r'\s*([\w\s,]+?)\s*->')
ANNOTATION_CLASS_RE = re.compile(r'\bannotation\s+class\s+(\w+)')
MATERIAL2_IMPORT_RE = re.compile(r'^\s*import\s+androidx\.compose\.material\.([A-Za-z_]\w*)', re.M)
MATERIAL2_ALLOWED_SUBPACKAGES = {'icons', 'ripple', 'pullrefresh'}


def _trailing_lambda_body(body, open_paren_pos):
    """Dado o '(' de uma chamada, devolve (offset_do_open_brace, texto_do_corpo_do_lambda)
    do lambda trailing `(...) { ... }`, ou None se não houver lambda trailing."""
    close_paren = find_matching(body, open_paren_pos, '(', ')')
    if close_paren == -1:
        return None
    after = body[close_paren + 1:]
    ws_len = len(after) - len(after.lstrip())
    if ws_len >= len(after) or after[ws_len] != '{':
        return None
    open_brace = close_paren + 1 + ws_len
    close_brace = find_matching(body, open_brace, '{', '}')
    if close_brace == -1:
        return None
    return open_brace, body[open_brace + 1:close_brace]


def _lambda_ignores_its_param(lambda_body):
    """True se o lambda declara um parâmetro (`nome ->`) que não é usado no corpo, ou não
    declara parâmetro nem usa `it` — indício de que o valor fornecido pelo slot foi ignorado."""
    header = LAMBDA_HEADER_RE.match(lambda_body)
    if header and '->' in lambda_body[:header.end() + 1]:
        names = [n.strip() for n in header.group(1).split(',') if n.strip()]
        rest = lambda_body[header.end():]
        # ignora nomes triviais e checa se algum é referenciado no corpo
        if any(re.search(rf'\b{re.escape(n)}\b', rest) for n in names if n not in ('_',)):
            return False
        return True
    # sem parâmetro nomeado: só é "ignorado" se nem `it` aparece
    return not re.search(r'\bit\b', lambda_body)


def _strip_composable_annotation(type_str):
    return type_str.replace('@Composable', '').strip()


def _is_content_slot_param(p):
    """Um parâmetro de 'slot de conteúdo' é uma lambda @Composable (ex.: content: @Composable
    () -> Unit) — diferente de um callback de evento comum (ex.: onClick: () -> Unit), que é um
    parâmetro obrigatório normal e não precisa vir por último."""
    t = p['type'].strip()
    return '@Composable' in t and FUNCTION_TYPE_UNIT_RE.match(_strip_composable_annotation(t))


def _count_top_level_emitters(body):
    depth = 0
    count = 0
    i, n = 0, len(body)
    while i < n:
        c = body[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
        elif c == '(' and depth == 0:
            j = i - 1
            while j >= 0 and body[j] in ' \t':
                j -= 1
            k = j
            while k >= 0 and (body[k].isalnum() or body[k] == '_'):
                k -= 1
            name = body[k + 1:j + 1]
            if name in EMITTING_COMPOSABLES:
                count += 1
        i += 1
    return count


def run(fn):
    findings = []

    if 'Preview' in fn.annotations:
        if not fn.is_private:
            findings.append(make_finding(
                fn, 'preview-naming-visibility',
                f"Função @Preview '{fn.name}' não é private — previews não deveriam vazar para a "
                f"API pública do módulo."
            ))
        if not fn.name.endswith('Preview'):
            findings.append(make_finding(
                fn, 'preview-naming-visibility',
                f"Função @Preview '{fn.name}' deveria terminar com o sufixo 'Preview'."
            ))
        return findings  # previews não passam pelas checagens de shape abaixo

    is_unit_return = fn.return_type.strip() in ('', 'Unit')
    if is_unit_return and not PASCAL_CASE_RE.match(fn.name):
        findings.append(make_finding(
            fn, 'composable-naming',
            f"'{fn.name}' retorna Unit (emite UI) mas o nome não segue PascalCase de substantivo "
            f"— convenção esperada para composables que emitem UI."
        ))

    for p in fn.params:
        t = _strip_composable_annotation(p['type'])
        if FUNCTION_TYPE_UNIT_RE.match(t) and p['name'] not in CONTENT_PARAM_NAMES:
            if not p['name'].startswith('on'):
                findings.append(make_finding(
                    fn, 'event-callback-naming',
                    f"Parâmetro de evento '{p['name']}: {p['type']}' não segue a convenção "
                    f"'onXxx' usada para callbacks de interação do usuário."
                ))

    modifier_idx = next(
        (i for i, p in enumerate(fn.params) if p['type'].strip() == 'Modifier'), None
    )
    if modifier_idx is not None:
        for p in fn.params[:modifier_idx]:
            if p['default'] is not None:
                findings.append(make_finding(
                    fn, 'param-ordering',
                    f"Parâmetro opcional '{p['name']}' aparece antes de 'modifier' — a convenção "
                    f"é: obrigatórios -> modifier -> opcionais -> lambda de conteúdo por último."
                ))
                break

    content_slot_params = []
    if fn.params:
        last = fn.params[-1]
        content_slot_params = [p for p in fn.params if _is_content_slot_param(p)]
        if content_slot_params and last not in content_slot_params:
            names = ', '.join(p['name'] for p in content_slot_params)
            findings.append(make_finding(
                fn, 'param-ordering',
                f"Há parâmetro(s) de slot de conteúdo @Composable ({names}) que não estão na "
                f"última posição — a lambda de conteúdo/trailing deveria vir por último para "
                f"permitir a sintaxe de trailing lambda no call site."
            ))

    if len(content_slot_params) == 1 and content_slot_params[0]['name'] not in CONTENT_PARAM_NAMES:
        p = content_slot_params[0]
        findings.append(make_finding(
            fn, 'content-slot-param-naming',
            f"Parâmetro de slot de conteúdo '{p['name']}: {p['type']}' — a convenção é nomear "
            f"o único slot de conteúdo trailing como 'content' (nomes como 'itemContent' de "
            f"wrappers de lista são uma exceção legítima; confirme antes de renomear)."
        ))

    if fn.body:
        top_level_calls = _count_top_level_emitters(fn.body)
        has_slot_param = any(_is_content_slot_param(p) for p in fn.params)
        if top_level_calls > 1 and not has_slot_param:
            findings.append(make_finding(
                fn, 'multiple-content-emitters',
                f"'{fn.name}' emite {top_level_calls} componentes de UI no nível raiz sem expor "
                f"parâmetros de slot — envolva em um único container (Row/Column/Box) ou exponha "
                f"slots nomeados em vez de deixar múltiplos emissores soltos."
            ))

        if not is_unit_return and top_level_calls >= 1:
            findings.append(make_finding(
                fn, 'composable-emit-and-return',
                f"'{fn.name}' retorna '{fn.return_type.strip()}' mas também emite UI no nível "
                f"raiz — um composable deve ou emitir UI (retornando Unit) ou calcular e "
                f"devolver um valor, nunca os dois (regra 'emit XOR return value' das "
                f"guidelines oficiais de API do Compose)."
            ))

    # event-trailing-lambda: callback de evento (on*) como último parâmetro, depois do modifier
    if len(fn.params) >= 2:
        last = fn.params[-1]
        last_type = _strip_composable_annotation(last['type'])
        is_event_lambda = (
            '@Composable' not in last['type']
            and FUNCTION_TYPE_ANY_RE.match(last_type)
            and last['name'].startswith('on')
        )
        modifier_before = any(p['type'].strip() == 'Modifier' for p in fn.params[:-1])
        if is_event_lambda and modifier_before:
            findings.append(make_finding(
                fn, 'event-trailing-lambda',
                f"'{last['name']}: {last['type']}' é um callback de evento na última posição "
                f"(depois do modifier) — a trailing lambda deveria ser reservada para o slot "
                f"de conteúdo @Composable. Mova o evento para junto dos parâmetros "
                f"obrigatórios, antes do modifier."
            ))

    # unused-scope: Scaffold/AnimatedContent/BoxWithConstraints que ignoram o valor do slot
    if fn.body:
        for m in SCAFFOLD_CALL_RE.finditer(fn.body):
            open_paren = fn.body.find('(', m.start())
            lam = _trailing_lambda_body(fn.body, open_paren)
            if lam and _lambda_ignores_its_param(lam[1]):
                findings.append(make_finding(
                    fn, 'scaffold-padding-ignored',
                    f"O lambda de conteúdo de {m.group(1)}(...) ignora o PaddingValues "
                    f"fornecido — sem aplicá-lo (ex.: 'Modifier.padding(innerPadding)'), o "
                    f"conteúdo fica atrás das barras (topBar/bottomBar). Capture e aplique o "
                    f"parâmetro de padding.",
                    offset=m.start(),
                ))

        for m in ANIMATED_CONTENT_RE.finditer(fn.body):
            open_paren = fn.body.find('(', m.start())
            lam = _trailing_lambda_body(fn.body, open_paren)
            if lam and _lambda_ignores_its_param(lam[1]):
                findings.append(make_finding(
                    fn, 'animatedcontent-unused-target',
                    "O lambda de conteúdo de AnimatedContent ignora o parâmetro targetState — "
                    "use o valor recebido pelo lambda, não a variável externa, senão o "
                    "conteúdo animado renderiza o estado errado durante a transição.",
                    offset=m.start(),
                ))

        for m in BOX_CONSTRAINTS_RE.finditer(fn.body):
            open_delim = fn.body.find('{', m.start())
            if open_delim == -1:
                continue
            close_delim = find_matching(fn.body, open_delim, '{', '}')
            if close_delim == -1:
                continue
            scope_body = fn.body[open_delim + 1:close_delim]
            if not any(tok in scope_body for tok in CONSTRAINTS_SCOPE_TOKENS):
                findings.append(make_finding(
                    fn, 'boxwithconstraints-unused-scope',
                    "BoxWithConstraints cujo corpo não usa constraints/maxWidth/maxHeight — "
                    "se o layout não depende das restrições recebidas, um Box comum é mais "
                    "barato (BoxWithConstraints adia a composição do conteúdo até a medição).",
                    offset=m.start(),
                ))

    return findings


def _annotations_above(text, pos):
    """Devolve o texto das linhas de anotação (`@...`) imediatamente acima de `pos`,
    parando na primeira linha que não é anotação nem em branco — evita herdar anotações
    da declaração anterior."""
    line_start = text.rfind('\n', 0, pos)
    collected = []
    while line_start > 0:
        prev_line_start = text.rfind('\n', 0, line_start)
        line = text[prev_line_start + 1:line_start].strip()
        if line == '':
            line_start = prev_line_start
            continue
        if line.startswith('@'):
            collected.append(line)
            line_start = prev_line_start
            continue
        break
    return '\n'.join(collected)


def run_file(text, file_path, offsets):
    """Checagens de nível de arquivo: naming de annotation classes (@Composable/@Preview
    agregadas) e uso de Material 2."""
    findings = []

    for m in ANNOTATION_CLASS_RE.finditer(text):
        name = m.group(1)
        prefix = _annotations_above(text, m.start())
        if '@Preview' in prefix and not name.startswith('Preview'):
            findings.append({
                'file': file_path,
                'line': line_number(offsets, m.start()),
                'checkId': 'preview-annotation-naming',
                'message': f"Annotation de multipreview '{name}' (agrega @Preview) deveria "
                           f"usar o prefixo 'Preview' (ex.: 'PreviewScreenSizes').",
            })
        if ('@Composable' in prefix or '@ComposableTargetMarker' in prefix) and not name.endswith('Composable'):
            findings.append({
                'file': file_path,
                'line': line_number(offsets, m.start()),
                'checkId': 'composable-annotation-naming',
                'message': f"Annotation marcada com @Composable '{name}' deveria terminar "
                           f"com o sufixo 'Composable' (ex.: '{name}Composable').",
            })

    for m in MATERIAL2_IMPORT_RE.finditer(text):
        first_segment = m.group(1)
        if first_segment in MATERIAL2_ALLOWED_SUBPACKAGES:
            continue
        findings.append({
            'file': file_path,
            'line': line_number(offsets, m.start()),
            'checkId': 'material2-usage',
            'message': f"Import de Material 2 ('androidx.compose.material.{first_segment}') — "
                       f"se o projeto usa Material 3, prefira o equivalente em "
                       f"'androidx.compose.material3' para consistência de design system.",
        })

    return findings
