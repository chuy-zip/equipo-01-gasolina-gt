# Informe técnico

La fuente editable es [informe.md](informe.md). La redacción es formal y académica, en primera persona plural. Cubre calidad de extracción, variables del modelo, resultados frente a la línea base, cómputo y lecciones aprendidas.

Archivos generados:

- [informe.docx](informe.docx): versión editable en LibreOffice Writer.
- [informe.pdf](informe.pdf): versión de cinco páginas.
- [../docs/informe.pdf](../docs/informe.pdf): copia idéntica en la ruta de entrega del enunciado.

## Regeneración

Desde la raíz del repositorio:

```bash
python informe/generar.py
```

Se requieren Python 3, Pandoc, LibreOffice y `pdfinfo` (Poppler). El script convierte Markdown a un ODT temporal con Pandoc, aplica formato A4 con fuente Liberation Serif de 11 puntos y genera el DOCX con LibreOffice. Luego exporta ese DOCX a PDF con LibreOffice y comprueba que no supere cinco páginas antes de reemplazar los entregables. Emplea un perfil temporal independiente de LibreOffice.

Editar el Markdown y regenerar mantiene los tres entregables sincronizados. Los cambios hechos solamente en el DOCX se pierden al regenerar.

## Alcance de las cifras

Versión 2, del 16 de noviembre de 2026. Cada cifra sale de una de estas fuentes:

| Cifras | Fuente |
|---|---|
| Exactitud de extracción, 26 de 44 | Ejecución posterior a la revisión manual del 2026-11-15 |
| Precios y rechazos en plata, 266 y 211 | `presentacion/capturas/05_silver_precios.png` y `06_silver_rechazos.png` |
| Métricas del modelo v4 y de la línea base | Corrida `logistica_mem_eia_fotos` en MLflow, `presentacion/capturas/03_mlflow_experimento.png` |
| Aporte de las fotos, bootstrap y permutación | `docs/modelo/modelo.md`, sección "Efecto de las fotos" |
| Corridas del job y duración por tarea | `presentacion/capturas/01_job_historial.png` y `02_job_grafo.png` |
| Predicción de la semana del 2026-11-10 | `presentacion/capturas/07_gold_predicciones.png` |
| Versión del modelo en la API | Consulta a `/health` y `/modelo/metricas` de la API pública el 2026-11-16 |

Si se despliega el `champion` v4 en el Droplet, hay que actualizar el párrafo **API** de la sección 4.
