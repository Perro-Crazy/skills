"""Checagens de tratamento de exceção e null-safety em Kotlin — todas por regex sobre o
texto inteiro do arquivo (não dependem de reconhecer uma classe Android específica),
espelhando regras reais do ruleset padrão do detekt (potential-bugs/empty-blocks)."""
import re

from . import make_file_finding, find_matching

# Operador de asserção de não-nulo ('!!'): exige um caractere de identificador
# imediatamente antes (é um operador postfix sobre uma expressão) para reduzir falsos
# positivos contra sequências como '!= !x' incomuns. Não distingue ocorrências dentro
# de strings/comentários (limitação textual documentada no scanner principal).
NOT_NULL_ASSERTION_RE = re.compile(r'\w!!(?!=)')

CATCH_HEADER_RE = re.compile(r'\bcatch\s*\(\s*(\w+)\s*:\s*([\w.]+)\s*\)\s*')
GENERIC_EXCEPTION_TYPES = {'Exception', 'Throwable', 'RuntimeException'}

PRINTSTACKTRACE_RE = re.compile(r'\.printStackTrace\s*\(\s*\)')


def _iter_catch_blocks(text):
    for m in CATCH_HEADER_RE.finditer(text):
        var_name, exc_type = m.group(1), m.group(2)
        after = text[m.end():]
        ws = len(after) - len(after.lstrip())
        if ws >= len(after) or after[ws] != '{':
            continue
        open_brace = m.end() + ws
        close_brace = find_matching(text, open_brace, '{', '}')
        if close_brace == -1:
            continue
        body = text[open_brace + 1:close_brace]
        yield m, var_name, exc_type, body, open_brace


def run_file(text, file_path, offsets):
    if not (file_path.endswith('.kt') or file_path.endswith('.java')):
        return []
    findings = []

    for m in NOT_NULL_ASSERTION_RE.finditer(text):
        findings.append(make_file_finding(
            file_path, offsets, m.start(), 'not-null-assertion-operator',
            "Operador '!!' — converte um valor potencialmente nulo em uma "
            "NullPointerException explícita caso ele seja nulo em tempo de execução, "
            "descartando o benefício do null-safety do Kotlin no ponto de uso. Prefira "
            "'?.let { }', o operador Elvis '?:' com um fallback explícito, ou (se a "
            "não-nulidade for de fato uma invariante conhecida) 'checkNotNull(x) { "
            "\"mensagem explicando por quê\" }', que ao menos produz uma mensagem de erro "
            "útil em vez de um NPE genérico.",
        ))

    for m in PRINTSTACKTRACE_RE.finditer(text):
        findings.append(make_file_finding(
            file_path, offsets, m.start(), 'printstacktrace-usage',
            "'.printStackTrace()' escreve o stack trace em stderr — em um dispositivo "
            "Android real isso não vai para lugar nenhum útil (não aparece no logcat com "
            "tag/nível filtráveis, não é capturado por ferramentas de crash reporting). "
            "Use Log.e(TAG, \"mensagem\", exception) ou registre a exceção na ferramenta de "
            "observabilidade do projeto (Crashlytics, Sentry etc.).",
        ))

    for m, var_name, exc_type, body, open_brace in _iter_catch_blocks(text):
        stripped_body = body.strip()
        if not stripped_body:
            findings.append(make_file_finding(
                file_path, offsets, m.start(), 'empty-catch-block',
                f"catch ({var_name}: {exc_type}) com corpo vazio — a exceção é silenciosamente "
                f"descartada, o que costuma esconder um bug real em vez de tratá-lo. Se "
                f"ignorar a exceção for realmente intencional, ao menos deixe um comentário "
                f"explicando por quê (ex.: \"// esperado quando X, seguro ignorar\") em vez de "
                f"um bloco vazio indistinguível de 'esqueci de tratar isso'.",
            ))
        elif var_name not in body:
            findings.append(make_file_finding(
                file_path, offsets, m.start(), 'swallowed-exception',
                f"catch ({var_name}: {exc_type}) faz algo no corpo, mas nunca referencia "
                f"'{var_name}' — a exceção capturada não é logada, relançada nem inspecionada "
                f"de forma alguma, então qualquer informação sobre a causa real da falha "
                f"(mensagem, stack trace, tipo específico) se perde. Ao menos logue "
                f"'{var_name}' (Log.e/Log.w) antes de seguir com o fallback.",
            ))

        if exc_type in GENERIC_EXCEPTION_TYPES:
            findings.append(make_file_finding(
                file_path, offsets, m.start(), 'generic-exception-caught',
                f"catch ({var_name}: {exc_type}) captura um tipo genérico demais — engole "
                f"junto qualquer subclasse inesperada (incluindo erros de programação como "
                f"IllegalStateException/NullPointerException que provavelmente deveriam "
                f"propagar e ser corrigidos, não tratados como uma falha de runtime "
                f"recuperável). Capture o(s) tipo(s) de exceção específico(s) que este bloco "
                f"realmente sabe tratar.",
            ))

    return findings
