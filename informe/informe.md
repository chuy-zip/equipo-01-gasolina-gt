# Informe técnico

**Monitoreo y predicción del precio de los combustibles en Guatemala**  
Equipo 01 · MLOps · Universidad del Valle de Guatemala  
Fecha del informe: 19 de noviembre de 2026

## 1. Calidad de la extracción y tratamiento de datos

Desarrollamos en Databricks un flujo de procesamiento (pipeline) que extrae precios de gasolina súper, regular y diésel de fotografías. Para predecir su dirección semanal, incorporamos el histórico diario del Ministerio de Energía y Minas (MEM), desde 2013, y los precios internacionales de la Energy Information Administration (EIA), la agencia de información energética de Estados Unidos. Organizamos tablas Delta externas en Bronce, Plata y Oro, bajo el catálogo `equipo_01`, con un contenedor de almacenamiento (bucket) de AWS S3 por capa. Una API permite consultar precios y predicciones.

**Bronce.** Cargamos las 110 fotografías con `binaryFile`. Identificamos los archivos nuevos y aplicamos `MERGE` según su ruta, sin duplicar filas al repetir la carga. Conservamos el contenido binario, la fecha de ingesta y la ruta de origen para rastrear cada fotografía.

**Plata.** Llama 4 Maverick, un modelo de visión disponible en Databricks, recibe la imagen completa y un acercamiento a las pantallas inferiores. Devuelve venta, galones y precios en JSON. Si el cociente entre venta y galones coincide con un precio de las pantallas, usamos ese valor calculado para el combustible despachado. Obtenemos la fecha de los metadatos EXIF, porque las carpetas no siempre reflejan el año de captura. Asignamos el municipio más cercano a las coordenadas GPS, sin guardarlas. Lo contrastamos con reconocimiento óptico de caracteres (OCR) y otro modelo de visión:

| Técnica de extracción | Resultado de la revisión manual |
|---|---|
| Llama 4 Maverick, técnica elegida | 26 de 44 visibles, **59.1 %** |
| RapidOCR con modelos PP-OCRv5, línea base | 3 de 31, 9.7 % (medición anterior) |
| Gemma 3 12B | Inferior a Maverick en una prueba de 10 fotografías |

Aplicamos nueve reglas de calidad, incluidas las tres sugeridas en el enunciado: precio entre 20 y 55 quetzales (Q) por galón, combustible válido y fecha no futura. Justificamos el rango con el MEM, que registró entre Q24.80 y Q49.40 durante el periodo fotografiado. Rechazamos desviaciones superiores al 15 % frente a la referencia del día por posibles errores de lectura. Registramos **266 precios válidos** en `silver.precios`: 93 de súper, 95 de regular y 78 de diésel, del 14 de diciembre de 2022 al 8 de noviembre de 2026. En `silver.precios_rejected` quedaron **211 filas**: combustible fuera de catálogo (88, V-Power), combustible no identificado (59), precio no leído (36) y desviación de la referencia (28).

Revisamos manualmente 20 fotografías y registramos los precios legibles como referencia de evaluación. Comparamos por archivo y combustible, con tolerancia de un centavo; contamos como error las lecturas incorrectas y los precios visibles ausentes de Plata. Las mediciones previas, de 68 % a 71 % sobre 31 precios, usaron una referencia que después ampliamos y corregimos. Evaluamos extracciones almacenadas, sin procesar fotos nuevas: el cambio de exactitud no demuestra una degradación del extractor. La medición anterior de RapidOCR tampoco es directamente comparable. Predominaron los reflejos nocturnos y las confusiones entre 4 y 9 en pantallas de siete segmentos.

## 2. Variables y formulación del modelo

