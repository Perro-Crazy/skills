"""Checagens de convenção de parâmetro Modifier.

Ver references/modifier-conventions.md para o racional completo de cada regra.
"""
import re

from . import make_finding, line_number, EMITTING_COMPOSABLES

COMPOSED_USAGE_RE = re.compile(r'\bcomposed\s*[({]')


def _find_modifier_param(fn):
    for p in fn.params:
        if p['type'].strip() == 'Modifier':
            return p
    return None


def _find_all_modifier_params(fn):
    return [p for p in fn.params if p['type'].strip() == 'Modifier']


def _body_emits_ui(fn):
    if not fn.body:
        return False
    return any(re.search(rf'\b{name}\s*\(', fn.body) for name in EMITTING_COMPOSABLES)


def run(fn):
    findings = []

    modifier_params_all = _find_all_modifier_params(fn)
    if len(modifier_params_all) > 1:
        names = ', '.join(p['name'] for p in modifier_params_all)
        findings.append(make_finding(
            fn, 'multiple-modifier-params',
            f"'{fn.name}' declara {len(modifier_params_all)} parâmetros do tipo Modifier "
            f"({names}) — a convenção é expor exatamente um parâmetro Modifier; resolva a "
            f"necessidade de customizar múltiplas regiões internamente (ex.: via "
            f"'.then(...)' em cada filho, ou compondo o layout de outro jeito)."
        ))

    modifier_param = _find_modifier_param(fn)

    if modifier_param is None:
        if _body_emits_ui(fn):
            findings.append(make_finding(
                fn, 'modifier-param-missing',
                f"'{fn.name}' emite UI mas não expõe um parâmetro 'modifier: Modifier = Modifier' "
                f"— sem isso, quem chama não consegue ajustar layout/tamanho/semântica de fora."
            ))
        return findings

    if modifier_param['name'] != 'modifier':
        findings.append(make_finding(
            fn, 'modifier-param-wrong-name',
            f"Parâmetro do tipo Modifier chamado '{modifier_param['name']}' — a convenção é "
            f"nomeá-lo exatamente 'modifier'."
        ))

    if not modifier_param['default'] or modifier_param['default'].strip() != 'Modifier':
        findings.append(make_finding(
            fn, 'modifier-param-no-default',
            f"Parâmetro '{modifier_param['name']}: Modifier' não tem valor default '= Modifier' "
            f"— sem default, o composable não pode ser usado sem passar um Modifier explícito."
        ))

    if fn.body:
        mod_name = modifier_param['name']
        # conta apenas ocorrências como *valor* (ex.: 'modifier = modifier', ou 'modifier)'),
        # não como rótulo de argumento nomeado — 'modifier = xyz' não deve contar o rótulo.
        value_re = re.compile(rf'\b{re.escape(mod_name)}\b(?!\s*=(?!=))')
        matches = list(value_re.finditer(fn.body))
        if len(matches) >= 2:
            findings.append(make_finding(
                fn, 'modifier-reused',
                f"'{mod_name}' é passado como valor {len(matches)}x no corpo — confirme que a "
                f"mesma instância não está sendo aplicada a múltiplos filhos irmãos (cada filho "
                f"deveria receber seu próprio encadeamento de Modifier, senão modificações por "
                f"filho são perdidas).",
                offset=matches[0].start(),
            ))

        then_re = re.compile(rf'\.then\s*\(\s*{re.escape(mod_name)}\s*\)')
        for m in then_re.finditer(fn.body):
            findings.append(make_finding(
                fn, 'modifier-chain-order-risk',
                f"'.then({mod_name})' encontrado — o '{mod_name}' recebido do chamador está "
                f"sendo anexado ao FINAL da cadeia, o que inverte a precedência esperada. A "
                f"convenção é aplicar o '{mod_name}' recebido primeiro na cadeia (ex.: "
                f"'{mod_name}.background(...)'), não anexá-lo via '.then(...)' no final.",
                offset=m.start(),
            ))

    return findings


def run_file(text, file_path, offsets):
    """Checagem em nível de arquivo: Modifier.composed{} é tipicamente usado para
    declarar extension functions de Modifier (ex.: `fun Modifier.foo() = composed { ... }`),
    que não são anotadas @Composable — por isso essa checagem não pode viver em run(fn)
    (que só enxerga corpos de funções @Composable) e precisa varrer o arquivo inteiro."""
    findings = []
    for m in COMPOSED_USAGE_RE.finditer(text):
        findings.append({
            'file': file_path,
            'line': line_number(offsets, m.start()),
            'checkId': 'modifier-composed-deprecated',
            'message': "Uso de Modifier.composed{} — prefira migrar para uma "
                       "ModifierNodeElement/Modifier.Node customizada (composed{} recompõe a "
                       "cada chamada e está em depreciação gradual).",
        })
    return findings
