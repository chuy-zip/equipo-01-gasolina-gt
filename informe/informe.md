# Informe técnico

**Monitoreo y predicción del precio de los combustibles en Guatemala**  
Equipo 01 · MLOps · Universidad del Valle de Guatemala  
16 de noviembre de 2026

## 1. Calidad de la extracción y tratamiento de datos

Desarrollamos un pipeline en Databricks para transformar fotografías de dispensadores en precios de gasolina súper, regular y diésel, construir agregados semanales y publicar consultas y predicciones mediante una API. Organizamos los datos en tablas Delta de bronce, plata y oro dentro del catálogo `equipo_01`. Complementamos las fotografías con precios oficiales del Ministerio de Energía y Minas (MEM) y series internacionales de la Energy Information Administration (EIA).

Incorporamos 110 fotografías a bronce mediante `binaryFile`, comparación de rutas y `MERGE` por `path`. En plata utilizamos Llama 4 Maverick, al que enviamos la imagen completa y un acercamiento a las pantallas inferiores. Extraemos la venta, el volumen despachado y los precios por combustible. Cuando identificamos una coincidencia única con una ventana, utilizamos el cociente entre venta y galones como precio del combustible despachado. Obtenemos la fecha del EXIF y conservamos una ubicación textual derivada del GPS, sin almacenar las coordenadas en las filas de precios.

Aplicamos controles de catálogo, integridad y plausibilidad: admitimos los tres combustibles definidos, exigimos un precio entre Q20 y Q55 por galón y una fecha válida no futura. Cuando contamos con una referencia del MEM, rechazamos diferencias superiores al 15 %. Enviamos las lecturas fallidas y los duplicados a `silver.precios_rejected`, con el motivo correspondiente. En `silver.precios` consolidamos los registros por fecha, ubicación, combustible y modalidad; consignamos la modalidad como `no_indicada` cuando la fotografía no la informa.

Revisamos manualmente 20 fotografías, con registro a nombre de Nelson Garcia el 15 de noviembre de 2026. Conservamos los precios legibles y los comentarios en `data/revision_manual/revision_fotos.csv`; dejamos vacíos los valores que no pudimos determinar. En la evaluación posterior obtuvimos 26 aciertos de 44 precios visibles, equivalentes al **59.1 %**. Comparamos por archivo y combustible con una tolerancia de `0.011` quetzales, aproximadamente un centavo. Contamos como desacierto un precio visible sin correspondencia en plata; por ello, medimos tanto los errores de lectura como las ausencias después de los filtros.

Registramos anteriormente 21–22 aciertos de 31 precios con el modelo de visión y 3 de 31 con RapidOCR, aproximadamente 68–71 % y 9.7 %, respectivamente. No interpretamos la diferencia con el 59.1 % como una degradación comprobada: ampliamos y corregimos la referencia manual, y no repetimos la evaluación de OCR sobre los 44 precios. La última ejecución procesó cero fotos nuevas y evaluó las extracciones existentes. Identificamos dificultades con reflejos, dígitos de siete segmentos y confusiones entre 4 y 9; con esta muestra tampoco estimamos la exactitud de todo el conjunto de fotografías.

## 2. Variables y formulación del modelo

Formulamos una clasificación de la dirección del precio para la semana siguiente: `sube`, `baja` o `se_mantiene`. Agrupamos los datos de martes a lunes e identificamos cada semana por su martes inicial. Definimos la etiqueta mediante la diferencia entre el precio de cierre de la semana siguiente y el actual: asignamos `sube` para cambios de al menos Q0.10 y `baja` para cambios de como máximo −Q0.10; dentro de ese intervalo asignamos `se_mantiene`. Excluimos semanas incompletas y conservamos sin etiqueta la última semana completa para generar la predicción.

Construimos una observación por semana y combustible en `gold.features_modelo`, a partir del historial del MEM y las series de la EIA. Aunque incorporamos las fotografías a `gold.precio_semanal` y `gold.variacion_semanal`, no utilizamos actualmente sus precios como variables de entrenamiento. Disponemos de una cobertura fotográfica irregular y sustentamos la serie histórica del clasificador en las fuentes complementarias.

| Grupo | Variables que incorporamos y significado |
|---|---|
| Combustible | `combustible`: súper, regular o diésel, codificado mediante variables indicadoras. |
| Cambios locales | `cambio_l1` a `cambio_l4`: cambio observado al cierre de la semana y los tres anteriores. |
| Tendencia local | `tendencia_4` y `tendencia_8`: precio de cierre menos su media móvil de cuatro u ocho semanas. |
| Tipo de cambio y calendario | `tipo_cambio_cambio`: diferencia semanal del tipo de cambio; `mes`: mes del cierre semanal. |
| Relación entre combustibles | `otro_super_l1`, `otro_regular_l1` y `otro_diesel_l1`: cambios semanales de los tres combustibles. |
| Mercado internacional | `intl_cambio_1` a `intl_cambio_3`: cambios del precio internacional convertido a quetzales. |
| Brecha local e internacional | `brecha_vs_8`: diferencia entre ambos precios respecto de su media de ocho semanas. |

