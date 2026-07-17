"""Checagens de performance em listas preguiçosas (LazyColumn/LazyRow/LazyVerticalGrid).

Nenhuma dessas checagens tem cobertura direta em Android Lint/ktlint/detekt hoje —
ver references/lazy-list-performance.md, que usa isso como o exemplo canônico de que
um linter é necessário mas não suficiente para um pass de boas práticas em Compose.
"""
import re

from . import make_finding, find_matching

ITEMS_CALL_RE = re.compile(r'\bitems(Indexed)?\s*\(')
MODIFIER_START_RE = re.compile(r'\bModifier\b')
CHAIN_CALL_RE = re.compile(r'\s*\.\s*(\w+)\s*\(')
ITEM_LAMBDA_HEADER_RE = re.compile(r'\s*([\w\s,]+?)\s*->')

# Funções de Modifier dependentes do scope (BoxScope/RowScope/ColumnScope/LazyItemScope) —
# não podem ser hoisted para fora do lambda de item mesmo quando não referenciam o item,
# pois exigem o receiver do scope local.
SCOPE_DEPENDENT_MODIFIER_FNS = {
    'align', 'weight', 'matchParentSize', 'animateItemPlacement', 'animateItem',
}


def _iter_modifier_chains(text):
    """Encontra cada ocorrência da palavra 'Modifier' seguida de uma cadeia de chamadas
    '.nome(...)' (usando find_matching para balancear parênteses aninhados nos argumentos),
    retornando (offset_relativo, texto_da_cadeia) para cada cadeia completa encontrada."""
    chains = []
    for m in MODIFIER_START_RE.finditer(text):
        start = m.start()
        pos = m.end()
        while True:
            call_m = CHAIN_CALL_RE.match(text, pos)
            if not call_m:
                break
            open_paren = text.find('(', call_m.start())
            close_paren = find_matching(text, open_paren, '(', ')')
            if close_paren == -1:
                break
            pos = close_paren + 1
        if pos > m.end():
            chains.append((start, text[start:pos]))
    return chains


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

        after = body[close_paren + 1:]
        ws_len = len(after) - len(after.lstrip())
        if ws_len >= len(after) or after[ws_len] != '{':
            continue  # sem lambda trailing de item — nada a analisar abaixo
        open_brace = close_paren + 1 + ws_len
        close_brace = find_matching(body, open_brace, '{', '}')
        if close_brace == -1:
            continue
        item_body = body[open_brace + 1:close_brace]

        header_m = ITEM_LAMBDA_HEADER_RE.match(item_body)
        item_params = [p.strip() for p in header_m.group(1).split(',') if p.strip()] if header_m else ['it']

        for chain_start, chain_text in _iter_modifier_chains(item_body):
            if item_params and any(re.search(rf'\b{re.escape(p)}\b', chain_text) for p in item_params):
                continue  # cadeia depende do(s) parâmetro(s) do item -> não hoistable
            if any(f'.{scope_fn}(' in chain_text for scope_fn in SCOPE_DEPENDENT_MODIFIER_FNS):
                continue  # depende do scope (BoxScope/RowScope/LazyItemScope) -> não hoistable
            findings.append(make_finding(
                fn, 'lazy-item-modifier-not-hoisted',
                f"Cadeia de Modifier construída dentro do lambda de item ('{chain_text.strip()}') "
                f"não referencia o(s) parâmetro(s) do item — candidata a ser hoisted para uma "
                f"'val' declarada fora do lambda, evitando recriar a cadeia a cada item "
                f"recomposto. Confirme que não há uma variável local derivada do item usada "
                f"na cadeia antes de mover (o scanner só enxerga o nome literal do parâmetro).",
                offset=open_brace + 1 + chain_start,
            ))

    return findings
