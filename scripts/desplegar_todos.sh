#!/usr/bin/env bash
# Despliega la versión actual del código a TODAS las instancias de clientes
# listadas en scripts/clientes.txt (una app Fly.io por línea).
#
# Uso: ./scripts/desplegar_todos.sh

set -uo pipefail

cd "$(dirname "$0")/.."
CLIENTES_FILE="scripts/clientes.txt"

if [ ! -f "$CLIENTES_FILE" ]; then
    echo "No existe $CLIENTES_FILE"
    exit 1
fi

FALLOS=()
while IFS= read -r app || [ -n "$app" ]; do
    [ -z "$app" ] && continue
    case "$app" in \#*) continue ;; esac
    echo ""
    echo "==================== $app ===================="
    if fly deploy --app "$app" --ha=false; then
        echo "OK: $app"
    else
        echo "FALLO: $app"
        FALLOS+=("$app")
    fi
done < "$CLIENTES_FILE"

echo ""
if [ ${#FALLOS[@]} -eq 0 ]; then
    echo "Todos los despliegues OK."
else
    echo "Fallaron: ${FALLOS[*]}"
    exit 1
fi
