"""Checagens de acessibilidade em composables.

Ver references/accessibility.md para o racional completo de cada regra. Todas operam
sobre o corpo de funções @Composable (chamadas a Image/Icon e cadeias de Modifier com
clickable), então composables com corpo em forma de expressão não são cobertos
(limitação geral do scanner).
"""
import re

from . import make_finding, find_matching

IMAGE_ICON_CALL_RE = re.compile(r'\b(Image|Icon)\s*\(')
EMPTY_CONTENT_DESC_RE = re.compile(r'\bcontentDescription\s*=\s*""')
NULL_CONTENT_DESC_RE = re.compile(r'\bcontentDescription\s*=\s*null\b')
CLICKABLE_RE = re.compile(r'\.\s*(clickable|toggleable|selectable)\b')
SIZE_MODIFIER_RE = re.compile(
    r'\.\s*(size|width|height|requiredSize|requiredWidth|requiredHeight)\s*\(\s*(\d+)\s*\.dp'
)
INTERACTIVE_NEARBY_RE = re.compile(r'\b(clickable|toggleable|selectable)\b')
ICON_BUTTON_NEARBY_RE = re.compile(r'\b(IconButton|IconToggleButton|FilledIconButton|OutlinedIconButton)\s*\(')

MIN_TOUCH_TARGET_DP = 48


def run(fn):
    findings = []
    body = fn.body or ''

    # image-missing-content-description / null-content-description-clickable
    for m in IMAGE_ICON_CALL_RE.finditer(body):
        name = m.group(1)
        open_paren = body.find('(', m.start())
        close_paren = find_matching(body, open_paren, '(', ')')
        if close_paren == -1:
            continue
        args = body[open_paren + 1:close_paren]

        if 'contentDescription' not in args:
            findings.append(make_finding(
                fn, 'image-missing-content-description',
                f"{name}(...) sem 'contentDescription' nomeado — declare a descrição "
                f"explicitamente: um texto significativo se o elemento é informativo, ou "
                f"'contentDescription = null' se é puramente decorativo (o leitor de tela "
                f"o ignora). Evite depender de argumento posicional.",
                offset=m.start(),
            ))
        elif NULL_CONTENT_DESC_RE.search(args):
            window_before = body[max(0, m.start() - 250):m.start()]
            if CLICKABLE_RE.search(args) or ICON_BUTTON_NEARBY_RE.search(window_before):
                findings.append(make_finding(
                    fn, 'null-content-description-clickable',
                    f"{name}(contentDescription = null) num elemento clicável — "
                    f"'null' marca o elemento como decorativo (ignorado pelo leitor de "
                    f"tela), mas um alvo clicável precisa de um rótulo. Forneça uma "
                    f"descrição da ação (ex.: 'Editar perfil').",
                    offset=m.start(),
                ))

    for m in EMPTY_CONTENT_DESC_RE.finditer(body):
        findings.append(make_finding(
            fn, 'empty-content-description',
            "contentDescription = \"\" (string vazia) — o elemento é anunciado como vazio "
            "pelo leitor de tela em vez de descrito ou ignorado. Use um texto significativo "
            "(informativo) ou 'null' (decorativo).",
            offset=m.start(),
        ))

    # touch-target-too-small
    for m in SIZE_MODIFIER_RE.finditer(body):
        value = int(m.group(2))
        if value >= MIN_TOUCH_TARGET_DP:
            continue
        window = body[max(0, m.start() - 120):m.end() + 120]
        if INTERACTIVE_NEARBY_RE.search(window):
            findings.append(make_finding(
                fn, 'touch-target-too-small',
                f"Elemento interativo com .{m.group(1)}({value}.dp) — abaixo do alvo de "
                f"toque mínimo de {MIN_TOUCH_TARGET_DP}.dp recomendado para acessibilidade. "
                f"Use 'Modifier.minimumInteractiveComponentSize()' ou "
                f"'sizeIn(minWidth = {MIN_TOUCH_TARGET_DP}.dp, minHeight = {MIN_TOUCH_TARGET_DP}.dp)'.",
                offset=m.start(),
            ))

    # clickable-without-semantics
    for m in CLICKABLE_RE.finditer(body):
        if m.group(1) != 'clickable':
            continue
        after = body[m.end():m.end() + 200]
        window = body[max(0, m.start() - 150):m.end() + 200]
        has_label_or_role = 'onClickLabel' in after or 'role' in after.split('}')[0]
        if not has_label_or_role and '.semantics' not in window and 'Role.' not in window:
            findings.append(make_finding(
                fn, 'clickable-without-semantics',
                "Modifier.clickable sem 'onClickLabel'/'role' e sem 'semantics' associado — "
                "para elementos que não são um componente semântico (Button, etc.), o leitor "
                "de tela não sabe o papel/ação. Declare 'role = Role.Button' e/ou "
                "'onClickLabel' descrevendo a ação.",
                offset=m.start(),
            ))

    return findings
