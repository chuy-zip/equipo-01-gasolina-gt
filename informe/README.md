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

La métrica de extracción procede de la ejecución compartida por Nelson (26/44); las métricas predictivas proceden de la evaluación histórica documentada en `docs/modelo/modelo.md`. El informe no presenta un nuevo entrenamiento ni atribuye fotografías a corridas concretas a partir de capturas agregadas. Las capturas compartidas en la conversación no están incrustadas en los archivos.
