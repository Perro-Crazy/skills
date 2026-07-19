"""Checagens de vazamento de memória por Context/View/Activity retido além do seu ciclo
de vida — a família de bugs mais comum e mais cara de diagnosticar em apps Android
(LeakCanary existe basicamente por causa desta classe de problema).
"""
import re

from . import make_finding, make_file_finding, find_matching

# Tipos cujo valor "vivo" quase sempre está atrelado a um ciclo de vida curto
# (Activity/Fragment) — reter uma instância deles além desse ciclo de vida é o padrão
# clássico de vazamento. Deliberadamente NÃO inclui `Application` (context de app inteiro,
# seguro de reter estaticamente).
_LEAKY_CONTEXT_TYPE_ALT = r'Context|Activity|\w+Activity|View|\w+Fragment'

STATIC_FIELD_RE = re.compile(
    r'\b(?:private\s+)?(?:val|var)\s+(\w+)\s*:\s*(' + _LEAKY_CONTEXT_TYPE_ALT + r')\??\b'
)

BINDING_FIELD_RE = re.compile(r'\bvar\s+(_\w*[Bb]inding)\s*:\s*[\w.]+\?')
ON_DESTROY_VIEW_RE = re.compile(r'\bfun\s+onDestroyView\s*\([^)]*\)\s*\{')

INNER_HANDLER_RE = re.compile(r'\binner\s+class\s+(\w+)\s*(?:\([^)]*\))?\s*:\s*Handler\b')

OBSERVE_FOREVER_RE = re.compile(r'\.observeForever\s*[({]')
REMOVE_OBSERVER_RE = re.compile(r'\.removeObserver\s*\(')


def run_object(obj):
    """object/companion object com propriedade tipada Context/Activity/View — candidato
    a vazamento estático (o valor sobrevive à instância que originou o Context, já que o
    campo é essencialmente um `static` do ponto de vista da JVM)."""
    findings = []
    for m in STATIC_FIELD_RE.finditer(obj.body):
        prop_name, type_name = m.group(1), m.group(2)
        findings.append(make_finding(
            obj, 'static-field-leaks-context',
            f"'{obj.name}.{prop_name}' é uma propriedade de {'companion object' if obj.kind == 'companion_object' else 'object'} "
            f"tipada '{type_name}' — se o valor atribuído a ela for de fato uma Activity/View/"
            f"Context de Activity (não o applicationContext), a instância nunca é coletada pelo "
            f"GC enquanto o object existir (o que, para um object/companion object Kotlin, é a "
            f"vida inteira do processo). Confirme a origem do valor antes de corrigir: se for "
            f"sempre `.applicationContext`, este finding é um falso positivo (o scanner não "
            f"resolve o valor real, só o tipo declarado) — senão, prefira um WeakReference ou, "
            f"melhor, não reter a referência.",
            offset=m.start(1),
        ))
    return findings


def run_class(cls):
    findings = []

    if cls.kind == 'fragment':
        binding_m = BINDING_FIELD_RE.search(cls.body)
        if binding_m:
            field_name = binding_m.group(1)
            destroy_m = ON_DESTROY_VIEW_RE.search(cls.body)
            nulled = False
            if destroy_m:
                open_brace = destroy_m.end() - 1
                close_brace = find_matching(cls.body, open_brace, '{', '}')
                if close_brace != -1:
                    method_body = cls.body[open_brace + 1:close_brace]
                    if re.search(rf'\b{re.escape(field_name)}\s*=\s*null\b', method_body):
                        nulled = True
            if not nulled:
                reason = (
                    "sem override de onDestroyView() neste arquivo" if not destroy_m else
                    f"onDestroyView() não atribui '{field_name} = null'"
                )
                findings.append(make_finding(
                    cls, 'fragment-view-binding-not-cleared',
                    f"Fragment '{cls.name}' declara '{field_name}' (ViewBinding nullable) mas "
                    f"{reason} — a view hierarchy do Fragment é destruída em onDestroyView() "
                    f"enquanto a instância do Fragment pode sobreviver mais tempo (voltando de "
                    f"um back stack, por exemplo); sem nulling explícito, o binding retém a view "
                    f"antiga viva além do necessário. Fix oficial: `_{field_name.lstrip('_')} = "
                    f"null` (ou o nome exato do campo) dentro de onDestroyView().",
                    offset=binding_m.start(1),
                ))

        for m in INNER_HANDLER_RE.finditer(cls.body):
            findings.append(make_finding(
                cls, 'handler-inner-class-leak',
                f"'{m.group(1)}' é uma inner class (não estática) estendendo Handler dentro "
                f"de '{cls.name}' — em Kotlin, `inner class` retém uma referência implícita à "
                f"instância externa (o Fragment/Activity); combinado com mensagens pendentes na "
                f"fila do Handler, isso pode reter o Fragment/Activity vivo além do seu ciclo de "
                f"vida. Prefira uma classe top-level ou `object`/classe aninhada não-inner "
                f"recebendo uma WeakReference explícita à Activity/Fragment, se precisar dela.",
                offset=m.start(),
            ))

    if cls.kind == 'activity':
        for m in INNER_HANDLER_RE.finditer(cls.body):
            findings.append(make_finding(
                cls, 'handler-inner-class-leak',
                f"'{m.group(1)}' é uma inner class (não estática) estendendo Handler dentro "
                f"de '{cls.name}' — mesma observação de vazamento que em Fragments (ver "
                f"references/context-and-lifecycle-leaks.md): a inner class retém a Activity "
                f"externa implicitamente.",
                offset=m.start(),
            ))

    return findings


def run_file(text, file_path, offsets):
    if not (file_path.endswith('.kt') or file_path.endswith('.java')):
        return []
    findings = []

    observe_matches = list(OBSERVE_FOREVER_RE.finditer(text))
    if observe_matches and not REMOVE_OBSERVER_RE.search(text):
        for m in observe_matches:
            findings.append(make_file_finding(
                file_path, offsets, m.start(), 'livedata-observeforever-not-removed',
                "'.observeForever(...)' não está pareado com nenhum '.removeObserver(...)' "
                "neste arquivo — ao contrário de '.observe(this, ...)' (lifecycle-aware, "
                "remove o observer automaticamente), observeForever mantém o observer vivo "
                "indefinidamente até removeObserver ser chamado manualmente, o que costuma "
                "vazar o observer (e o que ele referencia) quando o componente que o registrou "
                "é destruído.",
            ))

    return findings
