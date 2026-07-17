#!/usr/bin/env bash
# Corroboração opcional e best-effort: se ktlint e/ou detekt estiverem disponíveis
# de forma standalone no ambiente (não como parte da configuração de build do
# projeto-alvo), roda-os diretamente contra o caminho informado só para dar uma
# segunda opinião real ao lado do scan_compose_components.py.
#
# Procura as ferramentas em três lugares, nesta ordem: PATH, cache local deste
# skill (~/.cache/jetpack-compose-refactor/tools/ — populado por
# install_external_linters.sh), e ~/.m2 ou ~/.gradle/caches para os jars de
# ruleset compose-rules. Este script NUNCA depende do build.gradle*/version
# catalog do projeto-alvo, NUNCA baixa nada sozinho (isso é
# install_external_linters.sh, que exige --yes explícito), e NUNCA falha o fluxo
# principal do skill: se nenhuma ferramenta for encontrada, ele sugere o comando
# de instalação e sai com status 0.
#
# Uso: ./try_external_linters.sh <arquivo-ou-diretório>
#
# Saída: bruta, direto do stdout de cada ferramenta — este script não tenta
# fundir esses achados com o JSON do scan_compose_components.py (ver
# scripts/README.md para o porquê dessa escolha).
set -uo pipefail

TARGET="${1:-}"
if [[ -z "$TARGET" ]]; then
  echo "Uso: $0 <arquivo-ou-diretório>" >&2
  exit 2
fi

CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/jetpack-compose-refactor/tools"
CACHE_BIN="$CACHE_DIR/bin"
CACHE_JARS="$CACHE_DIR/jars"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

find_ruleset_jar() {
  # $1: padrão de nome (ex.: '*compose-rules*ktlint*.jar')
  find "$CACHE_JARS" "${HOME}/.m2" "${HOME}/.gradle/caches" -iname "$1" 2>/dev/null | head -n1
}

found_any=0

# --- ktlint ---------------------------------------------------------------
KTLINT_BIN=""
if command -v ktlint >/dev/null 2>&1; then
  KTLINT_BIN="ktlint"
elif [[ -x "$CACHE_BIN/ktlint" ]]; then
  KTLINT_BIN="$CACHE_BIN/ktlint"
fi

if [[ -n "$KTLINT_BIN" ]]; then
  found_any=1
  echo "== ktlint (standalone: $KTLINT_BIN) =="
  # Precisa ser o jar MESCLADO (ruleset + módulo common) — o ktlint isola cada
  # -R num classloader próprio, então passar os dois jars separados não resolve
  # a dependência cruzada (ver nota em install_external_linters.sh).
  RULESET_JAR="$(find_ruleset_jar '*compose-rules-ktlint-merged*.jar')"
  # ktlint interpreta argumentos posicionais como padrões de glob estilo
  # .gitignore relativos ao diretório de trabalho — um caminho absoluto de
  # DIRETÓRIO não funciona (cai no comportamento default e tenta varrer a
  # partir de "/", batendo em coisas como /lost+found). Um caminho absoluto de
  # ARQUIVO funciona bem. Então: para arquivo, passa direto; para diretório,
  # entra nele e roda sem padrão (default = tudo recursivamente a partir do cwd).
  if [[ -f "$TARGET" ]]; then
    KTLINT_TARGET_ARGS=("$TARGET")
    KTLINT_RUN_DIR="$(pwd)"
  else
    KTLINT_TARGET_ARGS=()
    KTLINT_RUN_DIR="$TARGET"
  fi
  if [[ -n "$RULESET_JAR" ]]; then
    echo "usando ruleset de compose-rules: $RULESET_JAR"
    ( cd "$KTLINT_RUN_DIR" && "$KTLINT_BIN" -R "$RULESET_JAR" "${KTLINT_TARGET_ARGS[@]}" ) 2>&1 || true
  else
    echo "aviso: jar do ktlint compose-rules não encontrado — rodando ktlint só com as regras built-in."
    echo "       para instalar (com confirmação explícita): $SCRIPT_DIR/install_external_linters.sh --only ktlint --yes"
    ( cd "$KTLINT_RUN_DIR" && "$KTLINT_BIN" "${KTLINT_TARGET_ARGS[@]}" ) 2>&1 || true
  fi
else
  echo "ktlint não encontrado (nem no PATH, nem no cache local) — pulando corroboração via ktlint."
  echo "  para habilitar: $SCRIPT_DIR/install_external_linters.sh --only ktlint --yes"
  echo "  (baixa um binário da internet para $CACHE_BIN — o workflow do skill roda isso automaticamente)"
fi

echo

# --- detekt -----------------------------------------------------------------
DETEKT_CMD=()
if command -v detekt >/dev/null 2>&1; then
  DETEKT_CMD=(detekt)
elif command -v detekt-cli >/dev/null 2>&1; then
  DETEKT_CMD=(detekt-cli)
elif [[ -f "$CACHE_BIN/detekt-cli.jar" ]] && command -v java >/dev/null 2>&1; then
  DETEKT_CMD=(java -jar "$CACHE_BIN/detekt-cli.jar")
fi

if [[ "${#DETEKT_CMD[@]}" -gt 0 ]]; then
  found_any=1
  echo "== detekt (standalone: ${DETEKT_CMD[*]}) =="
  # detekt carrega múltiplos --plugins num classloader compartilhado, então (ao
  # contrário do ktlint) basta passar o ruleset e sua dependência common
  # separados por vírgula — não precisa de jar mesclado.
  PLUGIN_JAR="$(find_ruleset_jar '*compose-rules-detekt-[0-9]*.jar')"
  COMMON_JAR="$(find_ruleset_jar '*compose-rules-common*.jar')"
  if [[ -n "$PLUGIN_JAR" && -n "$COMMON_JAR" ]]; then
    echo "usando plugins de compose-rules: $PLUGIN_JAR, $COMMON_JAR"
    "${DETEKT_CMD[@]}" --input "$TARGET" --plugins "$PLUGIN_JAR,$COMMON_JAR" 2>&1 || true
  else
    echo "aviso: jar do detekt compose-rules não encontrado — rodando detekt só com as regras built-in."
    echo "       para instalar (com confirmação explícita): $SCRIPT_DIR/install_external_linters.sh --only detekt --yes"
    "${DETEKT_CMD[@]}" --input "$TARGET" 2>&1 || true
  fi
else
  echo "detekt/detekt-cli não encontrado (nem no PATH, nem no cache local) — pulando corroboração via detekt."
  echo "  para habilitar: $SCRIPT_DIR/install_external_linters.sh --only detekt --yes"
  echo "  (pergunte antes de rodar — baixa um jar da internet para $CACHE_BIN; requer 'java' instalado)"
fi

if [[ "$found_any" -eq 0 ]]; then
  echo
  echo "Nenhuma ferramenta externa (ktlint/detekt) disponível neste ambiente — sem corroboração externa."
  echo "O scan_compose_components.py continua sendo a fonte primária de findings, isso é sempre opcional."
fi

exit 0
