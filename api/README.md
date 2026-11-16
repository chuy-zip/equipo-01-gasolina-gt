# API del precio de la gasolina

FastAPI sobre la copia de la capa oro y el modelo `champion`. La imagen de Docker lleva todo adentro:
no se conecta a Databricks ni a S3 y no necesita credenciales.

## Endpoints

| Endpoint | Qué devuelve |
|---|---|
| `GET /health` | Estado, versión del modelo y fecha de la copia de oro |
| `GET /precios/actual?combustible=` | Último precio de referencia del MEM y límite de precio normal |
| `GET /precios?combustible=&desde=&hasta=&fuente=&limit=&offset=` | Histórico semanal. `fuente` es `mem` o `fotos`. `limit` va de 1 a 1000 |
| `GET /prediccion?combustible=` | Predicción de la semana siguiente con el modelo empaquetado. `coincide_con_databricks` la compara con `gold.predicciones` |
| `GET /modelo/metricas` | Balanced accuracy del modelo y de la línea base del enunciado |
| `GET /docs` | Documentación interactiva |

## Por qué Docker

El enunciado permite Docker, conda, uv o venv. Se eligió Docker porque:

1. La imagen fija la versión de Python y de scikit-learn con que se entrenó el modelo. Con otra versión el modelo puede no cargar.
2. La imagen lleva el modelo y los datos. En el Droplet no hay que instalar nada de Python ni copiar archivos sueltos.
3. `restart: unless-stopped` deja la API corriendo aunque se cierre la sesión ssh o se reinicie Docker.

## Probar en local

Desde la raíz del repo, con la CLI de Databricks autenticada:

```bash
pip install -e ".[exportar]"
python scripts/exportar_para_api.py
cd api
docker build -t equipo-01-gasolina-api:latest .
PUERTO=8001 docker compose up -d
bash ../tests/consultas_api.sh http://localhost:8001
```

## Desplegar en el Droplet

La imagen se construye en local y se sube por ssh. En el Droplet solo se usa Docker, en `/home/equipo-01/api`.

```bash
docker save equipo-01-gasolina-api:latest | gzip | ssh -i <llave> equipo-01@<ip> "gunzip | docker load"
scp -i <llave> api/docker-compose.yml equipo-01@<ip>:/home/equipo-01/api/
ssh -i <llave> equipo-01@<ip> "cd /home/equipo-01/api && docker compose up -d"
bash tests/consultas_api.sh http://<ip>:8001
```

El `.env` del servidor tiene solo `PUERTO=8001`, con permisos 600. Ver `.env.example`.

## Actualizar cada semana

Después del job del martes: exportar de nuevo, reconstruir la imagen y volver a subirla con los mismos comandos.
`/health` muestra la fecha de la copia de oro para saber si está al día.
