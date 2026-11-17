# Informe técnico

**Monitoreo y predicción del precio de los combustibles en Guatemala**  
Equipo 01 · MLOps · Universidad del Valle de Guatemala  
16 de noviembre de 2026

## 1. Calidad de la extracción y tratamiento de datos

Desarrollamos en Databricks un pipeline que convierte fotografías de dispensadores en precios de gasolina súper, regular y diésel. Con esos precios construye agregados semanales, predice la dirección del precio de la semana siguiente y publica los resultados en una API. Organizamos los datos en tablas Delta externas de bronce, plata y oro, dentro del catálogo `equipo_01` y en el bucket de S3 de cada capa. Complementamos las fotografías con el histórico diario del Ministerio de Energía y Minas (MEM), desde 2013, y con los precios internacionales de la Energy Information Administration (EIA).

**Bronce.** Cargamos las 110 fotografías del bucket con `binaryFile`. Comparamos sus rutas con la tabla mediante `left_anti` y aplicamos `MERGE` por `path`, de modo que una segunda carga no duplica filas. Conservamos el contenido binario y las columnas de auditoría `_ingestion_timestamp` y `_source_file`.

**Plata.** Elegimos un modelo de visión, Llama 4 Maverick, servido por el propio workspace. Le enviamos la imagen completa y un acercamiento a las pantallas inferiores, y nos devuelve en JSON la venta, los galones y los precios por combustible. Cuando el cociente entre venta y galones coincide con una de las ventanas, adoptamos ese cociente como precio exacto del combustible despachado. Obtenemos la fecha del EXIF, porque la carpeta no siempre refleja el año real de la toma. La ubicación es el municipio más cercano al GPS, sin almacenar coordenadas.

| Técnica evaluada sobre la revisión manual | Precios correctos |
|---|---|
| Llama 4 Maverick, técnica elegida | 26 de 44 visibles, **59.1 %** |
| RapidOCR con modelos PP-OCRv5, línea base | 3 de 31, 9.7 % (medición anterior) |
| Gemma 3 12B | Inferior a Maverick en una prueba de 10 fotografías |

Aplicamos nueve reglas de calidad. Entre ellas están las tres del enunciado: un precio entre Q20 y Q55 por galón, un combustible dentro del catálogo y una fecha no futura. Justificamos el rango con la referencia del MEM, que osciló entre Q24.80 y Q49.40 en el periodo de las fotografías. Añadimos una regla que rechaza desviaciones superiores al 15 % respecto de la referencia vigente ese día, porque casi siempre delatan un dígito mal leído. La última ejecución dejó **266 precios válidos** en `silver.precios`: 93 de súper, 95 de regular y 78 de diésel, del 14 de diciembre de 2022 al 8 de noviembre de 2026. También dejó **211 filas** en `silver.precios_rejected`. Los motivos fueron combustible fuera de catálogo (88, la ventana de V-Power), combustible no identificado (59), precio no leído (36) y desviación de la referencia (28).

Para medir la exactitud, el equipo revisó a mano 20 fotografías y registró los precios legibles en `data/revision_manual/revision_fotos.csv`. Comparamos por archivo y combustible con una tolerancia de un centavo. Contamos como error tanto una lectura equivocada como un precio visible que no llegó a plata. Antes habíamos medido entre 68 % y 71 % sobre 31 precios. No interpretamos la diferencia como una degradación: ampliamos y corregimos la referencia manual, y la última ejecución evaluó extracciones existentes, sin fotos nuevas. Los errores dominantes son los reflejos nocturnos y la confusión entre 4 y 9 en pantallas de siete segmentos.

## 2. Variables y formulación del modelo

Formulamos una clasificación de tres clases sobre la dirección del precio de la semana siguiente: `sube`, `baja` o `se_mantiene`. Agrupamos los datos de martes a lunes, como los precios de referencia del MEM, e identificamos cada semana por su martes inicial. La etiqueta compara el precio de cierre de la semana siguiente con el actual. Asignamos `sube` a un cambio de al menos Q0.10, `baja` a uno de como máximo menos Q0.10 y `se_mantiene` al resto. Elegimos ese umbral porque reparte la historia en clases comparables: en la súper, 38 % de las semanas bajan, 32 % suben y 30 % se mantienen. Excluimos las semanas incompletas y dejamos sin etiqueta la última semana completa, que es la que se predice.

