# Informe técnico

La fuente editable es [informe.md](informe.md). La redacción es formal y académica, en primera persona plural. Cubre calidad de extracción, variables del modelo, resultados frente a la línea base, cómputo y lecciones aprendidas.

Archivos generados:

- [informe.docx](informe.docx): versión editable, sincronizada con el Markdown y maquetada en A4 con Times New Roman de 11 puntos.
- [informe.pdf](informe.pdf): versión de cinco páginas.
- [../docs/informe.pdf](../docs/informe.pdf): copia idéntica en la ruta de entrega del enunciado.

## Regeneración

La edición vigente se generó desde el Markdown, conservando las cinco tablas y una sección por página. Se exportó el DOCX a PDF mediante Microsoft Word, se comprobó la paginación y se revisaron visualmente las cinco páginas antes de actualizar las dos copias del PDF.

El script disponible en el repositorio ofrece una ruta alternativa con LibreOffice. Desde la raíz:

```bash
python informe/generar.py
```

Esta alternativa requiere Python 3, Pandoc, LibreOffice y `pdfinfo` (Poppler). Convierte el Markdown a un ODT temporal, aplica A4 con Liberation Serif de 11 puntos, genera el DOCX y lo exporta a PDF con LibreOffice. Comprueba que no supere cinco páginas antes de reemplazar los entregables y usa un perfil temporal independiente. El script conserva ese formato anterior y no reproduce exactamente la maquetación de Word de la edición vigente.

El Markdown es la fuente del contenido. Después de cualquier regeneración, comprobar que el DOCX y el PDF mantengan las cinco secciones, las cinco tablas, las métricas y el enlace de la API; revisar también las páginas y copiar la misma exportación a ambas rutas del PDF. Los cambios hechos solamente en el DOCX se pierden al regenerar.

## Alcance de las cifras

Edición revisada el 19 de noviembre de 2026. Esa es la fecha del informe; las fechas de los datos y las evaluaciones se conservan. Cada cifra sale de una de estas fuentes:

| Cifras | Fuente |
|---|---|
| Exactitud de extracción, 26 de 44 | Ejecución posterior a la revisión manual del 2026-11-15 |
| Precios y rechazos en plata, 266 y 211 | `presentacion/capturas/05_silver_precios.png` y `06_silver_rechazos.png` |
| Métricas del modelo v4 y de la línea base | Corrida `logistica_mem_eia_fotos` en MLflow, `presentacion/capturas/03_mlflow_experimento.png` |
| Aporte de las fotos, bootstrap y permutación | `docs/modelo/modelo.md`, sección "Efecto de las fotos" |
| Corridas del job y duración por tarea | `presentacion/capturas/01_job_historial.png` y `02_job_grafo.png` |
| Predicción de la semana del 2026-11-10 | `presentacion/capturas/07_gold_predicciones.png` |
| Modelo local de una verificación previa | Consulta a `/health` y `/modelo/metricas` de la API pública el 2026-11-16 |
| Modelo v4 desplegado en la API | Despliegue registrado en `docs/plan/plan_implementacion.md` y respuestas guardadas el 2026-11-17 en `presentacion/datos/api_respaldo.js` |

La sección 4 distingue la verificación anterior del modelo local del despliegue posterior del `champion` v4. La actualización de la API sigue siendo manual. La evidencia de corridas con fotos de semanas distintas continúa siendo parcial.
