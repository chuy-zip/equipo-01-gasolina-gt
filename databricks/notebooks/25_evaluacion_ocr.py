# Databricks notebook source
# MAGIC %md
# MAGIC # 25 Línea base con OCR
# MAGIC
# MAGIC Compara la extracción de plata contra OCR clásico en las mismas 20 fotos de la revisión manual.
# MAGIC No es parte del pipeline y no escribe tablas. Sirve para justificar la técnica elegida en el informe.
# MAGIC
# MAGIC 1. El OCR es RapidOCR con los modelos PP-OCRv5 de PaddleOCR. PaddleOCR no corre en el cómputo serverless,
# MAGIC    que es ARM. RapidOCR usa los mismos modelos sobre ONNX Runtime.
# MAGIC 2. Lee la mitad baja de cada foto, donde están las ventanas de precio.
# MAGIC 3. A cada etiqueta de combustible le asigna el número que está encima.
# MAGIC 4. Calcula la exactitud con la misma revisión manual que usa el notebook 21.

# COMMAND ----------

# Las fotos se copian al volumen antes de instalar librerías, porque después Spark no está disponible.
# Los widgets se conservan al reiniciar Python.
dbutils.widgets.text("catalogo", "equipo_01")
dbutils.widgets.text("esquema_bronze", "bronze")
dbutils.widgets.text("repo_raw", "https://raw.githubusercontent.com/chuy-zip/equipo-01-gasolina-gt/main")

import os

import pandas as pd
from pyspark.sql import functions as F

catalogo = dbutils.widgets.get("catalogo")
esquema_bronze = dbutils.widgets.get("esquema_bronze")
repo_raw = dbutils.widgets.get("repo_raw")

TEMPORAL = f"/Volumes/{catalogo}/{esquema_bronze}/archivos/evaluacion_ocr"
os.makedirs(TEMPORAL, exist_ok=True)

revision = pd.read_csv(f"{repo_raw}/data/revision_manual/revision_fotos.csv")
revision.to_csv(f"{TEMPORAL}/revision.csv", index=False)
nombres = revision["archivo"].tolist()

fotos_bronce = (
    spark.table(f"{catalogo}.{esquema_bronze}.fotos_precios")
    .withColumn("archivo", F.element_at(F.split("path", "/"), -1))
    .filter(F.col("archivo").isin(nombres))
    .select("archivo", "content")
    .collect()
)
for fila in fotos_bronce:
    with open(f"{TEMPORAL}/{fila.archivo}", "wb") as archivo:
        archivo.write(fila.content)
print("Fotos copiadas:", len(fotos_bronce))

# COMMAND ----------

# MAGIC %pip install -q "rapidocr>=3.4" onnxruntime pillow-heif "numpy<2" "opencv-python-headless<4.11"

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

import os
import sys

import numpy as np
import pandas as pd
import pillow_heif
from PIL import Image, ImageOps
from rapidocr import LangDet, LangRec, ModelType, OCRVersion, RapidOCR

sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "..", "..", "src")))
from gas_price import fotos

pillow_heif.register_heif_opener()
catalogo = dbutils.widgets.get("catalogo")
esquema_bronze = dbutils.widgets.get("esquema_bronze")
TEMPORAL = f"/Volumes/{catalogo}/{esquema_bronze}/archivos/evaluacion_ocr"

ocr = RapidOCR(params={
    "Det.ocr_version": OCRVersion.PPOCRV5, "Det.lang_type": LangDet.CH, "Det.model_type": ModelType.MOBILE,
    "Rec.ocr_version": OCRVersion.PPOCRV5, "Rec.lang_type": LangRec.CH, "Rec.model_type": ModelType.MOBILE,
})

revision = pd.read_csv(f"{TEMPORAL}/revision.csv")
filas = []
for nombre in revision["archivo"]:
    ruta = f"{TEMPORAL}/{nombre}"
    if not os.path.exists(ruta):
        continue
    imagen = ImageOps.exif_transpose(Image.open(ruta)).convert("RGB")
    ancho, alto = imagen.size
    abajo = imagen.crop((0, alto // 2, ancho, alto))
    resultado = ocr(np.array(abajo)[:, :, ::-1])
    cajas = []
    for texto, poligono in zip(resultado.txts or [], resultado.boxes if resultado.boxes is not None else []):
        poligono = np.array(poligono)
        cajas.append({"texto": texto, "caja": [*poligono.min(axis=0).tolist(), *poligono.max(axis=0).tolist()]})
    for combustible, precio in fotos.precios_desde_ocr(cajas).items():
        filas.append({"archivo": nombre, "combustible": combustible, "precio_q_galon": precio})

extraido = pd.DataFrame(filas, columns=["archivo", "combustible", "precio_q_galon"])
comparacion = fotos.exactitud(extraido, revision)
aciertos = int(comparacion["correcto"].sum())
print(f"Precios visibles en las fotos revisadas: {len(comparacion)}")
print(f"OCR correcto: {aciertos} ({aciertos / len(comparacion):.0%})")
display(comparacion)

# COMMAND ----------

# Se borran las copias temporales de las fotos.
for nombre in os.listdir(TEMPORAL):
    os.remove(f"{TEMPORAL}/{nombre}")

dbutils.notebook.exit(f"OCR {aciertos}/{len(comparacion)}")
