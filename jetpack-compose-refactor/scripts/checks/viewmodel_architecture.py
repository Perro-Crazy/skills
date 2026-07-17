"""Checagens de arquitetura ViewModel <-> Composable.

Ver references/viewmodel-architecture.md para o racional completo de cada regra.
"""
import re

from . import make_finding

VIEWMODEL_TYPE_RE = re.compile(r'^\w*ViewModel\w*(<.*>)?\??$')
VM_ACQUIRE_RE = re.compile(r'\b(viewModel|hiltViewModel|koinViewModel)\s*(<[^>]*>)?\s*\(')
FUNCTION_TYPE_PREFIX_RE = re.compile(r'^\(.*\)\s*->\s*')

PROPERTY_TYPED_RE = re.compile(r'^(private\s+)?(val|var)\s+(\w+)\s*:\s*([^=\n{]+)')
PROPERTY_INFERRED_RE = re.compile(r'^(private\s+)?(val|var)\s+(\w+)\s*=\s*(.+)')
COMPOSE_STATE_TYPE_RE = re.compile(r'^(androidx\.compose\.runtime\.)?(State|MutableState)\s*<')
COMPOSE_STATE_CTOR_RE = re.compile(r'^mutable\w*StateOf\s*\(')
STATE_HOLDER_TYPE_RE = re.compile(r'^(StateFlow|State|MutableState|LiveData)\s*<')
STATE_HOLDER_CTOR_RE = re.compile(r'^(MutableStateFlow|StateFlow|MutableLiveData|LiveData)\s*\(')


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


def _iter_top_level_property_lines(class_body):
    """Percorre o corpo da classe linha a linha, rastreando profundidade de chaves por
    contagem de '{'/'}' por linha (heurístico textual, sem consciência de string/comentário
    — mesmo nível de precisão dos outros regexes deste scanner). Só produz as linhas cuja
    profundidade ANTES da linha é 0, ou seja, ignora o interior de funções/init/lambdas
    aninhados (blocos de método) e enxerga apenas declarações de nível de classe."""
    lines = []
    depth = 0
    pos = 0
    for raw_line in class_body.split('\n'):
        if depth == 0:
            lines.append(raw_line.strip())
        depth = max(0, depth + raw_line.count('{') - raw_line.count('}'))
        pos += len(raw_line) + 1
    return lines


def run_class(cls):
    """Checagens de nível de classe (não de função @Composable) sobre classes que
    herdam de *ViewModel*. Ver find_viewmodel_classes em scan_compose_components.py
    para como o corpo da classe é extraído."""
    findings = []
    exposing_compose_state = []
    state_holders = []

    for line in _iter_top_level_property_lines(cls.body):
        m = PROPERTY_TYPED_RE.match(line)
        tail_type = tail_init = None
        if m:
            tail_type = m.group(4).strip()
        else:
            m = PROPERTY_INFERRED_RE.match(line)
            if m:
                tail_init = m.group(4).strip()
        if not m:
            continue
        is_private = bool(m.group(1))
        if is_private:
            continue
        name = m.group(3)

        is_compose_state = (
            (tail_type is not None and COMPOSE_STATE_TYPE_RE.match(tail_type))
            or (tail_init is not None and COMPOSE_STATE_CTOR_RE.match(tail_init))
        )
        if is_compose_state:
            exposing_compose_state.append(name)

        is_state_holder = (
            is_compose_state
            or (tail_type is not None and STATE_HOLDER_TYPE_RE.match(tail_type))
            or (tail_init is not None and STATE_HOLDER_CTOR_RE.match(tail_init))
        )
        if is_state_holder:
            state_holders.append(name)

    for name in exposing_compose_state:
        findings.append(make_finding(
            cls, 'viewmodel-exposes-compose-state',
            f"'{cls.name}.{name}' expõe State/MutableState do runtime do Compose "
            f"diretamente — prefira um backing field privado 'MutableStateFlow' exposto "
            f"como 'StateFlow' (via '.asStateFlow()'), para manter o ViewModel "
            f"desacoplado do runtime do Compose."
        ))

    if len(state_holders) > 1:
        names = ', '.join(state_holders)
        findings.append(make_finding(
            cls, 'viewmodel-multiple-state-holders',
            f"'{cls.name}' expõe {len(state_holders)} propriedades separadas de estado "
            f"({names}) — considere consolidar num único 'data class XxxUiState' exposto "
            f"como uma única fonte de verdade para a tela."
        ))

    return findings