Formulamos el problema como una clasificación de la dirección del precio de la semana siguiente: `sube`, `baja` o `se_mantiene`. Agrupamos los datos de martes a lunes e identificamos cada semana por su martes inicial. La etiqueta compara el precio de cierre de la semana siguiente con el de la semana observada: un aumento de al menos Q0.10 se clasifica como `sube`; una disminución de al menos Q0.10, como `baja`; y el resto, como `se_mantiene`. El umbral produce clases de tamaños comparables: en la súper, 38 % de las semanas bajan, 32 % suben y 30 % se mantienen. Excluimos semanas incompletas; la última completa queda sin etiqueta y aporta las variables para predecir la siguiente.

En Oro calculamos promedios, mínimos y máximos en `gold.precio_semanal`, y cambios en quetzales y porcentajes en `gold.variacion_semanal`. Construimos una fila por semana y combustible en `gold.features_modelo`, con **17 variables numéricas y el tipo de combustible**, agrupados así:

| Grupo | Variables y significado |
|---|---|
| Combustible | `combustible`: súper, regular o diésel, codificado con variables indicadoras. |
| Cambios locales (MEM) | `cambio_l1` a `cambio_l4`: cambio semanal del precio en las cuatro últimas semanas. |
| Tendencia local (MEM) | `tendencia_4` y `tendencia_8`: precio de cierre menos su media móvil de 4 u 8 semanas. |
| Contexto (MEM) | `tipo_cambio_cambio`: cambio semanal del tipo de cambio; `mes`: mes del cierre. |
| Relación entre combustibles (MEM) | `otro_super_l1`, `otro_regular_l1` y `otro_diesel_l1`: último cambio de cada combustible. |
| Mercado internacional (EIA) | `intl_cambio_1` a `intl_cambio_3`: cambios del precio internacional convertido a quetzales. |
| Brecha (MEM y EIA) | `brecha_vs_8`: diferencia entre el precio local y el internacional, menos su media de 8 semanas. |
| Fotografías | `foto_disponible`: 1 si hubo foto válida del combustible en la semana; `foto_brecha`: precio promedio de las fotos menos el oficial. |

Para evitar usar información posterior al periodo observado, calculamos el precio internacional con los siete días anteriores al lunes de cierre, sin incluirlo. Completamos los días sin publicación del MEM con el último precio conocido y los marcamos como imputados. Las semanas sin fotografía reciben cero en ambas variables de fotos y permanecen en el conjunto. Entrenamos con trece años de historia oficial, ya que las 110 fotografías distribuidas en cuatro años eran insuficientes por sí solas.

En la prueba de viabilidad, los modelos con solo MEM no mejoraron de forma consistente la regla de repetir la dirección anterior. Con precios internacionales, la regresión logística la superó en los periodos evaluados desde 2022; Gradient Boosting fue menos estable. Elegimos una regresión logística multiclase en scikit-learn, con estandarización numérica, variables indicadoras para el combustible, ponderación para compensar las diferencias de tamaño entre clases y un máximo de 3000 iteraciones. Integramos la preparación de datos y el clasificador en un mismo proceso. Las variables con mayor peso fueron la brecha frente al precio internacional y su cambio de la semana anterior.

## 3. Evaluación frente a la línea base

Separamos los datos por tiempo: entrenamos con las 1818 filas anteriores a la prueba y reservamos las últimas 104 semanas, desde el 5 de noviembre de 2024, con 312 filas. Comparamos el modelo con la línea base del enunciado, que repite la dirección de la semana anterior, usando las mismas etiquetas. Registramos parámetros, métricas y una huella que identifica los datos en un experimento compartido de MLflow, la herramienta de seguimiento de experimentos. Estos resultados corresponden a la versión 4, seleccionada como `champion` en la evaluación documentada:

| Métrica | Regresión logística (v4) | Línea base |
|---|---:|---:|
| Exactitud balanceada | **0.564** | 0.458 |
| F1 macro | **0.561** | 0.458 |
| Acierto de dirección en semanas con movimiento | **0.736** | 0.640 |

