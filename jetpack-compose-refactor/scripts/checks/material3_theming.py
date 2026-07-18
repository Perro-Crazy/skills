"""Checagens de theming do Material 3: cores e tipografia fixas em vez de tokens de
MaterialTheme.

Ver references/material3-theming.md para o racional completo de cada regra.
"""
import re

from . import make_finding, find_matching

COLOR_CONSTRUCTOR_RE = re.compile(r'\bColor\s*\(')
COLOR_NAMED_CONSTANT_RE = re.compile(
    r'\bColor\.(Black|DarkGray|Gray|LightGray|White|Red|Green|Blue|Yellow|Cyan|Magenta)\b'
)
THEME_BUILDER_RE = re.compile(
    r'\b(lightColorScheme|darkColorScheme|dynamicLightColorScheme|dynamicDarkColorScheme)\s*\('
)
TEXT_CALL_RE = re.compile(r'\bText\s*\(')
FONT_SIZE_ARG_RE = re.compile(r'\bfontSize\s*=')
FONT_FAMILY_ARG_RE = re.compile(r'\bfontFamily\s*=')
THEME_TYPOGRAPHY_RE = re.compile(r'MaterialTheme\.typography')


def _has_hardcoded_typography(args_raw):
    if THEME_TYPOGRAPHY_RE.search(args_raw):
        # deriva de um MaterialTheme.typography.* (ex.: via '.copy(fontSize = ...)') —
        # ajuste pontual sobre um estilo do tema, não tipografia reinventada do zero.
        return False
    return bool(FONT_SIZE_ARG_RE.search(args_raw) or FONT_FAMILY_ARG_RE.search(args_raw))


def run(fn):
    findings = []

    if 'Preview' in fn.annotations or not fn.body:
        return findings

    # Composable que constrói o próprio ColorScheme do app (tipicamente 'AppTheme'/
    # 'MyAppTheme' chamando lightColorScheme/darkColorScheme) é o lugar certo para
    # declarar as cores fixas da paleta — não um finding.
    if fn.name.endswith('Theme') or THEME_BUILDER_RE.search(fn.body):
        return findings

    for m in COLOR_CONSTRUCTOR_RE.finditer(fn.body):
        findings.append(make_finding(
            fn, 'material3-hardcoded-color',
            "Cor construída inline com 'Color(...)' dentro de um composable de UI — prefira "
            "um token de 'MaterialTheme.colorScheme' (ex.: 'MaterialTheme.colorScheme.primary'). "
            "Cor fixa aqui não reage a dark theme nem a dynamic color; se é mesmo uma cor de "
            "marca fixa, declare-a uma vez no arquivo de tema (Theme.kt/Color.kt) e referencie "
            "o token a partir daí, em vez de repetir o literal em cada composable.",
            offset=m.start(),
        ))

    for m in COLOR_NAMED_CONSTANT_RE.finditer(fn.body):
        findings.append(make_finding(
            fn, 'material3-hardcoded-color',
            f"Constante de cor fixa 'Color.{m.group(1)}' usada diretamente no composable — "
            f"prefira um token de 'MaterialTheme.colorScheme' para respeitar dark theme e "
            f"dynamic color.",
            offset=m.start(),
        ))

    for m in TEXT_CALL_RE.finditer(fn.body):
        open_paren = m.end() - 1
        close_paren = find_matching(fn.body, open_paren, '(', ')')
        if close_paren == -1:
            continue
        args_raw = fn.body[open_paren + 1:close_paren]
        if _has_hardcoded_typography(args_raw):
            findings.append(make_finding(
                fn, 'material3-hardcoded-typography',
                "Text(...) define 'fontSize'/'fontFamily' diretamente em vez de usar "
                "'style = MaterialTheme.typography.*' — tipografia inline não segue a "
                "escala do design system e não muda se o tema for atualizado. Prefira um "
                "estilo de 'MaterialTheme.typography' (ex.: 'bodyLarge', 'titleMedium') e, "
                "se precisar de um ajuste pontual, derive dele com '.copy(...)' em vez de "
                "definir os atributos do zero.",
                offset=m.start(),
            ))

    return findings
