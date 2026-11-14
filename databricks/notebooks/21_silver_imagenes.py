# Databricks notebook source
# MAGIC %md
# MAGIC # 21 Fotos a plata
# MAGIC
# MAGIC Convierte cada foto de bronce en precios por combustible.
# MAGIC
# MAGIC 1. **Lectura.** Un modelo de visión del workspace, Llama 4 Maverick, lee las pantallas del dispensador:
# MAGIC    la venta, los galones y las ventanas de precio por combustible. Recibe la foto completa y un acercamiento a la parte baja.
# MAGIC 2. **Precio despachado.** Venta entre galones da el precio exacto del combustible que se cargó.
# MAGIC    Si coincide con una ventana, esa fila usa el precio calculado.
# MAGIC 3. **Fecha y ubicación.** La fecha sale del EXIF. La ubicación es el municipio y departamento más cercanos al GPS.
# MAGIC    No se guardan coordenadas.
# MAGIC 4. **Reglas de calidad.** Combustible en el catálogo, precio leído, precio entre Q20 y Q55, fecha no futura
# MAGIC    y precio a menos de 15 % de la referencia del MEM. Lo que falla va a `silver.precios_rejected` con el motivo.
# MAGIC 5. **Escritura.** `MERGE` en `silver.precios` por fecha, ubicación, combustible y modalidad.
# MAGIC
# MAGIC Solo se procesan las fotos que todavía no están en plata. Una segunda corrida no cambia nada.
# MAGIC La técnica elegida y la comparación con OCR están en `docs/datos/fuentes_de_datos.md`.

# COMMAND ----------

# MAGIC %pip install -q pillow-heif reverse_geocoder

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

# En un job, los parámetros llegan como widgets. Los valores por defecto sirven para correrlo a mano.
dbutils.widgets.text("catalogo", "equipo_01")
dbutils.widgets.text("esquema_bronze", "bronze")
dbutils.widgets.text("esquema_silver", "silver")
dbutils.widgets.text("repo_raw", "https://raw.githubusercontent.com/chuy-zip/equipo-01-gasolina-gt/main")
dbutils.widgets.text("modelo_vision", "databricks-llama-4-maverick")
# "true" vuelve a leer todas las fotos, por ejemplo si cambia el modelo o las instrucciones.
dbutils.widgets.text("reprocesar_fotos", "false")

catalogo = dbutils.widgets.get("catalogo")
esquema_bronze = dbutils.widgets.get("esquema_bronze")
esquema_silver = dbutils.widgets.get("esquema_silver")
repo_raw = dbutils.widgets.get("repo_raw")
modelo_vision = dbutils.widgets.get("modelo_vision")
reprocesar = dbutils.widgets.get("reprocesar_fotos").lower() == "true"

# COMMAND ----------

import base64
import datetime as dt
import io
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pandas as pd
import pillow_heif
import reverse_geocoder
from databricks.sdk import WorkspaceClient
from PIL import Image, ImageOps
from pyspark.sql import functions as F

# El código compartido vive en src/, dos carpetas arriba de este notebook.
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "..", "..", "src")))
from gas_price import fotos

pillow_heif.register_heif_opener()

BRONCE = f"{catalogo}.{esquema_bronze}.fotos_precios"
PRECIOS = f"{catalogo}.{esquema_silver}.precios"
RECHAZADOS = f"{catalogo}.{esquema_silver}.precios_rejected"
OFICIALES = f"{catalogo}.{esquema_silver}.precios_oficiales"
HOY = dt.date.today()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Fotos por procesar

# COMMAND ----------

procesadas = spark.table(PRECIOS).select("foto_origen").union(spark.table(RECHAZADOS).select("foto_origen")).distinct()
pendientes = spark.table(BRONCE).select("path")
if not reprocesar:
    pendientes = pendientes.join(procesadas, pendientes.path == procesadas.foto_origen, "left_anti")
rutas = sorted(fila.path for fila in pendientes.collect())
print("Fotos en bronce:", spark.table(BRONCE).count())
print("Fotos por procesar:", len(rutas))
# Sin fotos nuevas, las celdas siguientes no escriben nada y el resumen se muestra igual.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Lectura con el modelo de visión

# COMMAND ----------

cliente = WorkspaceClient()


def a_grados(valor, referencia):
    if not valor:
        return None
    grados, minutos, segundos = (float(x) for x in valor)
    decimal = grados + minutos / 60 + segundos / 3600
    return -decimal if referencia in ("S", "W") else decimal


def a_base64(imagen, lado_maximo):
    copia = imagen.copy()
    copia.thumbnail((lado_maximo, lado_maximo))
    salida = io.BytesIO()
    copia.save(salida, "JPEG", quality=90)
    return base64.b64encode(salida.getvalue()).decode()


