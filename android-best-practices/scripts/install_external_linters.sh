#!/usr/bin/env bash
# Baixa, para um cache local do usuário, os binários/jars standalone de ktlint e
# detekt-cli — SEM tocar em nada do projeto-alvo. Isso é o que try_external_linters.sh
# usa para corroboração opcional (ver scripts/README.md).
#
# Ao contrário do skill irmão jetpack-compose-refactor (que precisa baixar também os
# jars de um ruleset de terceiros, io.nlopez.compose.rules, e mesclá-los manualmente),
# este script não precisa de nenhum plugin extra: as checagens deste skill que têm
# correspondência real em detekt (PrintStackTrace, UnsafeCallOnNullableType,
# EmptyCatchBlock, TooGenericExceptionCaught, SwallowedException, GlobalCoroutineUsage)
# vivem nos rulesets padrão do detekt (potential-bugs/empty-blocks/exceptions/
# coroutines), habilitados por padrão em qualquer execução do detekt-cli sem
# configuração adicional.
#
# Segurança: baixar e depois executar um binário de terceiros da internet é uma ação
# com risco real, então este script nunca baixa nada por conta própria — sem a flag
# --yes ele só imprime o que faria (dry-run). O workflow em ../SKILL.md roda este
# script com --yes automaticamente (sem pedir confirmação ao usuário) como parte
# obrigatória do passo 3; quem invocar este script manualmente decide por conta própria
# se quer passar --yes.
#
# Uso:
#   ./install_external_linters.sh                    # dry-run: só mostra o plano
#   ./install_external_linters.sh --yes               # instala ktlint + detekt
#   ./install_external_linters.sh --only ktlint --yes
#   ./install_external_linters.sh --only detekt --yes
#
# As versões abaixo são as mesmas já validadas ponta a ponta pelo skill irmão
# jetpack-compose-refactor (baixadas e executadas de verdade contra arquivos .kt de
# exemplo naquele skill). Se algum download começar a falhar (404), provavelmente saiu
# uma versão nova — atualize as variáveis *_VERSION conferindo:
#   ktlint:     https://github.com/ktlint/ktlint/releases/latest
#   detekt-cli: https://github.com/detekt/detekt/releases/latest
set -euo pipefail

KTLINT_VERSION="1.8.0"
DETEKT_VERSION="1.23.8"

CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/android-best-practices/tools"
BIN_DIR="$CACHE_DIR/bin"

ONLY="all"
DO_DOWNLOAD=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --yes) DO_DOWNLOAD=1; shift ;;
    --only) ONLY="${2:-}"; shift 2 ;;
    -h|--help)
      sed -n '1,30p' "$0"
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
DETEKT_CLI_URL="https://github.com/detekt/detekt/releases/download/v${DETEKT_VERSION}/detekt-cli-${DETEKT_VERSION}-all.jar"

echo "Cache de instalação: $CACHE_DIR"
echo "Itens no plano:"
if [[ "$want_ktlint" -eq 1 ]]; then
  echo "  - ktlint executável (v${KTLINT_VERSION}, regras built-in, sem plugin) -> $BIN_DIR/ktlint"
  echo "      <- $KTLINT_URL"
fi
if [[ "$want_detekt" -eq 1 ]]; then
  echo "  - detekt-cli fat jar (v${DETEKT_VERSION}, rulesets padrão built-in) -> $BIN_DIR/detekt-cli.jar (requer 'java -jar' para rodar)"
  echo "      <- $DETEKT_CLI_URL"
fi

if [[ "$DO_DOWNLOAD" -eq 0 ]]; then
  echo
  echo "Dry-run — nada foi baixado. Rode de novo com --yes para instalar de fato"
  echo "(só faça isso após confirmar explicitamente com quem pediu a análise/refatoração)."
  exit 0
fi

mkdir -p "$BIN_DIR"

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

if [[ "$want_ktlint" -eq 1 ]]; then
  download "$KTLINT_URL" "$BIN_DIR/ktlint"
  chmod +x "$BIN_DIR/ktlint"
fi

if [[ "$want_detekt" -eq 1 ]]; then
  download "$DETEKT_CLI_URL" "$BIN_DIR/detekt-cli.jar"
fi

echo
echo "Instalação concluída em $CACHE_DIR — nada fora desse diretório foi modificado"
echo "(o projeto-alvo sendo analisado não foi tocado)."
echo "Rode ./try_external_linters.sh <alvo> para usar as ferramentas recém-instaladas."
