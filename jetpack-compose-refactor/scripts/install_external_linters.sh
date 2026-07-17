#!/usr/bin/env bash
# Baixa, para um cache local do usuário, os binários/jars standalone de ktlint e
# detekt-cli, mais os jars do ruleset compose-rules (io.nlopez.compose.rules) para
# cada um — SEM tocar em nada do projeto-alvo. Isso é o que try_external_linters.sh
# usa para corroboração opcional (ver scripts/README.md).
#
# Segurança: baixar e depois executar um binário de terceiros da internet é uma ação
# com risco real, então este script continua nunca baixando nada por conta própria —
# sem a flag --yes ele só imprime o que faria (dry-run). O workflow em ../SKILL.md
# roda este script com --yes automaticamente (sem pedir confirmação ao usuário) como
# parte obrigatória do passo 3; quem invocar este script manualmente decide por conta
# própria se quer passar --yes.
#
# Uso:
#   ./install_external_linters.sh                    # dry-run: só mostra o plano
#   ./install_external_linters.sh --yes               # instala ktlint + detekt
#   ./install_external_linters.sh --only ktlint --yes
#   ./install_external_linters.sh --only detekt --yes
#
# As versões abaixo foram confirmadas contra os releases/coordenadas reais no
# momento em que este script foi escrito (testado ponta a ponta, incluindo rodar
# ktlint/detekt de verdade contra arquivos .kt de exemplo). Se algum download
# começar a falhar (404), provavelmente saiu uma versão nova — atualize as
# variáveis *_VERSION conferindo:
#   ktlint:        https://github.com/ktlint/ktlint/releases/latest
#   detekt-cli:    https://github.com/detekt/detekt/releases/latest
#   compose-rules: https://search.maven.org/search?q=g:io.nlopez.compose.rules
#
# Nota de arquitetura importante (descoberta ao testar contra o ruleset real):
# io.nlopez.compose.rules:ktlint e io.nlopez.compose.rules:detekt dependem de um
# terceiro jar, io.nlopez.compose.rules:common, para as classes compartilhadas
# (ComposeKtVisitor etc.). O detekt carrega múltiplos jars de --plugins num
# classloader compartilhado, então basta passar os dois jars separados por
# vírgula. O ktlint, por outro lado, isola cada jar de -R num classloader próprio
# — passar dois -R não funciona (cada jar não enxerga classes do outro). Por isso
# este script MESCLA o ruleset do ktlint com o common num único jar antes de
# deixá-lo pronto para uso; para detekt, os dois jars ficam separados mesmo.
set -euo pipefail

KTLINT_VERSION="1.8.0"
DETEKT_VERSION="1.23.8"
COMPOSE_RULES_VERSION="0.4.22"

CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/jetpack-compose-refactor/tools"
BIN_DIR="$CACHE_DIR/bin"
JARS_DIR="$CACHE_DIR/jars"

ONLY="all"
DO_DOWNLOAD=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --yes) DO_DOWNLOAD=1; shift ;;
    --only) ONLY="${2:-}"; shift 2 ;;
    -h|--help)
      sed -n '1,33p' "$0"
      exit 0
      ;;
    *) echo "Argumento desconhecido: $1" >&2; exit 2 ;;
  esac
done

want_ktlint=0
want_detekt=0
case "$ONLY" in
  all) want_ktlint=1; want_detekt=1 ;;
  ktlint) want_ktlint=1 ;;
  detekt) want_detekt=1 ;;
  *) echo "Valor inválido para --only: '$ONLY' (use ktlint, detekt ou all)" >&2; exit 2 ;;
esac

KTLINT_URL="https://github.com/ktlint/ktlint/releases/download/${KTLINT_VERSION}/ktlint"
KTLINT_RULESET_JAR="compose-rules-ktlint-${COMPOSE_RULES_VERSION}.jar"
KTLINT_RULESET_URL="https://repo1.maven.org/maven2/io/nlopez/compose/rules/ktlint/${COMPOSE_RULES_VERSION}/ktlint-${COMPOSE_RULES_VERSION}.jar"
KTLINT_MERGED_JAR="compose-rules-ktlint-merged-${COMPOSE_RULES_VERSION}.jar"

DETEKT_CLI_URL="https://github.com/detekt/detekt/releases/download/v${DETEKT_VERSION}/detekt-cli-${DETEKT_VERSION}-all.jar"
DETEKT_RULESET_JAR="compose-rules-detekt-${COMPOSE_RULES_VERSION}.jar"
DETEKT_RULESET_URL="https://repo1.maven.org/maven2/io/nlopez/compose/rules/detekt/${COMPOSE_RULES_VERSION}/detekt-${COMPOSE_RULES_VERSION}.jar"