def leer_foto(ruta, contenido):
    """Devuelve la fecha, el GPS y la respuesta del modelo. Los errores quedan como lectura fallida."""
    resultado = {"foto_origen": ruta, "fecha": None, "latitud": None, "longitud": None, "respuesta": None}
    try:
        with Image.open(io.BytesIO(contenido)) as original:
            exif = original.getexif()
            resultado["fecha"] = fotos.fecha_de_exif(exif.get_ifd(0x8769).get(0x9003) or exif.get(0x0132))
            gps = exif.get_ifd(0x8825)
            if gps:
                resultado["latitud"] = a_grados(gps.get(2), gps.get(1))
                resultado["longitud"] = a_grados(gps.get(4), gps.get(3))
            imagen = ImageOps.exif_transpose(original).convert("RGB")
        ancho, alto = imagen.size
        abajo = imagen.crop((0, alto // 2, ancho, alto))
        cuerpo = {
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": fotos.INSTRUCCIONES_MODELO},
                {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + a_base64(imagen, 1600)}},
                {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + a_base64(abajo, 2400)}},
            ]}],
            "max_tokens": 300,
            "temperature": 0,
        }
        respuesta = cliente.api_client.do("POST", f"/serving-endpoints/{modelo_vision}/invocations", body=cuerpo)
        resultado["respuesta"] = respuesta["choices"][0]["message"]["content"]
    except Exception as e:
        print("No se pudo leer", ruta.rsplit("/", 1)[-1], type(e).__name__, str(e)[:200])
    return resultado


# Se leen por lotes para no cargar todas las fotos en memoria a la vez.
lecturas = []
for inicio in range(0, len(rutas), 20):
    lote = spark.table(BRONCE).filter(F.col("path").isin(rutas[inicio:inicio + 20])).select("path", "content").collect()
    with ThreadPoolExecutor(max_workers=4) as hilos:
        lecturas += list(hilos.map(lambda fila: leer_foto(fila.path, fila.content), lote))
    print(f"Leídas {len(lecturas)} de {len(rutas)}")

lecturas = pd.DataFrame(lecturas, columns=["foto_origen", "fecha", "latitud", "longitud", "respuesta"])

# COMMAND ----------

# Municipio y departamento más cercanos al GPS, con una base de lugares que viene en la librería.
# Así la ubicación queda legible y no se guardan coordenadas.
con_gps = lecturas["latitud"].notna()
lecturas["ubicacion"] = "sin_ubicacion"
if con_gps.any():
    lugares = reverse_geocoder.search(list(zip(lecturas.loc[con_gps, "latitud"], lecturas.loc[con_gps, "longitud"])), mode=1)
    lecturas.loc[con_gps, "ubicacion"] = [f"{l['name']}, {l['admin1']}" for l in lugares]

# COMMAND ----------

# MAGIC %md
# MAGIC ## Filas y reglas de calidad

# COMMAND ----------

filas = []
for lectura in lecturas.itertuples():
    for fila in fotos.filas_de_lectura(fotos.parsear_lectura(lectura.respuesta)):
        filas.append({**fila, "fecha": lectura.fecha, "ubicacion": lectura.ubicacion,
                      "modalidad": fotos.MODALIDAD, "foto_origen": lectura.foto_origen})
filas = pd.DataFrame(filas, columns=["combustible", "precio_q_galon", "motivo_previo", "fecha", "ubicacion",
                                     "modalidad", "foto_origen"])

oficiales = spark.table(OFICIALES).select("fecha", "combustible", "precio_q_galon").toPandas()
filas = fotos.agregar_referencia(filas, oficiales)
filas["motivo"] = [
    fotos.motivo_rechazo(f.combustible, f.precio_q_galon, f.fecha, f.referencia, HOY, f.motivo_previo)
    for f in filas.itertuples()
]

# La llave se revisa contra lo que ya está en plata. Si otra foto ya tiene esa llave, la más reciente se queda
# y la otra pasa a cuarentena como duplicada. Así cada foto queda registrada en alguna de las dos tablas.
existentes = (
    spark.table(PRECIOS).join(spark.createDataFrame([(r,) for r in rutas], "foto_origen STRING"), "foto_origen", "left_anti")
    .toPandas().assign(_nueva=False)
)
nuevas = filas[filas["motivo"].isna()].assign(_nueva=True)
quedan, duplicadas = fotos.separar_duplicados(pd.concat([existentes, nuevas], ignore_index=True))
validas = quedan[quedan["_nueva"]]
duplicadas = duplicadas.assign(motivo="duplicado")
rechazadas = pd.concat([filas[filas["motivo"].notna()], duplicadas], ignore_index=True)

