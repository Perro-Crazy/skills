"""Checagens de estado e recomposição.

Ver references/state-and-recomposition.md para o racional completo de cada regra.
"""
import re

from . import make_finding

MUTABLE_STATE_RE = re.compile(r'mutableStateOf\s*(<[^>]*>)?\s*\(')
TYPED_NUMERIC_RE = re.compile(r'mutableStateOf\s*<\s*(Int|Float|Long)\s*>\s*\(')
BARE_INT_LITERAL_RE = re.compile(r'mutableStateOf\s*\(\s*(-?\d+)\s*\)')
UNSTABLE_COLLECTION_RE = re.compile(r'^(List|MutableList|Map|MutableMap|Set|MutableSet)\s*<')
LAUNCHED_EFFECT_RE = re.compile(r'LaunchedEffect\s*\(\s*(Unit|true)\s*\)')
COMPOSITION_LOCAL_RE = re.compile(r'\b(Local[A-Z]\w*)\.current\b')

# CompositionLocals de plataforma cujo uso é uma preocupação transversal legítima
# (tema, densidade, lifecycle) — não vale a pena sinalizar esses.
SAFE_COMPOSITION_LOCALS = {
    'LocalContext', 'LocalConfiguration', 'LocalDensity', 'LocalLifecycleOwner',
    'LocalView', 'LocalContentColor', 'LocalTextStyle', 'LocalLayoutDirection',
    'LocalFocusManager', 'LocalSoftwareKeyboardController', 'LocalClipboardManager',
    'LocalInspectionMode', 'LocalUriHandler',
}


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

    return findings
