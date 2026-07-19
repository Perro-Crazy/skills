"""Checagens de segurança do AndroidManifest.xml e de segredos/URLs hardcoded no código.

`run_manifest` opera sobre AndroidManifest.xml via xml.etree.ElementTree (stdlib), com
um TreeBuilder customizado para recuperar número de linha a partir do parser Expat
subjacente (ElementTree não expõe isso por padrão). `run_file` opera por regex sobre
texto de .kt/.java, como os demais módulos.
"""
import re
import xml.parsers.expat as expat

from . import make_file_finding

ANDROID_NS = 'http://schemas.android.com/apk/res/android'
# xml.etree.ElementTree's XMLParser não expõe o parser Expat subjacente de forma estável
# entre versões do Python (o acelerador C não tem o atributo `.parser`/`._parser`), então
# este módulo usa xml.parsers.expat diretamente — ainda stdlib puro, mas nos dá acesso
# direto a CurrentLineNumber em cada callback de abertura de tag, sem depender de detalhe
# de implementação do ElementTree.


class _Node:
    __slots__ = ('tag', 'attrib', 'line', 'children')

    def __init__(self, tag, attrib, line):
        self.tag = tag
        self.attrib = attrib
        self.line = line
        self.children = []

    def find(self, tag):
        for c in self.children:
            if c.tag == tag:
                return c
        return None

    def findall(self, tag):
        return [c for c in self.children if c.tag == tag]


def _parse_manifest(text):
    stack = []
    roots = []

    def on_start(name, attrs):
        node = _Node(name, attrs, parser.CurrentLineNumber)
        if stack:
            stack[-1].children.append(node)
        else:
            roots.append(node)
        stack.append(node)

    def on_end(name):
        stack.pop()

    parser = expat.ParserCreate(namespace_separator=' ')
    parser.StartElementHandler = on_start
    parser.EndElementHandler = on_end
    parser.Parse(text, True)
    if not roots:
        raise expat.ExpatError('manifest sem elemento raiz')
    return roots[0]


def _attr(elem, name):
    return elem.attrib.get(ANDROID_NS + ' ' + name)


def _line_of(elem, fallback=1):
    return elem.line if elem is not None else fallback


def run_manifest(text, file_path):
    findings = []
    try:
        root = _parse_manifest(text)
    except expat.ExpatError:
        return findings  # manifest malformado -> degradação graciosa, não é erro do scanner

    app = root.find('application')
    if app is None:
        return findings
    app_line = _line_of(app)

    if _attr(app, 'allowBackup') == 'true':
        findings.append({
            'file': file_path, 'line': app_line, 'checkId': 'manifest-allow-backup-enabled',
            'message': "<application android:allowBackup=\"true\"> permite que o Android "
                       "faça backup completo do app (adb backup, backup automático na nuvem) "
                       "sem controle sobre o que é incluído — dados sensíveis (tokens, "
                       "credenciais em SharedPreferences/DB) podem vazar em um backup extraído. "
                       "Se o app não lida com dados sensíveis, defina explicitamente `false` ou "
                       "use android:fullBackupContent/android:dataExtractionRules para excluir "
                       "o que for sensível.",
        })

    if _attr(app, 'debuggable') == 'true':
        findings.append({
            'file': file_path, 'line': app_line, 'checkId': 'manifest-debuggable-enabled',
            'message': "<application android:debuggable=\"true\"> hardcoded no manifest "
                       "expõe o app a debug (incluindo em builds que acabem indo pra produção "
                       "por engano) e desabilita algumas proteções do runtime. O Android Gradle "
                       "Plugin já define isso automaticamente por build type "
                       "(debug=true/release=false) — remova o atributo do manifest e deixe o "
                       "build type controlar.",
        })

    if _attr(app, 'usesCleartextTraffic') == 'true':
        findings.append({
            'file': file_path, 'line': app_line, 'checkId': 'manifest-cleartext-traffic-enabled',
            'message': "<application android:usesCleartextTraffic=\"true\"> permite tráfego "
                       "HTTP não criptografado para qualquer host — dados em trânsito (incluindo "
                       "tokens de sessão) ficam expostos a interceptação. Desde API 28 o default "
                       "já é `false`; prefira uma Network Security Config com exceções pontuais "
                       "por domínio (ex.: só para um host de desenvolvimento local) em vez de "
                       "liberar globalmente.",
        })

    for tag in ('receiver', 'service', 'provider'):
        for comp in app.findall(tag):
            if _attr(comp, 'exported') == 'true' and _attr(comp, 'permission') is None:
                comp_name = _attr(comp, 'name') or f'<{tag} sem android:name>'
                findings.append({
                    'file': file_path, 'line': _line_of(comp, app_line),
                    'checkId': 'manifest-component-exported-without-permission',
                    'message': f"<{tag} android:name=\"{comp_name}\" android:exported=\"true\"> "
                               f"sem android:permission — qualquer app instalado no dispositivo "
                               f"pode invocar este componente diretamente (enviar um broadcast, "
                               f"iniciar o service, consultar o provider), mesmo sem ter sido "
                               f"convidado a interagir com o seu app. Se a exposição for "
                               f"intencional (ex.: um provider consumido por outro app do mesmo "
                               f"fabricante), restrinja com android:permission (uma permission "
                               f"signature-level, tipicamente) em vez de deixar aberto.",
                })

    return findings