print("Fotos procesadas:", lecturas["foto_origen"].nunique())
print("Filas válidas:", len(validas))
print("Filas rechazadas:", len(rechazadas))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Escritura

# COMMAND ----------

COLUMNAS = ["fecha", "combustible", "precio_q_galon", "modalidad", "ubicacion", "foto_origen"]
ESQUEMA = "fecha DATE, combustible STRING, precio_q_galon DECIMAL(10,2), modalidad STRING, ubicacion STRING, foto_origen STRING"


def a_spark(df, columnas, esquema):
    datos = df[columnas].astype(object).where(df[columnas].notna(), None)
    datos["precio_q_galon"] = [None if p is None else Decimal(f"{float(p):.2f}") for p in datos["precio_q_galon"]]
    return spark.createDataFrame(datos.to_dict("records"), schema=esquema)


# Las fotos de esta corrida se borran antes de escribir. Así reprocesar no deja filas viejas.
spark.createDataFrame([(r,) for r in rutas], "foto_origen STRING").createOrReplaceTempView("fotos_corrida")
spark.sql(f"DELETE FROM {RECHAZADOS} WHERE foto_origen IN (SELECT foto_origen FROM fotos_corrida)")
spark.sql(f"DELETE FROM {PRECIOS} WHERE foto_origen IN (SELECT foto_origen FROM fotos_corrida)")

if len(validas):
    a_spark(validas, COLUMNAS, ESQUEMA).createOrReplaceTempView("precios_nuevos")
    spark.sql(f"""
        MERGE INTO {PRECIOS} AS destino
        USING precios_nuevos AS origen
        ON destino.fecha = origen.fecha AND destino.ubicacion = origen.ubicacion
           AND destino.combustible = origen.combustible AND destino.modalidad = origen.modalidad
        WHEN MATCHED THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *
    """)

if len(rechazadas):
    # La tabla la define databricks/sql/tablas.sql. insertInto respeta esa definición.
    a_spark(rechazadas, COLUMNAS + ["motivo"], ESQUEMA + ", motivo STRING").select(
        *spark.table(RECHAZADOS).columns).write.insertInto(RECHAZADOS)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Resumen
# MAGIC
# MAGIC Cuántas fotos se procesaron, cuántas filas se rechazaron y por qué.

# COMMAND ----------

total_fotos = spark.table(BRONCE).count()
en_plata = spark.table(PRECIOS).select("foto_origen").distinct().count()
print("Fotos en bronce:", total_fotos)
print("Fotos con al menos un precio válido:", en_plata)
print("Filas en silver.precios:", spark.table(PRECIOS).count())
print("Filas en silver.precios_rejected:", spark.table(RECHAZADOS).count())

display(spark.table(RECHAZADOS).groupBy("motivo").count().orderBy(F.desc("count")))

# COMMAND ----------

display(spark.table(PRECIOS).groupBy("combustible").agg(
    F.count("*").alias("filas"), F.min("fecha").alias("desde"), F.max("fecha").alias("hasta"),
    F.min("precio_q_galon").alias("minimo"), F.max("precio_q_galon").alias("maximo")).orderBy("combustible"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Exactitud contra la revisión manual
# MAGIC
# MAGIC `data/revision_manual/revision_fotos.csv` tiene el precio real de cada combustible en 20 fotos, revisado a mano.
# MAGIC Un precio es correcto si coincide al centavo con el de `silver.precios`.

# COMMAND ----------

try:
    revision = pd.read_csv(f"{repo_raw}/data/revision_manual/revision_fotos.csv")
except Exception as e:
    revision = None
    print("No se encontró la revisión manual:", e)

if revision is not None:
    extraido = spark.table(PRECIOS).select("foto_origen", "combustible", "precio_q_galon").toPandas()
    extraido["archivo"] = extraido["foto_origen"].str.rsplit("/", n=1).str[-1]
    comparacion = fotos.exactitud(extraido, revision)
    aciertos = int(comparacion["correcto"].sum())
    print(f"Fotos revisadas: {revision['archivo'].nunique()}")
    print(f"Precios visibles en esas fotos: {len(comparacion)}")
    print(f"Extraídos correctamente: {aciertos} ({aciertos / len(comparacion):.0%})")
    display(comparacion.groupby("combustible")["correcto"].agg(["sum", "count", "mean"]).reset_index())
    display(comparacion)

dbutils.notebook.exit(f"Procesadas {len(rutas)} fotos. Válidas {len(validas)}. Rechazadas {len(rechazadas)}"
                      + (f". Exactitud {aciertos}/{len(comparacion)}" if revision is not None else ""))
