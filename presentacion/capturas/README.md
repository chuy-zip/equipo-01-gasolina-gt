# Capturas para el anexo (plan B)

Las diapositivas 22 y 23 muestran estas imágenes. Si un archivo no existe, la diapositiva muestra un recuadro con el nombre esperado.

Formato para todas:

- PNG, en modo oscuro de Databricks si es posible.
- Ventana del navegador a 1920 × 1080 o más, con zoom al 100 %.
- Recortar la barra del navegador y las pestañas. Dejar solo el contenido.
- Proporción cercana a 16:9. Cada recuadro de la diapositiva mide unos 800 × 340.
- Sin correos, tokens, URL completas de buckets ni coordenadas GPS: el repo es público.

| Archivo | Qué debe mostrar | Dónde |
|---|---|---|
| `01_job_historial.png` | Historial de corridas de `equipo-01-pipeline`: al menos 2 corridas exitosas con fecha y duración | Jobs & Pipelines, `equipo-01-pipeline`, pestaña **Runs** |
| `02_job_grafo.png` | Grafo de las 9 tareas de una corrida exitosa, con la duración de cada tarea | Abrir una corrida, vista **Graph** o **Timeline** |
| `03_mlflow_experimento.png` | Corridas del experimento con las métricas `balanced_accuracy` del modelo y de la línea base | Experiments, `/Shared/equipo-01-tendencia` |
| `04_modelo_champion.png` | Modelo registrado con su versión y el alias `champion` | Catalog, `equipo_01.gold.modelo_tendencia_precio` |
| `05_silver_precios.png` | Conteo de `silver.precios` por combustible y rango de fechas | SQL Editor: `SELECT combustible, COUNT(*), MIN(fecha), MAX(fecha) FROM equipo_01.silver.precios GROUP BY 1` |
| `06_silver_rechazos.png` | Conteo de rechazos por motivo | SQL Editor: `SELECT motivo, COUNT(*) FROM equipo_01.silver.precios_rejected GROUP BY 1 ORDER BY 2 DESC` |
| `07_gold_predicciones.png` | Filas de la predicción más reciente, con probabilidad y versión | SQL Editor: `SELECT * FROM equipo_01.gold.predicciones ORDER BY semana DESC LIMIT 6` |
| `08_api_swagger.png` | Swagger de la API pública con los 5 endpoints | <http://157.230.171.204:8001/docs> |

Si se agrega o cambia una captura, volver a exportar el PDF:

```
python presentacion/herramientas/exportar_pdf.py
```
