"""Utilidades compartilhadas pelos módulos de checagem em checks/.

Cada módulo de checagem expõe uma ou mais destas funções, conforme fizer sentido para
o tópico:

- `run_class(cls) -> list[dict]` — `cls` é uma instância de AndroidClass (definida em
  scan_android_best_practices.py), representando uma classe Activity/Fragment/ViewModel
  reconhecida pelo nome do supertipo.
- `run_object(obj) -> list[dict]` — `obj` é uma instância de ObjectBlock, representando
  um bloco `object { ... }` ou `companion object { ... }`.
- `run_file(text, file_path, offsets) -> list[dict]` — checagens que operam sobre o
  texto inteiro do arquivo, sem depender de uma classe/objeto reconhecido.
- `run_manifest(text, file_path) -> list[dict]` — só em security_and_manifest.py,
  específico para AndroidManifest.xml.

Todas devolvem findings crus: `{file, line, checkId, message}` — sem topic/severity/
mirrors, que são enriquecidos depois pelo scanner principal via rule_topic_map.json.
"""
import bisect


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


def make_finding(entity, check_id, message, offset=None):
    """Constrói um finding cru a partir de uma AndroidClass ou ObjectBlock. `offset`,
    quando informado, é relativo ao início do corpo (`entity.body_start_offset`) e é
    usado para calcular a linha exata da ocorrência; sem ele, cai de volta para a linha
    de cabeçalho da classe/objeto."""
    if offset is not None:
        line = line_number(entity.offsets, entity.body_start_offset + offset)
    else:
        line = entity.header_line
    return {
        'file': entity.file,
        'line': line,
        'checkId': check_id,
        'message': message,
    }


def make_file_finding(file_path, offsets, pos, check_id, message):
    """Constrói um finding cru relativo a uma posição absoluta no texto inteiro do
    arquivo — usado pelas checagens `run_file`/`run_manifest`, que não têm uma
    AndroidClass/ObjectBlock de referência."""
    return {
        'file': file_path,
        'line': line_number(offsets, pos),
        'checkId': check_id,
        'message': message,
    }