Utilizamos 15 variables numéricas y una categórica. Para los precios internacionales calculamos un promedio de los siete días anteriores al lunes de cierre, sin incluir ese lunes. Completamos días sin publicación del MEM con el último precio conocido y los marcamos como imputados. Aunque conservamos el régimen fiscal en los datos, no lo incluimos en la lista de variables que consume el clasificador vigente.

Implementamos una regresión logística con estandarización de variables numéricas, codificación `OneHotEncoder` del combustible, ponderación de clases `balanced` y un máximo de 3000 iteraciones. Ajustamos las transformaciones dentro del mismo pipeline de entrenamiento. En las pruebas exploratorias documentadas encontramos mayor estabilidad con esta configuración que con Gradient Boosting, y observamos que las variables internacionales aportaban información adicional frente al uso exclusivo del MEM.

## 3. Evaluación frente a la línea base

Reservamos las últimas 104 semanas con etiqueta para evaluar y entrenamos con las semanas anteriores, mediante una partición temporal. Comparamos la regresión logística con la regla de repetir la dirección de la semana anterior, utilizando los mismos umbrales para las tres clases. Evaluamos el modelo antes del ajuste final con todos los datos etiquetados y registramos parámetros, métricas y versión en MLflow.

Presentamos los resultados históricos documentados en `docs/modelo/modelo.md`, obtenidos con los datos disponibles al 12 de noviembre de 2026. Para este informe revisamos su correspondencia con la implementación de `src/gas_price/modelo.py`; no ejecutamos un nuevo entrenamiento.

| Métrica | Regresión logística | Línea base |
|---|---:|---:|
| Exactitud balanceada | 0.55 | 0.46 |
| F1 macro | 0.55 | 0.46 |
| Acierto de dirección condicionado a movimiento | 0.74 | 0.64 |

Obtenemos una diferencia aproximada de nueve puntos porcentuales en exactitud balanceada. Empleamos esta métrica porque promedia la sensibilidad de las clases y evita que una clase frecuente determine por sí sola el resultado. Con F1 macro concedemos el mismo peso a cada clase al combinar precisión y sensibilidad. No disponemos de intervalos de confianza ni de una prueba de significancia para atribuir la diferencia a una mejora estadísticamente concluyente.

Interpretamos con cautela el acierto condicionado a movimiento: en el código incluimos únicamente las filas en las que tanto la etiqueta real como la predicción pertenecen a `sube` o `baja`. Excluimos los casos en que cualquiera de ellas es `se_mantiene`. Por tanto, calculamos esta métrica sobre subconjuntos que pueden variar entre el modelo y la regla; no la presentamos como exactitud sobre todas las semanas con movimiento real.

Después de evaluar, ajustamos el modelo final con todas las semanas etiquetadas y lo registramos con el alias `champion`. Guardamos las predicciones por semana objetivo y combustible en `gold.predicciones`, junto con la versión y las probabilidades de clase. Cuando disponemos del resultado real, completamos la dirección observada y el acierto. Conservamos las métricas de evaluación histórica en `gold.metricas_modelo`.

Distinguimos el 59.1 % de la revisión de imágenes de las métricas de clasificación: el primero corresponde a la recuperación de precios visibles y las segundas a la dirección del precio semanal del MEM. Para valorar la evolución futura necesitamos acumular predicciones emitidas antes de observar la semana objetivo. Reconocemos además la sensibilidad del modelo a cambios fiscales, variaciones del mercado internacional y diferencias entre la referencia oficial y los precios de una estación específica.

## 4. Configuración de cómputo y evidencia de ejecución

Trabajamos en el workspace compartido de Databricks Free Edition con cómputo serverless. Utilizamos notebooks interactivos durante el desarrollo y tareas serverless para ejecutar el job. No definimos clusters propios en el bundle; dejamos a la plataforma la asignación de infraestructura. Documentamos esta configuración y mantenemos pendiente la confirmación académica de su equivalencia con los clusters solicitados en el enunciado.

| Aspecto | Configuración que utilizamos |
|---|---|
| Desarrollo | Notebooks con cómputo serverless interactivo. |
| Ejecución programada | Job `equipo-01-pipeline`, con nueve tareas y dependencias entre ingesta, plata, oro, entrenamiento y predicción. |
| Runtime, nodos y workers | Sin valores fijados en el bundle; administración a cargo de Databricks. |
| Dependencias | Instalación por notebook; para imágenes empleamos `pillow-heif` y `reverse_geocoder`. |
| Concurrencia | Una corrida simultánea del job (`max_concurrent_runs: 1`). |
| Programación | Martes a las 08:00, zona `America/Guatemala`; notificación por correo ante fallos. |
| Reprocesamiento | `reprocesar_fotos=false` y `forzar_entrenamiento=false` por defecto. |

