"""Checagens de arquitetura ViewModel <-> Composable.

Ver references/viewmodel-architecture.md para o racional completo de cada regra.
"""
import re

from . import make_finding

VIEWMODEL_TYPE_RE = re.compile(r'^\w*ViewModel\w*(<.*>)?\??$')
VM_ACQUIRE_RE = re.compile(r'\b(viewModel|hiltViewModel|koinViewModel)\s*(<[^>]*>)?\s*\(')
FUNCTION_TYPE_PREFIX_RE = re.compile(r'^\(.*\)\s*->\s*')


def run(fn):
    findings = []

    for p in fn.params:
        t = p['type'].strip()
        if VIEWMODEL_TYPE_RE.match(t):
            findings.append(make_finding(
                fn, 'viewmodel-param-forwarding',
                f"Parâmetro '{p['name']}: {t}' repassa um ViewModel — se '{fn.name}' não for o "
                f"composable de tela (a raiz ligada ao destino de navegação), extraia estado + "
                f"callbacks em vez de repassar o ViewModel adiante."
            ))

    if fn.body:
        m = VM_ACQUIRE_RE.search(fn.body)
        if m:
            has_callback_param = any(
                FUNCTION_TYPE_PREFIX_RE.match(p['type'].strip().replace('@Composable', '').strip())
                for p in fn.params
            )
            if fn.params and has_callback_param:
                findings.append(make_finding(
                    fn, 'viewmodel-injection-in-leaf',
                    f"'{m.group(1)}()' chamado dentro de '{fn.name}', que já recebe parâmetro(s) "
                    f"de callback (indício de não ser o composable de tela) — injete o ViewModel "
                    f"apenas no composable de tela e repasse estado/callbacks para este.",
                    offset=m.start(),
                ))

    return findings