Construimos una fila por semana y combustible en `gold.features_modelo`, con 17 variables que integran las tres fuentes del pipeline:

| Grupo | Variables y significado |
|---|---|
| Combustible | `combustible`: súper, regular o diésel, codificado con variables indicadoras. |
| Cambios locales (MEM) | `cambio_l1` a `cambio_l4`: cambio semanal del precio en las cuatro últimas semanas. |
| Tendencia local (MEM) | `tendencia_4` y `tendencia_8`: precio de cierre menos su media móvil de 4 u 8 semanas. |
| Contexto (MEM) | `tipo_cambio_cambio`: cambio semanal del tipo de cambio; `mes`: mes del cierre. |
| Relación entre combustibles (MEM) | `otro_super_l1`, `otro_regular_l1` y `otro_diesel_l1`: último cambio de cada combustible. |
| Mercado internacional (EIA) | `intl_cambio_1` a `intl_cambio_3`: cambios del precio internacional convertido a quetzales. |
| Brecha (MEM y EIA) | `brecha_vs_8`: precio local menos internacional, comparado con su media de 8 semanas. |
| Fotografías | `foto_disponible`: 1 si hubo foto válida en la semana; `foto_brecha`: precio de las fotos menos el oficial. |

Para evitar fuga de información, el precio internacional de cada semana es el promedio de los siete días anteriores al lunes de cierre, sin incluirlo. Completamos los días sin publicación del MEM con el último precio conocido y los marcamos como imputados. Las semanas sin fotografía valen cero en las dos variables de fotos y no se descartan. Así el modelo sigue aprendiendo de trece años de historia oficial: 110 fotografías en cuatro años no alcanzan para entrenar por sí solas.

Usamos las fuentes complementarias por una razón empírica. En la prueba de viabilidad, con solo el histórico del MEM, ningún modelo superó a la regla de repetir la semana anterior. Al agregar el precio internacional, la regresión logística la superó desde 2022, mientras que Gradient Boosting fue menos estable entre periodos. Por eso elegimos una regresión logística multiclase con estandarización de las variables numéricas, `OneHotEncoder` para el combustible, ponderación de clases `balanced` y un máximo de 3000 iteraciones, todo dentro de un mismo `Pipeline` de scikit-learn. Las variables con más peso fueron la brecha contra el precio internacional y el cambio internacional de la semana anterior, lo que es coherente con la forma en que se fijan los precios locales.

## 3. Evaluación frente a la línea base

Aplicamos una partición temporal, nunca aleatoria. Reservamos las últimas 104 semanas para la prueba, desde el 5 de noviembre de 2024, con 312 filas, y entrenamos con las 1818 filas anteriores. La línea base es la regla del enunciado: repetir la dirección de la semana anterior. Evaluamos ambas con las mismas etiquetas y registramos parámetros, métricas y la huella de los datos en el experimento `/Shared/equipo-01-tendencia` de MLflow. La tabla resume la corrida de la versión 4, que es el `champion` vigente:

| Métrica | Regresión logística (v4) | Línea base |
|---|---:|---:|
| Exactitud balanceada | **0.564** | 0.458 |
| F1 macro | **0.561** | 0.458 |
| Acierto de dirección en semanas con movimiento | **0.736** | 0.640 |

**El modelo supera a la línea base** en unos once puntos de exactitud balanceada. Un clasificador aleatorio de tres clases obtendría 0.33. Usamos la exactitud balanceada como métrica principal porque promedia la sensibilidad de cada clase y evita que una clase frecuente domine el resultado. El acierto en semanas con movimiento solo considera las filas en que tanto la etiqueta como la predicción son `sube` o `baja`, así que la calculamos sobre subconjuntos distintos para el modelo y la regla. La reportamos como complemento, no como métrica principal.

Medimos también el aporte de las fotografías, con la misma partición. De las 312 filas de prueba, 147 tienen foto.

| Variables | Exactitud balanceada |
|---|---:|
| MEM y EIA | 0.548 |
| MEM, EIA y fotografías | 0.564 |

