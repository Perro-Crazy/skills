#!/usr/bin/env python3
"""Scanner heurístico de boas práticas para Jetpack Compose / Compose Multiplatform.

Não depende de nenhuma configuração de build do projeto-alvo: varre arquivos .kt
recursivamente (ou um arquivo único) e aplica um conjunto de checagens que espelham
regras conhecidas do Android Lint (Compose), ktlint compose-rules e detekt
compose-rules — documentadas em ../references/ e rastreadas em rule_topic_map.json.

Uso:
    python3 scan_compose_components.py --path <arquivo.kt-ou-diretório> [--format json|text] [--topics t1,t2]

Limitações conhecidas (é um heurístico textual, não um parser Kotlin completo):
- Funções com corpo em forma de expressão ('fun Foo() = ...') só passam pelas
  checagens baseadas em assinatura, não nas baseadas em corpo do composable.
- Balanceamento de '<' '>' para genéricos aninhados com tipos função
  (ex.: Map<String, () -> Unit>) pode contar incorretamente o '->' como fechamento
  de generic ao separar parâmetros.
- "Emissores de UI no nível raiz" e "reuso de Modifier" são heurísticas textuais,
  não uma análise de fluxo de dados real — sempre confirme antes de agir sobre elas.
- Funções genéricas com a sintaxe `fun <T> Foo(...)` são reconhecidas; anotações
  muito incomuns ou macros de geração de código podem confundir a detecção de
  limites de função.
Essas limitações são intencionais: o objetivo é sinalizar candidatos com boa
precisão para revisão humana, não substituir um compilador/parser real.
"""
import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from checks import build_line_offsets, line_number, find_matching  # noqa: E402
from checks import (  # noqa: E402
    state_and_recomposition,
    modifier_conventions,
    naming_and_api_shape,
    viewmodel_architecture,
    lazy_list_performance,
)

CHECK_MODULES = [
    state_and_recomposition,
    modifier_conventions,
    naming_and_api_shape,
    viewmodel_architecture,
    lazy_list_performance,
]

FUN_RE = re.compile(r'(?<![\w.])fun\s+(?:<[^>]*>\s+)?(\w+)\s*\(')
ANNOTATION_RE = re.compile(r'@([A-Za-z_][A-Za-z0-9_]*)(\([^)]*\))?')


@dataclass
class ComposableFunction:
    file: str
    name: str
    header_line: int
    params_raw: str
    return_type: str
    body: str
    body_start_offset: int
    annotations: list
    is_private: bool
    offsets: list
    params: list = field(default_factory=list)


def parse_param(param_str):
    s = param_str.strip()
    if not s:
        return None
    s = re.sub(r'^(vararg\s+)?(val|var)\s+', '', s)
    s = re.sub(r'^@\w+(\([^)]*\))?\s+', '', s)
    if ':' not in s:
        return None
    name_part, rest = s.split(':', 1)
    name = name_part.strip().split()[-1] if name_part.strip() else ''
    rest = rest.strip()
    if '=' in rest:
        type_part, default_part = rest.split('=', 1)
        default = default_part.strip()
    else:
        type_part, default = rest, None
    return {'name': name, 'type': type_part.strip(), 'default': default, 'raw': s}


def split_top_level_params(params_raw):
    parts = []
    depth_paren = depth_angle = depth_brace = depth_bracket = 0
    current = []
    in_string = False
    i, n = 0, len(params_raw)
    while i < n:
        c = params_raw[i]
        if in_string:
            current.append(c)
            if c == '\\' and i + 1 < n:
                current.append(params_raw[i + 1])
                i += 2
                continue
            if c == '"':
                in_string = False
            i += 1
            continue
        if c == '"':
            in_string = True
        elif c == '(':
            depth_paren += 1
        elif c == ')':
            depth_paren -= 1
        elif c == '<':
            depth_angle += 1
        elif c == '>':
            depth_angle = max(0, depth_angle - 1)
        elif c == '{':
            depth_brace += 1
        elif c == '}':
            depth_brace -= 1
        elif c == '[':
            depth_bracket += 1
        elif c == ']':
            depth_bracket -= 1

        if c == ',' and depth_paren == depth_angle == depth_brace == depth_bracket == 0:
            parts.append(''.join(current).strip())
            current = []
            i += 1
            continue
        current.append(c)
        i += 1
    tail = ''.join(current).strip()
    if tail:
        parts.append(tail)
    return [p for p in parts if p]


