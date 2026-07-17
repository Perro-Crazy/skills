"""Checagens de performance em listas preguiçosas (LazyColumn/LazyRow/LazyVerticalGrid).

Nenhuma dessas checagens tem cobertura direta em Android Lint/ktlint/detekt hoje —
ver references/lazy-list-performance.md, que usa isso como o exemplo canônico de que
um linter é necessário mas não suficiente para um pass de boas práticas em Compose.
"""
import re

from . import make_finding, find_matching

ITEMS_CALL_RE = re.compile(r'\bitems(Indexed)?\s*\(')


def run(fn):
    findings = []
    body = fn.body or ''

    for m in ITEMS_CALL_RE.finditer(body):
        open_paren = body.find('(', m.start())
        if open_paren == -1:
            continue
        close_paren = find_matching(body, open_paren, '(', ')')
        if close_paren == -1:
            continue
        args = body[open_paren + 1:close_paren]

        if not re.search(r'\bkey\s*=', args):
            findings.append(make_finding(
                fn, 'lazy-items-missing-key',
                "items(...) sem 'key = ' — a identidade dos itens se perde em mutações da lista "
                "(animações quebradas, recomposição desnecessária). Use um id estável por item, "
                "nunca o índice da lista.",
                offset=m.start(),
            ))

        if not re.search(r'\bcontentType\s*=', args):
            findings.append(make_finding(
                fn, 'lazy-items-missing-content-type',
                "items(...) sem 'contentType = ' — se a lista mistura tipos de item heterogêneos, "
                "declarar contentType melhora o reaproveitamento de slots de composição.",
                offset=m.start(),
            ))

    return findings