Para comparar propósitos, reservamos el cómputo interactivo para exploración y depuración, mientras que automatizamos el procesamiento con el job. En una configuración de clusters propios tendríamos que definir runtime, tamaño, workers y autoterminación del interactivo, así como el cómputo efímero de ejecución. En nuestro entorno serverless no fijamos esos parámetros ni presentamos una estimación monetaria: no contamos con mediciones de facturación del proyecto. Reducimos trabajo repetido al omitir fotos ya tratadas y evitar reentrenamientos cuando no cambian los datos.

En las capturas compartidas por el equipo observamos varias ejecuciones exitosas en el historial del job. En otro resumen de `silver.precios` observamos 266 registros distribuidos en tres grupos de combustible, con fechas desde el 14 de diciembre de 2022 hasta el 8 de noviembre de 2026; el máximo de uno de los grupos corresponde al 26 de octubre de 2026. Contamos registros de precios, no fotografías únicas, porque una foto puede aportar varios combustibles.

Utilizamos ambas observaciones como evidencia complementaria de ejecución y cobertura temporal. No identificamos en esas vistas las fotos incorporadas por cada corrida ni la versión de código utilizada; por ello mantenemos como parcial la evidencia del requisito de dos ejecuciones con fotos de semanas distintas. Para completar la trazabilidad necesitamos conservar identificadores de corrida, duración de cada tarea y relación con las imágenes procesadas. La ejecución que produjo 26/44 evaluó datos ya existentes y reportó cero fotos nuevas.

## 5. Lecciones aprendidas y alcance del trabajo

**Revisión humana y criterios de calidad.** Aprendimos que un precio numéricamente plausible puede contener un dígito incorrecto y superar los controles de rango. La revisión de 20 fotografías nos permitió corregir la referencia de evaluación y reconocer precios ilegibles. Mantendremos los casos ambiguos explícitos y evaluaremos cualquier modificación del extractor contra la misma versión del conjunto manual antes de comparar porcentajes.

**Consistencia temporal.** Encontramos fotografías cuya carpeta no reflejaba correctamente el año de captura y adoptamos la fecha del EXIF. Para el modelo descartamos semanas incompletas y limitamos las variables internacionales a información anterior al cierre. También distinguimos la agrupación exploratoria de lunes a domingo de las semanas de martes a lunes que implementamos en oro; las etiquetas semanales de una consulta exploratoria no sustituyen la convención del pipeline.

**Incrementalidad y evidencia.** Comprobamos que una segunda carga puede terminar correctamente sin incorporar fotos nuevas. Diferenciamos ese comportamiento de la cobertura histórica de plata y de la validación de predicciones futuras. Al preparar el informe identificamos que las capturas agregadas no conservan la relación entre archivos y ejecuciones; incorporaremos esa relación a la evidencia que guardemos en trabajos posteriores.

**Restricciones del entorno.** Adaptamos la lectura de HEIC y la extracción al cómputo disponible. Durante las pruebas documentadas encontramos dificultades para ejecutar PaddleOCR en el entorno serverless y utilizamos RapidOCR como alternativa para la línea base. En almacenamiento, adoptamos tablas externas con `CREATE EXTERNAL TABLE` después de resolver los permisos de escritura por capa; mantuvimos la ubicación de entrada de fotografías en modo de solo lectura.

**Versionado y despliegue.** Integramos código, configuración del job y reglas de calidad en Git, y registramos modelos con MLflow. El equipo confirmó el despliegue de la API en el Droplet. Identificamos dos rutas de generación de artefactos: descargar `champion` y oro desde Databricks, o entrenar localmente con `scripts/exportar_local.py`. Aún necesitamos documentar cuál de esos conjuntos de artefactos utiliza la imagen desplegada y conservar una prueba pública de su respuesta.

**Fuentes internas utilizadas.** Sustentamos este informe en el enunciado del proyecto, el código versionado y los resultados documentados o compartidos por el equipo. Conservamos las siguientes referencias para contrastar procedimientos y mediciones:

- Enunciado: `docs/contexto/enunciado_proyecto_final.pdf`.
- Extracción y referencia manual: `src/gas_price/fotos.py`, notebook `21_silver_imagenes.py` y `data/revision_manual/revision_fotos.csv`.
- Variables y evaluación: `src/gas_price/features.py`, `src/gas_price/modelo.py` y `docs/modelo/modelo.md`.
- Cómputo y orquestación: `resources/pipeline.yml`, `databricks.yml` y `docs/infraestructura/databricks.md`.
- Evidencia de operación: capturas compartidas por Nelson Garcia del historial del job, del resumen de plata y del resultado de exactitud; estado consolidado en `docs/plan/handoff_equipo.md`.
