"""Checagens de uso de coroutines/threading fora dos padrões recomendados pela
documentação oficial de concorrência do Android (viewModelScope/lifecycleScope,
Dispatchers, e a substituição de AsyncTask por coroutines desde API 30)."""
import re

from . import make_finding, make_file_finding

GLOBALSCOPE_RE = re.compile(r'\bGlobalScope\.(launch|async)\b')
RUNBLOCKING_RE = re.compile(r'\brunBlocking\s*[({]')
ASYNCTASK_RE = re.compile(r':\s*AsyncTask\b')
MANUAL_COROUTINESCOPE_RE = re.compile(r'\bCoroutineScope\s*\(')

TEST_PATH_SEGMENTS = ('/test/', '/androidTest/', '/sharedTest/')


def _is_test_file(file_path):
    normalized = file_path.replace('\\', '/')
    return any(seg in normalized for seg in TEST_PATH_SEGMENTS)


def run_file(text, file_path, offsets):
    if not (file_path.endswith('.kt') or file_path.endswith('.java')):
        return []
    findings = []

    for m in GLOBALSCOPE_RE.finditer(text):
        findings.append(make_file_finding(
            file_path, offsets, m.start(), 'globalscope-launch-usage',
            f"'GlobalScope.{m.group(1)}(...)' inicia uma coroutine sem vínculo com nenhum "
            f"ciclo de vida — ela sobrevive à Activity/Fragment/ViewModel que a criou e só "
            f"termina quando o processo morre ou a própria coroutine retorna, o que "
            f"tipicamente causa trabalho desperdiçado (ou pior, callbacks em uma UI já "
            f"destruída) e dificulta cancelamento coordenado. Prefira um escopo estruturado: "
            f"viewModelScope (dentro de ViewModel), lifecycleScope (dentro de Activity/"
            f"Fragment), ou um escopo próprio injetado e cancelado explicitamente.",
        ))

    if not _is_test_file(file_path):
        for m in RUNBLOCKING_RE.finditer(text):
            findings.append(make_file_finding(
                file_path, offsets, m.start(), 'runblocking-outside-tests',
                "'runBlocking { ... }' fora de código de teste bloqueia a thread chamadora até "
                "a coroutine interna terminar — se a thread chamadora for a main thread (comum "
                "em código de Activity/Fragment/ViewModel), isso trava a UI exatamente do jeito "
                "que coroutines existem para evitar. runBlocking é apropriado em testes (onde "
                "bloquear a thread de teste é aceitável) ou em código verdadeiramente "
                "top-level/main() de uma aplicação, não em código de app que roda na UI thread.",
            ))

    for m in ASYNCTASK_RE.finditer(text):
        findings.append(make_file_finding(
            file_path, offsets, m.start(), 'asynctask-subclass-deprecated',
            "Subclasse de 'AsyncTask' — a classe está @Deprecated desde a API 30 (Android "
            "11): tem armadilhas conhecidas de vazamento de memória (referência implícita à "
            "Activity/Fragment que a criou) e comportamento de execução em série por padrão "
            "que surpreende quem espera paralelismo. Migre para coroutines "
            "(viewModelScope/lifecycleScope + Dispatchers.IO) ou, para trabalho que deve "
            "sobreviver ao processo, WorkManager.",
        ))

    return findings


def run_class(cls):
    """Dentro de uma classe ViewModel, construir um CoroutineScope manualmente em vez de
    usar o viewModelScope já fornecido pela biblioteca é um sinal de que o cancelamento
    automático (ligado a onCleared()) está sendo perdido."""
    findings = []
    if cls.kind == 'viewmodel':
        for m in MANUAL_COROUTINESCOPE_RE.finditer(cls.body):
            findings.append(make_finding(
                cls, 'viewmodel-manual-coroutinescope',
                f"ViewModel '{cls.name}' constrói um CoroutineScope manualmente "
                f"('CoroutineScope(...)') em vez de usar 'viewModelScope', que já vem da "
                f"biblioteca androidx.lifecycle:lifecycle-viewmodel-ktx e é cancelado "
                f"automaticamente em onCleared() — um escopo manual precisa desse "
                f"cancelamento sendo replicado à mão (fácil de esquecer, causando coroutines "
                f"que sobrevivem ao ViewModel).",
                offset=m.start(),
            ))
    return findings