**El modelo supera a la línea base** en aproximadamente once puntos porcentuales de exactitud balanceada. Esta métrica promedia el acierto dentro de cada clase; la referencia esperada para un clasificador aleatorio de tres clases es 0.33. F1 macro combina precisión y sensibilidad, con igual peso para cada clase. El acierto en semanas con movimiento solo incluye filas cuya etiqueta y predicción son `sube` o `baja`. Como el modelo y la regla seleccionan subconjuntos distintos, sus valores no constituyen una comparación directa sobre los mismos casos; los reportamos como complemento.

Evaluamos el aporte de las fotografías con la misma partición temporal. De las 312 filas de prueba, 147 tienen foto.

| Variables | Exactitud balanceada |
|---|---:|
| MEM y EIA | 0.548 |
| MEM, EIA y fotografías | 0.564 |

Estimamos la incertidumbre mediante bootstrap, un remuestreo por semanas: con 2000 repeticiones, la mejora fue de +0.016 y el intervalo del 95 % abarcó de -0.023 a +0.054. El modelo con fotos obtuvo un resultado superior en el 81 % de los remuestreos. Además, una prueba de permutación con 200 ejecuciones, que redistribuye las variables de fotos entre semanas y reentrena, produjo p = 0.02. La permutación sugiere información predictiva bajo ese procedimiento, pero el intervalo incluye cero y no permite afirmar una mejora concluyente.

Después de evaluar, reentrenamos con todas las semanas etiquetadas y registramos el modelo en Unity Catalog, el catálogo de Databricks, como `equipo_01.gold.modelo_tendencia_precio`, con el alias `champion`. La tarea de predicción guarda en `gold.predicciones` la clase, su probabilidad, las probabilidades de cada clase y la versión, por semana y combustible. Para la semana objetivo del 10 de noviembre de 2026 predijo `baja`: 0.93 en regular, 0.92 en diésel y 0.95 en súper. Cuando se dispone del resultado observado, la tarea añade la dirección real y el acierto para evaluar predicciones emitidas antes de conocerlo.

El modelo puede no anticipar intervenciones fiscales como la baja de Q9.10 del 5 de octubre de 2026, atribuida a la exención de impuestos del Decreto 22-2026. Además, predice la dirección del precio de referencia nacional, no el de una estación concreta. El 59.1 % mide la extracción de precios de fotografías y debe distinguirse de las métricas de predicción semanal.

## 4. Configuración de cómputo, orquestación y despliegue

Trabajamos en un entorno compartido de Databricks Free Edition, con cómputo serverless, administrado por la plataforma y sin clusters propios. Adaptamos los entornos de desarrollo y ejecución solicitados en el enunciado a las opciones disponibles:

| Aspecto | Desarrollo (función del cluster interactivo) | Ejecución (función del job cluster) |
|---|---|---|
| Cómputo | Serverless interactivo de notebooks | Serverless de jobs, asignado por ejecución |
| Runtime, nodos y workers | Versión de ejecución y recursos administrados por Databricks; entorno visible en el panel de configuración | Administrados por Databricks, sin valores fijados en la configuración |
| Apagado | Automático por inactividad | Recursos liberados al terminar cada ejecución |
| Librerías | Instalación por notebook: `pillow-heif`, `reverse_geocoder`; OCR de línea base con `rapidocr` y `onnxruntime`; MLflow incluido | Librerías del pipeline instaladas por tarea; OCR fuera del job |

El cluster interactivo sirve para explorar y depurar; en un entorno facturado, mantenerlo encendido sin uso genera costos, de ahí la autoterminación. El job cluster se crea para una ejecución y se elimina al terminar, lo que limita el tiempo de recursos inactivos en cargas programadas. No medimos ahorros monetarios, porque Free Edition no expone la facturación. Para evitar trabajo repetido, omitimos fotos procesadas, recargamos MEM y EIA solo si cambia su huella digital y reentrenamos cuando cambia la de `gold.features_modelo`.

