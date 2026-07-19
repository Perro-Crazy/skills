#!/usr/bin/env bash
# Corroboração opcional e best-effort: se ktlint e/ou detekt estiverem disponíveis de
# forma standalone no ambiente (não como parte da configuração de build do
# projeto-alvo), roda-os diretamente contra o caminho informado só para dar uma segunda
# opinião real ao lado do scan_android_best_practices.py — usando só as regras built-in
# de cada ferramenta (nenhum plugin/ruleset de terceiros é necessário aqui, diferente do
# skill irmão jetpack-compose-refactor).
#
# Procura as ferramentas em dois lugares, nesta ordem: PATH e cache local deste skill
# (~/.cache/android-best-practices/tools/ — populado por install_external_linters.sh).
# Este script NUNCA depende do build.gradle*/version catalog do projeto-alvo, NUNCA
# baixa nada sozinho (isso é install_external_linters.sh, que exige --yes explícito), e
# NUNCA falha o fluxo principal do skill: se nenhuma ferramenta for encontrada, ele
# sugere o comando de instalação e sai com status 0.
#
# Uso: ./try_external_linters.sh <arquivo-ou-diretório>
#
# Saída: bruta, direto do stdout de cada ferramenta — este script não tenta fundir esses
# achados com o JSON do scan_android_best_practices.py (mesma decisão de design do skill
# irmão, ver scripts/README.md para o porquê).
#
# Nota importante: nem ktlint nem detekt reproduzem as checagens Android-específicas
# deste skill (manifest, Context leaks, arquitetura) — eles só corroboram o subconjunto
# que tem equivalente genérico Kotlin (ex.: PrintStackTrace, UnsafeCallOnNullableType,
# EmptyCatchBlock, TooGenericExceptionCaught, SwallowedException no detekt). Android
# Lint em si (que cobriria os checkIds de manifest/Context com mais fidelidade) não tem
# um instalador standalone leve — requer Android SDK cmdline-tools completo — então
# deliberadamente não faz parte deste par de scripts; ver references/security-and-manifest.md.
set -uo pipefail

TARGET="${1:-}"
if [[ -z "$TARGET" ]]; then
  echo "Uso: $0 <arquivo-ou-diretório>" >&2
  exit 2
fi

CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/android-best-practices/tools"
CACHE_BIN="$CACHE_DIR/bin"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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
  echo "== ktlint (standalone: $KTLINT_BIN, regras built-in) =="
  # ktlint interpreta argumentos posicionais como padrões de glob estilo .gitignore
  # relativos ao diretório de trabalho — um caminho absoluto de DIRETÓRIO não funciona
  # (cai no comportamento default e tenta varrer a partir de "/"). Um caminho absoluto
  # de ARQUIVO funciona bem. Então: para arquivo, passa direto; para diretório, entra
  # nele e roda sem padrão (default = tudo recursivamente a partir do cwd).
  if [[ -f "$TARGET" ]]; then
    ( "$KTLINT_BIN" "$TARGET" ) 2>&1 || true
  else
    ( cd "$TARGET" && "$KTLINT_BIN" ) 2>&1 || true
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
  echo "== detekt (standalone: ${DETEKT_CMD[*]}, rulesets padrão built-in) =="
  "${DETEKT_CMD[@]}" --input "$TARGET" 2>&1 || true
else
  echo "detekt/detekt-cli não encontrado (nem no PATH, nem no cache local) — pulando corroboração via detekt."
  echo "  para habilitar: $SCRIPT_DIR/install_external_linters.sh --only detekt --yes"
  echo "  (baixa um jar da internet para $CACHE_BIN; requer 'java' instalado)"
fi

if [[ "$found_any" -eq 0 ]]; then
  echo
  echo "Nenhuma ferramenta externa (ktlint/detekt) disponível neste ambiente — sem corroboração externa."
  echo "O scan_android_best_practices.py continua sendo a fonte primária de findings, isso é sempre opcional."
fi

exit 0
