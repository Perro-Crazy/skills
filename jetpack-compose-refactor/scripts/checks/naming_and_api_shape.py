"""Checagens de naming, ordenação de parâmetros e forma de API de composables.

Ver references/naming-and-api-shape.md para o racional completo de cada regra.
"""
import re

from . import make_finding, EMITTING_COMPOSABLES

PASCAL_CASE_RE = re.compile(r'^[A-Z][A-Za-z0-9]*$')
FUNCTION_TYPE_UNIT_RE = re.compile(r'^\(.*\)\s*->\s*Unit$')
CONTENT_PARAM_NAMES = {
    'content', 'label', 'icon', 'leadingIcon', 'trailingIcon', 'leadingContent',
    'trailingContent', 'placeholder', 'text', 'title', 'topBar', 'bottomBar',
    'floatingActionButton', 'snackbarHost', 'actions', 'navigationIcon',
}


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

    return findings