El job `equipo-01-pipeline` organiza nueve tareas: tres ramas paralelas de ingesta y limpieza, una por fuente, que convergen en Oro, entrenamiento y predicción. Mantiene el orden Bronce, Plata y Oro y permite reejecutar tareas por separado. Está programado los martes a las 8:00, hora de Guatemala, envía un correo si falla y admite una sola ejecución a la vez. Parametrizamos catálogo, esquemas, ubicación de fotos, modelo de visión e indicadores de reproceso. Un bundle, o paquete de configuración de Databricks, define el job; GitHub Actions lo despliega al integrar los cambios en la rama principal, tras superar las validaciones automáticas y las pruebas. La actualización de los archivos fuente sigue requiriendo intervención del equipo.

Documentamos cuatro ejecuciones exitosas iniciadas manualmente, de entre 2 min 7 s y 2 min 19 s. En la última, las ingestas duraron entre 29 y 32 s; Plata, entre 14 y 38 s; Oro, 18 s; entrenamiento, 28 s; y predicción, 21 s. Conservamos capturas del historial y de la duración de las tareas. El requisito de dos ejecuciones con fotos de semanas distintas quedó parcialmente cubierto: las 110 fotografías ya estaban cargadas y no llegaron nuevas entre pruebas. Las repeticiones comprobaron la idempotencia, es decir, la conservación del resultado al procesar los mismos datos.

**API.** Publicamos el servicio con FastAPI y Docker en el puerto 8001 del servidor Droplet de DigitalOcean (<http://157.230.171.204:8001/docs>), con reinicio automático del contenedor salvo detención manual. Ofrece las cinco rutas de consulta del enunciado, con filtros y paginación. Como el Droplet no accede a S3, acordamos con el catedrático empaquetar el modelo y una copia de Oro en la imagen, sin credenciales de AWS en el servidor. Una verificación previa registró un modelo local con MEM y EIA y exactitud balanceada de 0.548. Después desplegamos el `champion` v4 y las tablas Oro exportadas desde Databricks. El respaldo de la API registra la versión 4 y las mismas métricas y predicciones que Databricks para los tres combustibles. La actualización de la imagen sigue siendo manual.

## 5. Lecciones aprendidas

Durante la extracción encontramos precios con dígitos incorrectos que pasaban el control de rango. La comparación con el MEM y el cociente entre venta y galones ayudaron a detectarlos, pero la revisión manual también identificó precios legibles que no llegaban a Plata. Al corregir esa referencia cambió el porcentaje de aciertos; para futuras comparaciones, mantendremos una versión fija del conjunto revisado.

RapidOCR tuvo dificultades con los dígitos de siete segmentos y PaddleOCR falló en el cómputo serverless con arquitectura ARM. Usamos Llama 4 Maverick sin costo adicional dentro de la cuota del entorno y sin enviar las imágenes fuera de Databricks.

Las diferencias entre las carpetas y las fechas de captura nos llevaron a usar el EXIF. También tuvimos que alinear las tres fuentes con el cierre semanal y distinguirlo de la semana objetivo, para no incorporar información posterior a la predicción.

La comparación entre periodos nos llevó a incorporar precios internacionales y a elegir la regresión logística. Al evaluar las fotografías, tuvimos que distinguir la mejora observada de la incertidumbre sobre su magnitud. Para ampliar esa evaluación necesitamos más semanas fotografiadas.

Las restricciones del entorno también exigieron ajustes. Los cambios de `numpy` al instalar librerías podían afectar Spark, y los permisos iniciales impedían escribir en los buckets. Trabajamos con tablas externas después de que el catedrático habilitó la escritura y el permiso para crearlas.

El despliegue del job mediante integración continua en GitHub Actions mantuvo una configuración común para el equipo, mientras que la API dependió de una actualización manual. Quedaron pendientes la automatización de ese despliegue y de la descarga del Excel del MEM, además de un registro que vincule cada ejecución con las fotografías procesadas.
