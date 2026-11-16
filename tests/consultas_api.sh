#!/usr/bin/env bash
# Pruebas de usuario final de la API.
# Muestra el estado, el precio actual y la predicción de súper, regular y diésel.
#
# Uso:
#   bash tests/consultas_api.sh                     # contra http://localhost:8001
#   bash tests/consultas_api.sh http://<ip>:8001    # contra el Droplet
#
# Termina con error si algún endpoint no responde 200.

set -u
BASE="${1:-http://localhost:8001}"
FALLAS=0

consultar() {
  local titulo="$1" ruta="$2"
  echo
  echo "== ${titulo}"
  echo "GET ${BASE}${ruta}"
  local respuesta codigo
  respuesta=$(curl -sS -w '\n%{http_code}' "${BASE}${ruta}")
  codigo=$(echo "$respuesta" | tail -n 1)
  echo "$respuesta" | sed '$d'
  echo "HTTP ${codigo}"
  if [ "$codigo" != "200" ]; then
    FALLAS=$((FALLAS + 1))
  fi
}

consultar "Estado del servicio" "/health"
consultar "Precio actual de los tres combustibles" "/precios/actual"
for combustible in super regular diesel; do
  consultar "Predicción de la semana siguiente: ${combustible}" "/prediccion?combustible=${combustible}"
done
consultar "Histórico semanal del diésel, precio oficial" "/precios?combustible=diesel&desde=2026-10-01&hasta=2026-11-30&fuente=mem&limit=5"
consultar "Histórico semanal de la súper, precios de las fotos" "/precios?combustible=super&fuente=fotos&limit=3"
consultar "Métricas del modelo y de la línea base" "/modelo/metricas"
consultar "Documentación" "/openapi.json" > /dev/null

echo
if [ "$FALLAS" -eq 0 ]; then
  echo "Todas las consultas respondieron 200"
else
  echo "Consultas con error: ${FALLAS}"
  exit 1
fi
