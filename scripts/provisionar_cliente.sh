#!/usr/bin/env bash
# Aprovisiona una nueva instancia de GranjaManager para un cliente (ganadería) nuevo:
# crea la app en Fly.io, su volumen persistente, los secrets básicos y despliega.
#
# Uso:
#   ./scripts/provisionar_cliente.sh <slug-app> "<Nombre de la explotación>" [--demo] [--modulos=lista,separada,por,comas]
#
# Módulos disponibles (opcionales, todos activos si no se indica --modulos):
#   queseria, analisis_leche, maquinaria, alimentacion, economia, cuaderno
#   (Animales/Reproducción/Sanidad/Lotes/Tareas son el núcleo, siempre incluido)
#
# Ejemplo cliente normal (todos los módulos):
#   ./scripts/provisionar_cliente.sh granja-perez "Ganadería Pérez"
#
# Ejemplo cliente solo de carne (sin quesería/análisis de leche):
#   ./scripts/provisionar_cliente.sh granja-lopez "Ganadería López" --modulos=maquinaria,alimentacion,economia,cuaderno
#
# Ejemplo instancia de demostración (datos de ejemplo, se reinician cada noche):
#   ./scripts/provisionar_cliente.sh granja-demo "Explotación Demo" --demo
#
# El slug debe ser único en Fly.io (minúsculas, guiones, sin espacios) — será
# también el subdominio: https://<slug>.fly.dev

set -euo pipefail

APP_SLUG="${1:?Uso: provisionar_cliente.sh <slug-app> \"<Nombre de la explotación>\" [--demo] [--modulos=...]}"
NOMBRE_EXPLOTACION="${2:?Uso: provisionar_cliente.sh <slug-app> \"<Nombre de la explotación>\" [--demo] [--modulos=...]}"
shift 2

ES_DEMO=""
MODULOS=""
for arg in "$@"; do
    case "$arg" in
        --demo) ES_DEMO="--demo" ;;
        --modulos=*) MODULOS="${arg#--modulos=}" ;;
        *) echo "Argumento no reconocido: $arg" >&2; exit 1 ;;
    esac
done

ORG="personal"
REGION="cdg"

cd "$(dirname "$0")/.."

echo "==> Creando app Fly.io: $APP_SLUG"
fly apps create "$APP_SLUG" --org "$ORG"

echo "==> Creando volumen persistente (1GB, región $REGION)"
fly volumes create granja_data --app "$APP_SLUG" --region "$REGION" --size 1 --yes

echo "==> Generando SECRET_KEY aleatoria"
SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")

echo "==> Configurando secrets básicos"
fly secrets set \
  SECRET_KEY="$SECRET_KEY" \
  COOKIE_SECURE=true \
  UPLOADS_DIR=/data/uploads \
  EXPLOTACION_NOMBRE="$NOMBRE_EXPLOTACION" \
  BASE_URL="https://${APP_SLUG}.fly.dev" \
  --app "$APP_SLUG"

if [ "$ES_DEMO" = "--demo" ]; then
    echo "==> Activando DEMO_MODE (datos de ejemplo, se reinician cada noche)"
    fly secrets set DEMO_MODE=true --app "$APP_SLUG"
fi

if [ -n "$MODULOS" ]; then
    echo "==> Activando solo estos módulos: $MODULOS"
    fly secrets set MODULOS="$MODULOS" --app "$APP_SLUG"
fi

echo "==> Desplegando"
fly deploy --app "$APP_SLUG" --ha=false

if [ "$ES_DEMO" = "--demo" ]; then
    echo "==> Sembrando datos de ejemplo"
    fly ssh console --app "$APP_SLUG" -C "python -m services.demo_seed"
fi

CLIENTES_FILE="$(dirname "$0")/clientes.txt"
if ! grep -qx "$APP_SLUG" "$CLIENTES_FILE" 2>/dev/null; then
    echo "$APP_SLUG" >> "$CLIENTES_FILE"
    echo "==> Añadida $APP_SLUG a scripts/clientes.txt (para futuros despliegues masivos)"
fi

if [ "$ES_DEMO" = "--demo" ]; then
    cat <<EOF

Demo lista: https://${APP_SLUG}.fly.dev
Usuario: demo / Contraseña: demo1234
Se reinicia sola cada noche a las 04:00 (hora España).
EOF
else
    cat <<EOF

Listo: https://${APP_SLUG}.fly.dev

El primer usuario que entre podrá crear la cuenta de administrador
(se le redirige automáticamente a /auth/setup al no haber ningún usuario todavía).

Pendiente manual, cuando el cliente lo facilite (opcional):
  fly secrets set TELEGRAM_CHAT_ID=xxxxx --app $APP_SLUG
  (el bot de Telegram ya es el mismo para todos los clientes; solo hace
  falta el chat_id de cada uno para las alertas — ver RUNBOOK.md)
EOF
fi

if [ -n "$MODULOS" ]; then
    echo "Módulos activos: $MODULOS (además del núcleo: animales, reproducción, sanidad, lotes, tareas)"
else
    echo "Módulos activos: todos"
fi
