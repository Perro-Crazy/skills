#!/usr/bin/env python3
"""Scanner heurístico de boas práticas gerais para desenvolvimento Android (Kotlin/Java
+ AndroidManifest.xml).

Não depende de nenhuma configuração de build do projeto-alvo: varre arquivos
.kt/.java/AndroidManifest.xml recursivamente (ou um arquivo único) e aplica um conjunto
de checagens que espelham, quando existe uma fonte real, regras conhecidas de Android
Lint e do ruleset padrão do detekt (não é específico de Jetpack Compose — ver o skill
irmão `jetpack-compose-refactor` para isso) — documentadas em ../references/ e
rastreadas em rule_topic_map.json.

Uso:
    python3 scan_android_best_practices.py --path <arquivo-ou-diretório> [--format json|text] [--topics t1,t2]

Limitações conhecidas (é um heurístico textual, não um parser Kotlin/Java/XML completo):
- Classes só são classificadas como Activity/Fragment/ViewModel pelo nome literal do
  supertipo escrito na própria declaração (ex.: `class Foo : AppCompatActivity()`) —
  não resolve herança indireta entre arquivos (uma classe que estende uma base própria
  que só indiretamente estende Activity/Fragment/ViewModel não é reconhecida).
  Componentes Service/BroadcastReceiver/Application deliberadamente não são
  classificados por nome de classe (o sufixo "Service"/"Receiver" é comum demais em
  nomes de classes de domínio não relacionadas ao Android para servir de heurística
  confiável) — checagens sobre esses componentes vivem em AndroidManifest.xml, onde a
  tag já desambigua.
- `!!` (asserção de não-nulo), `printStackTrace()`, blocos catch etc. são detectados por
  regex no texto inteiro do arquivo — não distinguem uma ocorrência dentro de uma string
  literal ou comentário de uma ocorrência real de código (limitação textual conhecida;
  falsos positivos aqui são raros na prática mas existem).
- Checagens de AndroidManifest.xml usam `xml.etree.ElementTree` (stdlib) com um
  TreeBuilder customizado para recuperar número de linha via `CurrentLineNumber` do
  parser Expat subjacente — funciona para manifests bem formados; um manifest
  malformado (erro de XML) é ignorado silenciosamente (lista vazia), não é um erro do
  scanner.
Essas limitações são intencionais: o objetivo é sinalizar candidatos com boa precisão
para revisão humana, não substituir um compilador/parser real.
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
    security_and_manifest,
    context_and_lifecycle,
    coroutines_and_threading,
    error_handling_and_null_safety,
    resource_and_ui_hygiene,
    architecture_and_di,
)

# Módulos que expõem run_file(text, file_path, offsets) — rodam contra todo arquivo
# .kt/.java, independente de reconhecer alguma classe Android nele.
FILE_CHECK_MODULES = [
    security_and_manifest,
    context_and_lifecycle,
    coroutines_and_threading,
    error_handling_and_null_safety,
    resource_and_ui_hygiene,
]

# Módulos que expõem run_class(cls) para AndroidClass (Activity/Fragment/ViewModel).
CLASS_CHECK_MODULES = [
    context_and_lifecycle,
    coroutines_and_threading,
    architecture_and_di,
]

# Módulos que expõem run_object(obj) para ObjectBlock (object / companion object).
OBJECT_CHECK_MODULES = [
    context_and_lifecycle,
]

CLASS_RE = re.compile(r'(?<![\w.])class\s+(\w+)\b')
OBJECT_START_RE = re.compile(r'(?<![\w.])(companion\s+object|object)\b\s*(\w+)?')
CTOR_MODIFIER_RE = re.compile(r'\s*(private|public|internal|protected)?\s*(constructor\s*)?')

# Ordem importa pouco aqui (os três termos não se sobrepõem), mas viewmodel vem primeiro
# por convenção. `\b` só no fim do termo, de propósito: "BaseViewModel"/"AndroidViewModel"
# terminam em "ViewModel" mas não começam com ele, então um \b inicial os excluiria.
ANDROID_KIND_MARKERS = [
    ('viewmodel', re.compile(r'ViewModel\b')),
    ('activity', re.compile(r'Activity\b')),
    ('fragment', re.compile(r'Fragment\b')),
]


@dataclass
class AndroidClass:
    file: str
    name: str
    kind: str  # 'viewmodel' | 'activity' | 'fragment'
    header_line: int
    heritage: str
    ctor_raw: str
    body: str
    body_start_offset: int
    offsets: list


@dataclass
class ObjectBlock:
    file: str
    name: str
    kind: str  # 'object' | 'companion_object'
    header_line: int
    body: str
    body_start_offset: int
    offsets: list


def find_android_classes(text, file_path):
    """Encontra classes cujo supertipo direto (escrito no próprio arquivo) bate com
    ViewModel/Activity/Fragment — ver ANDROID_KIND_MARKERS e limitações no docstring do
    módulo. Só classes com uma cláusula de herança explícita (`:`) antes do `{` de
    abertura do corpo são consideradas candidatas."""
    offsets = build_line_offsets(text)
    classes = []
    for m in CLASS_RE.finditer(text):
        name = m.group(1)
        pos = m.end()

        if pos < len(text) and text[pos] == '<':
            close = find_matching(text, pos, '<', '>')
            pos = close + 1 if close != -1 else pos

        pos = CTOR_MODIFIER_RE.match(text, pos).end()

        ctor_raw = ''
        if pos < len(text) and text[pos] == '(':
            close_paren = find_matching(text, pos, '(', ')')
            if close_paren == -1:
                continue
            ctor_raw = text[pos + 1:close_paren]
            pos = close_paren + 1

        window = text[pos:pos + 500]
        brace_rel = window.find('{')
        if brace_rel == -1:
            continue
        header_tail = window[:brace_rel]
        if ':' not in header_tail:
            continue  # sem herança explícita -> não reconhecível por nome de supertipo

        kind = None
        for candidate_kind, pattern in ANDROID_KIND_MARKERS:
            if pattern.search(header_tail):
                kind = candidate_kind
                break
        if kind is None:
            continue

        open_brace = pos + brace_rel
        close_brace = find_matching(text, open_brace, '{', '}')
        if close_brace == -1:
            continue

        classes.append(AndroidClass(
            file=file_path,
            name=name,
            kind=kind,
            header_line=line_number(offsets, m.start()),
            heritage=header_tail.strip(),
            ctor_raw=ctor_raw,
            body=text[open_brace + 1:close_brace],
            body_start_offset=open_brace + 1,
            offsets=offsets,
        ))
    return classes


def find_object_blocks(text, file_path):
    """Encontra blocos `object Nome { ... }` e `companion object { ... }` — usado pela
    checagem de campo estático segurando Context/Activity/View (static-field-leaks-context).
    Heurística textual: não resolve se o `object` está aninhado dentro de outra classe ou
    é top-level, nem detecta o tipo de dado real de uma propriedade cujo tipo não está
    anotado explicitamente."""
    offsets = build_line_offsets(text)
    blocks = []
    for m in OBJECT_START_RE.finditer(text):
        kind = 'companion_object' if m.group(1).startswith('companion') else 'object'
        name = m.group(2) or ('Companion' if kind == 'companion_object' else '<anonymous>')
        pos = m.end()

        window = text[pos:pos + 300]
        brace_rel = window.find('{')
        if brace_rel == -1:
            continue

        open_brace = pos + brace_rel
        close_brace = find_matching(text, open_brace, '{', '}')
        if close_brace == -1:
            continue

        blocks.append(ObjectBlock(
            file=file_path,
            name=name,
            kind=kind,
            header_line=line_number(offsets, m.start()),
            body=text[open_brace + 1:close_brace],
            body_start_offset=open_brace + 1,
            offsets=offsets,
        ))
    return blocks


def load_rule_topic_map():
    map_path = Path(__file__).resolve().parent / 'rule_topic_map.json'
    with open(map_path, encoding='utf-8') as f:
        return json.load(f)


def enrich(raw_findings, rule_map):
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


def scan_source_file(path, rule_map):
    text = path.read_text(encoding='utf-8', errors='replace')
    offsets = build_line_offsets(text)
    raw_findings = []

    for cls in find_android_classes(text, str(path)):
        for module in CLASS_CHECK_MODULES:
            if hasattr(module, 'run_class'):
                raw_findings.extend(module.run_class(cls))

    for obj in find_object_blocks(text, str(path)):
        for module in OBJECT_CHECK_MODULES:
            if hasattr(module, 'run_object'):
                raw_findings.extend(module.run_object(obj))

    for module in FILE_CHECK_MODULES:
        if hasattr(module, 'run_file'):
            raw_findings.extend(module.run_file(text, str(path), offsets))

    return enrich(raw_findings, rule_map)


def scan_manifest_file(path, rule_map):
    text = path.read_text(encoding='utf-8', errors='replace')
    raw_findings = security_and_manifest.run_manifest(text, str(path))
    return enrich(raw_findings, rule_map)


def iter_target_files(target):
    """Produz tuplas (kind, path) onde kind é 'source' (.kt/.java) ou 'manifest'
    (AndroidManifest.xml, por nome de arquivo exato)."""
    if target.is_file():
        if target.name == 'AndroidManifest.xml':
            yield ('manifest', target)
        elif target.suffix in ('.kt', '.java'):
            yield ('source', target)
        return
    for path in sorted(target.rglob('*')):
        if not path.is_file():
            continue
        if path.name == 'AndroidManifest.xml':
            yield ('manifest', path)
        elif path.suffix in ('.kt', '.java'):
            yield ('source', path)


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
    parser.add_argument('--path', required=True, help='Arquivo (.kt/.java/AndroidManifest.xml) ou diretório a varrer recursivamente')
    parser.add_argument('--topics', help='Lista separada por vírgula de tópicos a incluir (default: todos)')
    parser.add_argument('--format', choices=['json', 'text'], default='text')
    args = parser.parse_args()

    target = Path(args.path).resolve()
    if not target.exists():
        print(f"Caminho não encontrado: {target}", file=sys.stderr)
        sys.exit(2)

    rule_map = load_rule_topic_map()
    all_findings = []
    for kind, file_path in iter_target_files(target):
        if kind == 'source':
            all_findings.extend(scan_source_file(file_path, rule_map))
        else:
            all_findings.extend(scan_manifest_file(file_path, rule_map))

    if args.topics:
        wanted = {t.strip() for t in args.topics.split(',') if t.strip()}
        all_findings = [f for f in all_findings if f['topic'] in wanted]

    if args.format == 'json':
        print(json.dumps(all_findings, indent=2, ensure_ascii=False))
    else:
        print(format_text(all_findings))


if __name__ == '__main__':
    main()