# Nome de variável sugerindo segredo (case-insensitive) + valor literal não trivial
# (>= 6 chars, sem interpolação `$`, já que uma string com "${...}" claramente não é um
# valor fixo). Evita casos como `val apiKeyHeader: String = "Authorization"` na medida do
# possível (nome não bate) mas é heurística — confirme lendo o código antes de agir.
SECRET_ASSIGNMENT_RE = re.compile(
    r'\b(?:val|var|const\s+val)\s+'
    r'(\w*(?:api[_-]?key|secret|token|password|passwd|access[_-]?key|private[_-]?key|client[_-]?secret)\w*)'
    r'\s*(?::\s*String)?\s*=\s*"([^"$]{6,})"',
    re.IGNORECASE,
)

HTTP_URL_RE = re.compile(
    r'"http://(?!localhost|127\.0\.0\.1|10\.0\.2\.2)[^"\s]+"'
)


def run_file(text, file_path, offsets):
    if not (file_path.endswith('.kt') or file_path.endswith('.java')):
        return []
    findings = []

    for m in SECRET_ASSIGNMENT_RE.finditer(text):
        findings.append(make_file_finding(
            file_path, offsets, m.start(1), 'hardcoded-secret-literal',
            f"Propriedade '{m.group(1)}' inicializada com uma string literal fixa — se este "
            f"for de fato um segredo (API key, token, senha), ele fica embutido no APK/AAB e "
            f"pode ser extraído por qualquer pessoa (o bytecode Kotlin/Java é trivial de "
            f"descompilar). Mova para um mecanismo fora do controle de versão (local.properties "
            f"+ BuildConfig, um secrets manager, ou pelo menos gradle.properties fora do git) e "
            f"confirme antes de aplicar — o scanner não sabe se este valor é de fato sensível ou "
            f"um placeholder/nome de header inofensivo.",
        ))

    for m in HTTP_URL_RE.finditer(text):
        findings.append(make_file_finding(
            file_path, offsets, m.start(), 'hardcoded-http-url',
            "URL literal usando 'http://' em vez de 'https://' — tráfego não criptografado "
            "para este host específico, independente da configuração de "
            "usesCleartextTraffic/Network Security Config do app. Confirme se o endpoint "
            "realmente não suporta TLS antes de mudar (times de integração às vezes hardcoded "
            "um endpoint de homologação http de propósito).",
        ))

    return findings