def find_composable_functions(text, file_path):
    offsets = build_line_offsets(text)
    functions = []
    for m in FUN_RE.finditer(text):
        fun_start = m.start()
        name = m.group(1)

        back_start = max(0, fun_start - 400)
        preceding = text[back_start:fun_start]
        cut_idx = max(preceding.rfind('}'), preceding.rfind(';'))
        header_prefix = preceding[cut_idx + 1:] if cut_idx != -1 else preceding
        annotation_names = [a[0] for a in ANNOTATION_RE.findall(header_prefix)]
        if 'Composable' not in annotation_names:
            continue
        is_private = bool(re.search(r'\bprivate\b', header_prefix))

        open_paren = m.end() - 1  # regex termina em '\(' literal
        close_paren = find_matching(text, open_paren, '(', ')')
        if close_paren == -1:
            continue
        params_raw = text[open_paren + 1:close_paren]

        after_params = text[close_paren + 1:close_paren + 300]
        brace_rel = after_params.find('{')
        eq_rel = after_params.find('=')
        return_type = ''
        body = ''
        body_start_offset = fun_start
        if brace_rel != -1 and (eq_rel == -1 or brace_rel < eq_rel):
            return_type = after_params[:brace_rel].lstrip(':').strip()
            open_brace = close_paren + 1 + brace_rel
            close_brace = find_matching(text, open_brace, '{', '}')
            if close_brace != -1:
                body = text[open_brace + 1:close_brace]
                body_start_offset = open_brace + 1
        elif eq_rel != -1:
            return_type = after_params[:eq_rel].lstrip(':').strip()
            # corpo de expressão: não analisado em profundidade (limitação documentada)
            body_start_offset = close_paren + 1 + eq_rel

        header_line = line_number(offsets, fun_start)
        params = [p for p in (parse_param(raw) for raw in split_top_level_params(params_raw)) if p]

        functions.append(ComposableFunction(
            file=file_path,
            name=name,
            header_line=header_line,
            params_raw=params_raw,
            return_type=return_type,
            body=body,
            body_start_offset=body_start_offset,
            annotations=annotation_names,
            is_private=is_private,
            offsets=offsets,
            params=params,
        ))
    return functions


def load_rule_topic_map():
    map_path = Path(__file__).resolve().parent / 'rule_topic_map.json'
    with open(map_path, encoding='utf-8') as f:
        return json.load(f)


def scan_file(path, rule_map):
    text = path.read_text(encoding='utf-8', errors='replace')
    functions = find_composable_functions(text, str(path))
    raw_findings = []
    for fn in functions:
        for module in CHECK_MODULES:
            raw_findings.extend(module.run(fn))

    offsets = build_line_offsets(text)
    raw_findings.extend(modifier_conventions.run_file(text, str(path), offsets))

    enriched = []
    for finding in raw_findings:
        rule = rule_map.get(finding['checkId'], {})
        enriched.append({
            'file': finding['file'],
            'line': finding['line'],
            'checkId': finding['checkId'],
            'topic': rule.get('topic', 'unknown'),
            'severity': rule.get('severity', 'warning'),
            'message': finding['message'],
            'mirrors': rule.get('mirrors'),
            'referencesFile': rule.get('references_file'),
            'examplesFile': rule.get('examples_file'),
        })
    return enriched


def iter_kotlin_files(target):
    if target.is_file():
        if target.suffix == '.kt':
            yield target
        return
    for path in sorted(target.rglob('*.kt')):
        if path.is_file():
            yield path


def group_by_topic(findings):
    grouped = {}
    for f in findings:
        grouped.setdefault(f['topic'], []).append(f)
    return grouped


def format_text(findings):
    if not findings:
        return "Nenhum finding encontrado."
    grouped = group_by_topic(findings)
    lines = []
    for topic in sorted(grouped):
        items = grouped[topic]
        lines.append(f"## {topic} ({len(items)})")
        for f in sorted(items, key=lambda x: (x['file'], x['line'])):
            lines.append(f"  {f['file']}:{f['line']} [{f['severity']}] {f['checkId']} — {f['message']}")
            if f.get('mirrors'):
                lines.append(f"    (espelha: {f['mirrors']})")
            if f.get('referencesFile'):
                lines.append(f"    -> ver {f['referencesFile']}")
        lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--path', required=True, help='Arquivo .kt ou diretório a varrer recursivamente')
    parser.add_argument('--topics', help='Lista separada por vírgula de tópicos a incluir (default: todos)')
    parser.add_argument('--format', choices=['json', 'text'], default='text')
    args = parser.parse_args()

    target = Path(args.path).resolve()
    if not target.exists():
        print(f"Caminho não encontrado: {target}", file=sys.stderr)
        sys.exit(2)

    rule_map = load_rule_topic_map()
    all_findings = []
    for kt_file in iter_kotlin_files(target):
        all_findings.extend(scan_file(kt_file, rule_map))

    if args.topics:
        wanted = {t.strip() for t in args.topics.split(',') if t.strip()}
        all_findings = [f for f in all_findings if f['topic'] in wanted]

    if args.format == 'json':
        print(json.dumps(all_findings, indent=2, ensure_ascii=False))
    else:
        print(format_text(all_findings))


if __name__ == '__main__':
    main()
