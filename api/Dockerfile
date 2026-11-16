# La imagen lleva el código de la API, el modelo champion y la copia de oro.
# Antes de construirla: python scripts/exportar_para_api.py, que llena api/artefactos/.
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY artefactos ./artefactos

ENV RUTA_ARTEFACTOS=/app/artefactos
EXPOSE 8000

# Usuario sin privilegios dentro del contenedor.
RUN useradd --create-home api
USER api

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
