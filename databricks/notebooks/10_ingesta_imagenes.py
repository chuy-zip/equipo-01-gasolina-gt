# Databricks notebook source
# MAGIC %md
# MAGIC # 10 Ingesta de fotos a bronce
# MAGIC
# MAGIC 1. Lee las fotos con `binaryFile` por la external location donde las deja el catedrático.
# MAGIC 2. Agrega a `bronze.fotos_precios` solo las que no estaban, con `MERGE` por `path`.
# MAGIC 3. Guarda el contenido original y las columnas de auditoría `_ingestion_timestamp` y `_source_file`.
# MAGIC
# MAGIC Una segunda corrida no duplica fotos. Al final compara las filas de bronce con las fotos de la carpeta.
# MAGIC
# MAGIC La ubicación y la carpeta llegan como parámetros. Si las fotos nuevas llegan a otra carpeta,
# MAGIC por ejemplo `fotos/AAAA-MM-DD/`, solo cambian los parámetros del job.

# COMMAND ----------

# En un job, los parámetros llegan como widgets. Los valores por defecto sirven para correrlo a mano.
dbutils.widgets.text("catalogo", "equipo_01")
dbutils.widgets.text("esquema_bronze", "bronze")
dbutils.widgets.text("ubicacion_fotos", "xloc-raw")
dbutils.widgets.text("carpeta_fotos", "")

catalogo = dbutils.widgets.get("catalogo")
esquema_bronze = dbutils.widgets.get("esquema_bronze")
ubicacion_fotos = dbutils.widgets.get("ubicacion_fotos")
carpeta_fotos = dbutils.widgets.get("carpeta_fotos")

# COMMAND ----------

import os
import sys

from pyspark.sql import functions as F

# El código compartido vive en src/, dos carpetas arriba de este notebook.
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "..", "..", "src")))
from gas_price import fotos

TABLA = f"{catalogo}.{esquema_bronze}.fotos_precios"

# La URL sale de la external location. Así no queda escrita en el repo, que es público.
url_ubicacion = spark.sql(f"DESCRIBE EXTERNAL LOCATION `{ubicacion_fotos}`").collect()[0]["url"]
url = fotos.url_fotos(url_ubicacion, carpeta_fotos)
print("External location:", ubicacion_fotos)
print("Carpeta:", carpeta_fotos or "(raíz)")

# COMMAND ----------

# Primero solo las rutas, sin leer el contenido, para saber cuáles faltan.
en_carpeta = (
    spark.read.format("binaryFile")
    .option("recursiveFileLookup", "true")
    .load(url)
    .select("path")
    .filter(F.col("path").rlike(fotos.regex_imagenes()))
)
ya_cargadas = spark.table(TABLA).select("path")
nuevas = en_carpeta.join(ya_cargadas, "path", "left_anti")

total_carpeta = en_carpeta.count()
total_nuevas = nuevas.count()
print("Fotos en la carpeta:", total_carpeta)
print("Fotos nuevas:", total_nuevas)

# COMMAND ----------

if total_nuevas > 0:
    rutas_nuevas = [fila.path for fila in nuevas.collect()]
    # Se lee el contenido solo de las fotos nuevas.
    filas = (
        spark.read.format("binaryFile")
        .load(rutas_nuevas)
        .withColumn("_ingestion_timestamp", F.current_timestamp())
        .withColumn("_source_file", F.col("path"))
        .select(*spark.table(TABLA).columns)
    )
    filas.createOrReplaceTempView("fotos_nuevas")
    # MERGE por path: si una corrida se repite o falla a medias, no se duplican fotos.
    spark.sql(f"""
        MERGE INTO {TABLA} AS destino
        USING fotos_nuevas AS origen
        ON destino.path = origen.path
        WHEN NOT MATCHED THEN INSERT *
    """)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Criterio de aceptación
# MAGIC
# MAGIC El número de filas en bronce coincide con el número de fotos en la carpeta, sin rutas repetidas.

# COMMAND ----------

bronce = spark.table(TABLA)
filas_bronce = bronce.filter(F.col("path").startswith(url)).count()
rutas_distintas = bronce.select("path").distinct().count()

print("Filas en bronce para esta carpeta:", filas_bronce)
print("Fotos en la carpeta:", total_carpeta)
assert rutas_distintas == bronce.count(), "Hay fotos repetidas en bronce"
assert filas_bronce == total_carpeta, "Bronce no coincide con la carpeta"

display(
    bronce.groupBy(F.to_date("_ingestion_timestamp").alias("fecha_carga"))
    .agg(F.count("*").alias("fotos"), F.round(F.sum("length") / 1e6, 1).alias("total_mb"))
    .orderBy("fecha_carga")
)

dbutils.notebook.exit(f"Nuevas: {total_nuevas}. En bronce: {filas_bronce} de {total_carpeta}")
