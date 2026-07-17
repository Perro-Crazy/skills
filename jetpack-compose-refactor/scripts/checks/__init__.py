"""Utilidades compartilhadas pelos módulos de checagem em checks/.

Cada módulo de checagem expõe uma função `run(fn) -> list[dict]`, onde `fn` é uma
instância de ComposableFunction (definida em scan_compose_components.py) e o retorno
é uma lista de findings crus (sem topic/severity/mirrors — isso é enriquecido depois
via rule_topic_map.json pelo scanner principal).
"""
import bisect

EMITTING_COMPOSABLES = {
    "Box", "Row", "Column", "LazyColumn", "LazyRow", "LazyVerticalGrid", "LazyHorizontalGrid",
    "Text", "Image", "Icon", "IconButton", "Button", "OutlinedButton", "TextButton",
    "ElevatedButton", "FilledTonalButton", "Card", "ElevatedCard", "OutlinedCard", "Surface",
    "Scaffold", "TopAppBar", "BottomAppBar", "NavigationBar", "NavigationRail", "Divider",
    "HorizontalDivider", "VerticalDivider", "Spacer", "TextField", "OutlinedTextField",
    "Checkbox", "RadioButton", "Switch", "Slider", "RangeSlider", "CircularProgressIndicator",
    "LinearProgressIndicator", "AlertDialog", "Dialog", "ModalBottomSheet", "BottomSheetScaffold",
    "FloatingActionButton", "ExtendedFloatingActionButton", "ConstraintLayout", "BoxWithConstraints",
    "Chip", "AssistChip", "FilterChip", "InputChip", "Tab", "TabRow", "NavigationBarItem",
    "NavigationDrawerItem", "ModalNavigationDrawer", "Snackbar", "SnackbarHost",
}


def find_matching(text, open_pos, open_char, close_char):
    """Encontra o índice do fechamento correspondente a text[open_pos] == open_char,
    ignorando ocorrências dentro de strings/chars/comentários. Retorna -1 se não achar."""
    depth = 0
    i = open_pos
    n = len(text)
    in_string = False
    in_char = False
    in_line_comment = False
    in_block_comment = False
    triple_quote = False
    while i < n:
        c = text[i]
        if in_line_comment:
            if c == '\n':
                in_line_comment = False
            i += 1
            continue
        if in_block_comment:
            if c == '*' and i + 1 < n and text[i + 1] == '/':
                in_block_comment = False
                i += 2
                continue
            i += 1
            continue
        if in_string:
            if c == '\\':
                i += 2
                continue
            if triple_quote:
                if text[i:i + 3] == '"""':
                    in_string = False
                    triple_quote = False
                    i += 3
                    continue
                i += 1
                continue
            if c == '"':
                in_string = False
            i += 1
            continue
        if in_char:
            if c == '\\':
                i += 2
                continue
            if c == "'":
                in_char = False
            i += 1
            continue
        if c == '/' and i + 1 < n and text[i + 1] == '/':
            in_line_comment = True
            i += 2
            continue
        if c == '/' and i + 1 < n and text[i + 1] == '*':
            in_block_comment = True
            i += 2
            continue
        if text[i:i + 3] == '"""':
            in_string = True
            triple_quote = True
            i += 3
            continue
        if c == '"':
            in_string = True
            i += 1
            continue
        if c == "'":
            in_char = True
            i += 1
            continue
        if c == open_char:
            depth += 1
        elif c == close_char:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def build_line_offsets(text):
    offsets = [0]
    for i, c in enumerate(text):
        if c == '\n':
            offsets.append(i + 1)
    return offsets


def line_number(offsets, pos):
    return bisect.bisect_right(offsets, pos)


def make_finding(fn, check_id, message, offset=None):
    """Constrói um finding cru. `offset`, quando informado, é relativo ao início do
    corpo da função (fn.body_start_offset) e é usado para calcular o número de linha
    exato da ocorrência; sem ele, cai de volta para a linha da assinatura da função."""
    if offset is not None:
        line = line_number(fn.offsets, fn.body_start_offset + offset)
    else:
        line = fn.header_line
    return {
        'file': fn.file,
        'line': line,
        'checkId': check_id,
        'message': message,
    }