COMMON_JAR="compose-rules-common-${COMPOSE_RULES_VERSION}.jar"
COMMON_URL="https://repo1.maven.org/maven2/io/nlopez/compose/rules/common/${COMPOSE_RULES_VERSION}/common-${COMPOSE_RULES_VERSION}.jar"

echo "Cache de instalação: $CACHE_DIR"
echo "Itens no plano:"
if [[ "$want_ktlint" -eq 1 ]]; then
  echo "  - ktlint executável (v${KTLINT_VERSION}) -> $BIN_DIR/ktlint"
  echo "      <- $KTLINT_URL"
  echo "  - ruleset compose-rules p/ ktlint + dependência common (v${COMPOSE_RULES_VERSION}), mesclados -> $JARS_DIR/$KTLINT_MERGED_JAR"
  echo "      <- $KTLINT_RULESET_URL"
  echo "      <- $COMMON_URL"
fi
if [[ "$want_detekt" -eq 1 ]]; then
  echo "  - detekt-cli fat jar (v${DETEKT_VERSION}) -> $BIN_DIR/detekt-cli.jar (requer 'java -jar' para rodar)"
  echo "      <- $DETEKT_CLI_URL"
  echo "  - ruleset compose-rules p/ detekt + dependência common (v${COMPOSE_RULES_VERSION}) -> $JARS_DIR/$DETEKT_RULESET_JAR, $JARS_DIR/$COMMON_JAR"
  echo "      <- $DETEKT_RULESET_URL"
  echo "      <- $COMMON_URL"
fi

if [[ "$DO_DOWNLOAD" -eq 0 ]]; then
  echo
  echo "Dry-run — nada foi baixado. Rode de novo com --yes para instalar de fato"
  echo "(só faça isso após confirmar explicitamente com quem pediu a refatoração)."
  exit 0
fi

mkdir -p "$BIN_DIR" "$JARS_DIR"

download() {
  local url="$1" dest="$2"
  if [[ -f "$dest" ]]; then
    echo "já existe, pulando: $dest"
    return 0
  fi
  echo "baixando $url"
  echo "     -> $dest"
  curl -fL --progress-bar -o "${dest}.part" "$url"
  mv "${dest}.part" "$dest"
}

if [[ "$want_ktlint" -eq 1 || "$want_detekt" -eq 1 ]]; then
  download "$COMMON_URL" "$JARS_DIR/$COMMON_JAR"
fi

if [[ "$want_ktlint" -eq 1 ]]; then
  download "$KTLINT_URL" "$BIN_DIR/ktlint"
  chmod +x "$BIN_DIR/ktlint"
  download "$KTLINT_RULESET_URL" "$JARS_DIR/$KTLINT_RULESET_JAR"

  if [[ -f "$JARS_DIR/$KTLINT_MERGED_JAR" ]]; then
    echo "já existe, pulando: $JARS_DIR/$KTLINT_MERGED_JAR"
  else
    echo "mesclando $KTLINT_RULESET_JAR + $COMMON_JAR -> $KTLINT_MERGED_JAR (necessário: ktlint isola cada -R num classloader próprio)"
    python3 - "$JARS_DIR/$KTLINT_RULESET_JAR" "$JARS_DIR/$COMMON_JAR" "$JARS_DIR/$KTLINT_MERGED_JAR" <<'PYEOF'
import sys
import zipfile

ruleset_jar, common_jar, out_jar = sys.argv[1:4]
seen = set()
with zipfile.ZipFile(out_jar, "w", zipfile.ZIP_DEFLATED) as out:
    for src in (ruleset_jar, common_jar):
        with zipfile.ZipFile(src) as z:
            for item in z.infolist():
                if item.filename in seen or item.filename.endswith("/"):
                    continue
                seen.add(item.filename)
                out.writestr(item, z.read(item.filename))
PYEOF
  fi
fi

if [[ "$want_detekt" -eq 1 ]]; then
  download "$DETEKT_CLI_URL" "$BIN_DIR/detekt-cli.jar"
  download "$DETEKT_RULESET_URL" "$JARS_DIR/$DETEKT_RULESET_JAR"
fi

echo
echo "Instalação concluída em $CACHE_DIR — nada fora desse diretório foi modificado"
echo "(o projeto-alvo sendo refatorado não foi tocado)."
echo "Rode ./try_external_linters.sh <alvo> para usar as ferramentas recém-instaladas."
