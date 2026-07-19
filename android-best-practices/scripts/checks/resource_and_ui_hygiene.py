"""Checagens de strings/cores hardcoded fora do sistema de recursos, e de logging via
stdout em vez do logcat estruturado."""
import re

from . import make_file_finding

HARDCODED_UI_STRING_RE = re.compile(
    r'\b(?:setText|setTitle|setMessage|setPositiveButtonText|setNegativeButtonText)\s*'
    r'\(\s*"([^"{}%]{2,})"\s*\)'
    r'|Toast\.makeText\([^,]+,\s*"([^"{}%]{2,})"'
)

HARDCODED_HEX_COLOR_RE = re.compile(r'Color\.parseColor\(\s*"(#[0-9A-Fa-f]{6,8})"\s*\)')

PRINTLN_RE = re.compile(r'(?<!\.)\bprintln\s*\(')
SYSTEM_OUT_RE = re.compile(r'\bSystem\.out\.print(?:ln)?\s*\(')

TEST_PATH_SEGMENTS = ('/test/', '/androidTest/', '/sharedTest/')


def _is_test_file(file_path):
    normalized = file_path.replace('\\', '/')
    return any(seg in normalized for seg in TEST_PATH_SEGMENTS)


def run_file(text, file_path, offsets):
    if not (file_path.endswith('.kt') or file_path.endswith('.java')):
        return []
    findings = []

    for m in HARDCODED_UI_STRING_RE.finditer(text):
        literal = m.group(1) or m.group(2)
        findings.append(make_file_finding(
            file_path, offsets, m.start(), 'hardcoded-user-facing-string',
            f"String de UI literal (\"{literal}\") passada direto para uma chamada de "
            f"exibição em vez de vir de um recurso — impede localização (o app não pode "
            f"ser traduzido sem editar código-fonte) e espalha texto de produto pelo "
            f"código em vez de centralizá-lo em strings.xml. Mova para "
            f"'<string name=\"...\">{literal}</string>' e referencie via "
            f"'getString(R.string....)' / 'context.getString(...)' / 'stringResource(...)' "
            f"(Compose).",
        ))

    for m in HARDCODED_HEX_COLOR_RE.finditer(text):
        findings.append(make_file_finding(
            file_path, offsets, m.start(), 'hardcoded-hex-color',
            f"Cor hexadecimal literal ('{m.group(1)}') passada para Color.parseColor(...) em "
            f"vez de um recurso de cor — dificulta reaproveitar a mesma cor em outro lugar de "
            f"forma consistente (ou trocá-la de uma vez em dark mode/rebrand). Prefira "
            f"'<color name=\"...\">{m.group(1)}</color>' em colors.xml + "
            f"'ContextCompat.getColor(context, R.color....)', ou um token de tema "
            f"(MaterialTheme.colorScheme, se o projeto usa Compose).",
        ))

    if not _is_test_file(file_path):
        for m in PRINTLN_RE.finditer(text):
            findings.append(make_file_finding(
                file_path, offsets, m.start(), 'println-instead-of-log',
                "'println(...)' escreve em stdout — em um dispositivo Android real isso não "
                "aparece no logcat com tag/nível filtráveis, e builds de release tipicamente "
                "não têm ninguém observando stdout. Use android.util.Log "
                "(Log.d/Log.i/Log.w/Log.e) com uma TAG consistente, que integra com o "
                "logcat e com ferramentas de observabilidade.",
            ))
        for m in SYSTEM_OUT_RE.finditer(text):
            findings.append(make_file_finding(
                file_path, offsets, m.start(), 'println-instead-of-log',
                "'System.out.print(...)' — mesma observação que 'println(...)': prefira "
                "android.util.Log para saída que precisa ser observável em um dispositivo "
                "Android real.",
            ))

    return findings