Para saber si esa mejora es real o ruido hicimos dos pruebas. Un bootstrap de 2000 remuestreos por semanas dio una mejora de +0.016, con un intervalo de 95 % entre menos 0.023 y +0.054. En 81 % de los remuestreos ganó el modelo con fotos. Una prueba de permutación con 200 corridas, que baraja las variables de fotos entre semanas y reentrena, dio p = 0.02. Concluimos que las fotos aportan información real, pero con tan pocas semanas fotografiadas la mejora es pequeña y su intervalo incluye el cero.

Después de evaluar, reentrenamos con todas las semanas etiquetadas y registramos el modelo en Unity Catalog como `equipo_01.gold.modelo_tendencia_precio`, con el alias `champion`. La tarea de predicción escribe en `gold.predicciones` una fila por combustible con la clase, su probabilidad, la probabilidad de cada clase y la versión. Para la semana del 10 de noviembre de 2026 predijo `baja` en los tres combustibles, con probabilidades de 0.93 en regular, 0.92 en diésel y 0.95 en súper. Cuando se conoce la semana objetivo, la misma tarea completa `direccion_real` y `acierto`. Esas filas acumuladas medirán el desempeño con semanas nuevas, que es la evaluación más honesta.

Reconocemos tres limitaciones. Primero, hay cambios que ningún dato anticipa, como la baja de Q9.10 del 5 de octubre de 2026 por la exención de impuestos del Decreto 22-2026. Segundo, el modelo predice el precio de referencia nacional, no el de una estación concreta. Tercero, el 59.1 % de la extracción y las métricas de clasificación miden cosas distintas: el primero mide la lectura de fotografías y las segundas, la dirección semanal.

## 4. Configuración de cómputo, orquestación y despliegue

Trabajamos en un workspace compartido de Databricks Free Edition. Esta edición solo ofrece cómputo serverless y no permite crear clusters propios. Por eso adaptamos los dos tipos de cluster que pide el enunciado a sus equivalentes serverless:

| Aspecto | Desarrollo (equivale al cluster interactivo) | Ejecución (equivale al job cluster) |
|---|---|---|
| Cómputo | Serverless interactivo de notebooks | Serverless de jobs, asignado por corrida |
| Runtime, nodos y workers | Administrados por Databricks; el entorno se ve en el panel Environment | Igual, sin valores fijados en el bundle |
| Apagado | Automático por inactividad | Se libera al terminar cada corrida |
| Librerías | `%pip` por notebook: `pillow-heif`, `reverse_geocoder`; OCR de línea base con `rapidocr` y `onnxruntime`; MLflow incluido | Las del pipeline, instaladas por cada tarea; el OCR queda fuera del job |

La diferencia de costo y propósito se mantiene. Un cluster interactivo sirve para explorar y depurar, y cobra mientras está encendido aunque nadie lo use; por eso el enunciado exige su autoterminación. Un job cluster existe solo durante la corrida, así que solo cobra el tiempo útil y es más barato para cargas programadas. Además reduce el trabajo repetido: el pipeline omite las fotos ya tratadas, solo recarga el MEM y la EIA si cambia su hash y solo reentrena si cambia la huella de `gold.features_modelo`. No presentamos cifras monetarias, porque Free Edition no expone la facturación.

El job `equipo-01-pipeline` tiene nueve tareas en tres ramas paralelas, una por fuente: ingesta en bronce, limpieza en plata y, al final, oro, entrenamiento y predicción. Conserva el orden bronce, plata y oro del enunciado y separa cada capa por fuente, para probar y reejecutar cada tarea por separado. Corre cada martes a las 8:00, hora de Guatemala, cuando el MEM publica los precios. Envía un correo si falla y admite una sola corrida simultánea. Recibe como parámetros el catálogo, los esquemas, la ubicación de las fotos, el modelo de visión y los indicadores de reproceso. Lo definimos como código con un bundle de Databricks, que GitHub Actions despliega solo al integrar en `main`, después de pasar los checks `plan` y `tests`.

