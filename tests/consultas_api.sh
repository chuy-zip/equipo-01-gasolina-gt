#!/usr/bin/env bash
# End-user queries: current price and prediction for super, regular and diesel.
# Usage: tests/consultas_api.sh [base_url]
BASE_URL="${1:-http://157.230.171.204:8001}"

curl -fsS "$BASE_URL/health"; echo
curl -fsS "$BASE_URL/precios/actual"; echo
for fuel in super regular diesel; do
  echo "== $fuel"
  curl -fsS "$BASE_URL/precios?combustible=$fuel&limit=3"; echo
  curl -fsS "$BASE_URL/prediccion?combustible=$fuel"; echo
done
curl -fsS "$BASE_URL/modelo/metricas"; echo
