"""Checagens de separação de camadas — ViewModel retendo uma referência Android-específica
de ciclo de vida curto, e Activity/Fragment instanciando diretamente um cliente de rede/DB
que deveria vir de injeção de dependência, seguindo o Guide to App Architecture oficial."""
import re

from . import make_finding

# Mesma lista de tipos "de ciclo de vida curto" que context_and_lifecycle.py, mas aplicada
# ao construtor/corpo de uma classe ViewModel: mesmo raciocínio de vazamento, ângulo
# diferente (aqui é "isto não deveria nem estar aqui", não "isto está sendo retido demais
# num object"). Deliberadamente exclui `Application` — AndroidViewModel(application) é o
# padrão oficial suportado para quando um ViewModel realmente precisa de um Context.
UI_REFERENCE_TYPE_RE = re.compile(
    r'\b(?:private\s+)?(?:val|var)\s+(\w+)\s*:\s*(Context|Activity|\w+Activity|View|Fragment|\w+Fragment)\??\b'
)

NETWORK_OR_DB_CLIENT_RE = re.compile(
    r'\b(?:Retrofit\.Builder\s*\(\s*\)|OkHttpClient\s*\(\s*\)|Room\.databaseBuilder\s*\()'
)


def run_class(cls):
    findings = []

    if cls.kind == 'viewmodel':
        for source, label in ((cls.ctor_raw, 'construtor'), (cls.body, 'corpo')):
            for m in UI_REFERENCE_TYPE_RE.finditer(source):
                prop_name, type_name = m.group(1), m.group(2)
                offset = None if source is cls.ctor_raw else m.start(1)
                findings.append(make_finding(
                    cls, 'viewmodel-holds-android-ui-reference',
                    f"ViewModel '{cls.name}' ({label}) retém '{prop_name}: {type_name}' — "
                    f"um ViewModel sobrevive a mudanças de configuração (rotação de tela etc.) "
                    f"e pode sobreviver à Activity/Fragment/View original inteiramente; "
                    f"segurar uma referência direta a um desses tipos é a causa mais comum de "
                    f"'Activity leaked' em apps Android. Se o ViewModel genuinamente precisa "
                    f"de um Context, use AndroidViewModel + getApplication() (o único Context "
                    f"seguro de reter por toda a vida do ViewModel); se precisa notificar a UI "
                    f"de algo, prefira expor estado observável (StateFlow/LiveData) que a "
                    f"UI observa, em vez de a ViewModel referenciar a UI diretamente.",
                    offset=offset,
                ))

    if cls.kind in ('activity', 'fragment'):
        for m in NETWORK_OR_DB_CLIENT_RE.finditer(cls.body):
            findings.append(make_finding(
                cls, 'ui-layer-instantiates-network-or-db-client',
                f"{cls.kind.capitalize()} '{cls.name}' instancia um cliente de rede/banco "
                f"diretamente ('{m.group(0)}') — segundo o Guide to App Architecture oficial, "
                f"a camada de UI (Activity/Fragment/Composable) não deveria conhecer detalhes "
                f"de como os dados são obtidos; isso acopla a tela a uma implementação "
                f"concreta (dificulta testar a UI isoladamente, trocar a fonte de dados, ou "
                f"reaproveitar a mesma instância entre telas). Mova a criação para uma camada "
                f"de repositório/data source, injetada no ViewModel (via Hilt/Koin/construtor "
                f"manual), e deixe a UI depender só do ViewModel.",
                offset=m.start(),
            ))

    return findings