El historial registra cuatro corridas exitosas, iniciadas con **Run now** el 13, el 15 (dos) y el 16 de noviembre de 2026, de entre 2 min 7 s y 2 min 19 s. En la corrida del 16 las ingestas duraron entre 29 y 32 s, las tareas de plata entre 14 y 38 s, oro 18 s, el entrenamiento 28 s y la predicción 21 s. Las capturas están en `presentacion/capturas/`. Cumplimos solo en parte el requisito de dos corridas con fotos de semanas distintas: las 110 fotografías ya estaban cargadas y no llegaron fotos nuevas entre corridas, de modo que las corridas posteriores confirmaron la idempotencia en lugar de incorporar semanas nuevas.

**API.** Publicamos una API en FastAPI, en Docker con `restart: unless-stopped`, en el puerto 8001 del Droplet (<http://157.230.171.204:8001/docs>). Ofrece los cinco endpoints del enunciado, con filtros, `limit` y `offset`. Nos apartamos del enunciado en un punto: el Droplet no tiene acceso a los buckets, así que, de acuerdo con el catedrático, la imagen empaqueta el modelo y una copia de las tablas de oro. Esa decisión elimina las credenciales de AWS del servidor. Al 16 de noviembre, `/health` reporta `version_modelo: local`, es decir, artefactos generados con `scripts/exportar_local.py` con MEM y EIA (exactitud balanceada de 0.548). Todavía no son el `champion` v4. Coinciden con Databricks en la predicción vigente (`baja` en los tres combustibles), y el siguiente despliegue debe usar `scripts/exportar_para_api.py`.

## 5. Lecciones aprendidas

**La revisión humana es la única medida real de la extracción.** Un precio plausible puede tener un dígito equivocado y aun así pasar el control de rango. La regla de desviación frente al MEM y el cálculo de venta entre galones atraparon la mayoría de esos errores, pero solo la revisión manual mostró cuántos precios visibles se perdían. Mantendremos una versión fija del conjunto revisado y compararemos cualquier cambio del extractor contra ella antes de comparar porcentajes.

**Un modelo de visión general superó al OCR especializado.** RapidOCR no reconoce bien los dígitos de siete segmentos, y PaddleOCR se cae en el cómputo serverless, que es ARM. Llama 4 Maverick ya estaba disponible en el workspace, no tuvo costo dentro de la cuota y las imágenes no salieron de Databricks. Aprendimos a medir varias técnicas sobre las mismas fotografías antes de elegir una.

**El tiempo es la fuente de errores más sutil.** Las carpetas no reflejaban el año real de las fotos y por eso adoptamos el EXIF. En el modelo, cualquier dato publicado después del cierre de la semana produce resultados irreales. Por eso usamos semanas completas de martes a lunes, promedios internacionales anteriores al lunes y una partición temporal estricta.

**Más datos complementarios valen más que un modelo más complejo.** La regresión logística con el precio internacional superó a Gradient Boosting y a cualquier modelo con solo datos del MEM. Las fotografías aportaron una mejora pequeña pero estadísticamente distinguible del azar. Sin las pruebas de bootstrap y permutación habríamos sobrestimado ese aporte o lo habríamos descartado.

**Las restricciones del entorno moldearon la arquitectura.** En Free Edition no hay clusters propios, `%pip` puede romper Spark si cambia la versión de `numpy` y las ubicaciones de solo lectura impidieron al principio escribir en los buckets. Lo resolvimos con tablas externas, después de que el catedrático habilitó `CREATE EXTERNAL TABLE`, y con una API autocontenida porque el Droplet no accede a S3.

**La automatización necesita trazabilidad.** El bundle, el CI y la regla de que solo el CI despliega dieron a todo el equipo una misma versión del job. La versión de la API, en cambio, se actualiza a mano y se quedó atrás del `champion`. Con más tiempo automatizaríamos ese despliegue, conservaríamos la relación entre cada corrida y las fotografías que procesó, y descargaríamos el Excel del MEM sin intervención manual.

**Fuentes.** Enunciado en `docs/contexto/`. Extracción en `src/gas_price/fotos.py` y `21_silver_imagenes.py`. Variables y modelo en `src/gas_price/features.py`, `src/gas_price/modelo.py` y `docs/modelo/modelo.md`. Orquestación en `resources/pipeline.yml` y `docs/infraestructura/`. Evidencia de ejecución en `presentacion/capturas/`.
