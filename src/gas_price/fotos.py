"""Reglas compartidas para las fotos de precios.

La lectura y la escritura con Spark quedan en los notebooks. Aquí va la lógica que se puede probar sin Spark:
qué archivos son fotos, cómo se interpreta la lectura del modelo de visión y las reglas de calidad.
"""

from __future__ import annotations

import datetime as dt
import json
import re

import pandas as pd

# Formatos de imagen que se cargan a bronce. Las fotos del bucket son HEIC del iPhone y un JPG.
EXTENSIONES_IMAGEN = ("heic", "heif", "jpg", "jpeg", "png", "webp")

# Catálogo del enunciado. V-Power aparece en los dispensadores pero no está en el catálogo.
COMBUSTIBLES = ("super", "regular", "diesel")
VENTANAS = ("diesel", "regular", "super", "v_power")

# Las fotos no indican si la bomba es de autoservicio o servicio completo.
MODALIDAD = "no_indicada"

# Rango de precio válido en quetzales por galón. Entre diciembre de 2022 y 2026, el periodo de las fotos,
# la referencia del MEM fue de Q24.80 a Q49.40. Se deja un margen hacia los dos lados.
PRECIO_MINIMO = 20.0
PRECIO_MAXIMO = 55.0

# Máxima diferencia contra la referencia del MEM de esa fecha. Una gasolinera cobra unos quetzales más o menos
# que el promedio nacional. Una diferencia mayor casi siempre es un dígito mal leído.
DESVIACION_MAXIMA = 0.15

# Tolerancia para decir que venta entre galones corresponde a una ventana de precio.
# Los precios de dos combustibles distintos casi nunca están a menos de Q0.10.
TOLERANCIA_DESPACHO = 0.10

MOTIVOS = (
    "lectura_fallida",
    "combustible_no_identificado",
    "combustible_fuera_de_catalogo",
    "precio_no_leido",
    "precio_fuera_de_rango",
    "fecha_nula",
    "fecha_futura",
    "desviado_de_referencia",
    "duplicado",
)

INSTRUCCIONES_MODELO = """Te doy dos imágenes del mismo dispensador de gasolina en Guatemala: la foto completa y un acercamiento a la parte baja.
Lee las pantallas LCD de 7 segmentos. Devuelve solo JSON:
{"venta_q": número o null, "galones": número o null,
 "precios": {"diesel": número o null, "regular": número o null, "super": número o null, "v_power": número o null}}
venta_q: pantalla "Esta Venta", dos decimales. galones: línea "Galones", tres decimales.
precios: ventanas pequeñas "Precio por galón" que están encima de cada etiqueta (Diesel, Regular, Super, V-Power). Asocia cada ventana con la etiqueta de su misma columna. Los precios tienen dos decimales, por ejemplo 28.59.
Cuidado con el 9 y el 4: en 7 segmentos el 9 tiene encendido el segmento de arriba y el 4 no. Revisa cada uno.
Si un número no se lee con claridad, pon null."""


def regex_imagenes() -> str:
    """Expresión regular, sin distinguir mayúsculas, que reconoce las rutas de imágenes."""
    return r"(?i)\.(" + "|".join(EXTENSIONES_IMAGEN) + r")$"


def es_imagen(ruta: str) -> bool:
    """True si la ruta termina en una extensión de imagen conocida."""
    return ruta.lower().rsplit(".", 1)[-1] in EXTENSIONES_IMAGEN if "." in ruta else False


def url_fotos(url_ubicacion: str, carpeta: str = "") -> str:
    """Une la URL de la external location con la carpeta de las fotos.

    La carpeta es configurable porque el enunciado habla de `fotos/AAAA-MM-DD/` y las fotos actuales
    están en la raíz de otra ubicación. Cambiar de una a otra es solo cambiar los parámetros del job.
    """
    base = url_ubicacion.rstrip("/") + "/"
    carpeta = carpeta.strip("/")
    return base + (carpeta + "/" if carpeta else "")


def fecha_de_exif(fecha_hora: str | None) -> dt.date | None:
    """Fecha de la toma a partir de `DateTimeOriginal`, que ya viene en hora local: `AAAA:MM:DD HH:MM:SS`."""
    if not fecha_hora:
        return None
    try:
        return dt.datetime.strptime(fecha_hora.strip()[:10], "%Y:%m:%d").date()
    except ValueError:
        return None


def _numero(valor) -> float | None:
    if valor is None or isinstance(valor, bool):
        return None
    try:
        numero = float(str(valor).replace(",", "."))
    except ValueError:
        return None
    return numero if numero > 0 else None


def parsear_lectura(texto: str | None) -> dict | None:
    """Convierte la respuesta del modelo en un diccionario con venta, galones y precios.

    Acepta el JSON solo o dentro de un bloque de código. Devuelve None si no hay JSON válido.
    """
    if not texto:
        return None
    encontrado = re.search(r"\{.*\}", texto, flags=re.DOTALL)
    if not encontrado:
        return None
    try:
        crudo = json.loads(encontrado.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(crudo, dict):
        return None
    precios = crudo.get("precios") if isinstance(crudo.get("precios"), dict) else {}
    return {
        "venta_q": _numero(crudo.get("venta_q")),
        "galones": _numero(crudo.get("galones")),
        "precios": {ventana: _numero(precios.get(ventana)) for ventana in VENTANAS},
    }


def precio_despachado(venta_q: float | None, galones: float | None) -> float | None:
    """Precio por galón de lo que se despachó: venta entre galones."""
    if not venta_q or not galones:
        return None
    return round(venta_q / galones, 2)


def confusion_7_segmentos(a: float, b: float) -> bool:
    """True si dos precios solo difieren en dígitos 4 y 9.

    En una pantalla de 7 segmentos el 9 y el 4 solo se distinguen por el segmento de arriba.
    Es el error de lectura más común en las fotos.
    """
    texto_a, texto_b = f"{a:.2f}", f"{b:.2f}"
    if texto_a == texto_b or len(texto_a) != len(texto_b):
        return False
    return all(x == y or {x, y} == {"4", "9"} for x, y in zip(texto_a, texto_b))


def combustible_despachado(precio: float | None, precios: dict, tolerancia: float = TOLERANCIA_DESPACHO) -> str | None:
    """Ventana cuyo precio coincide con el precio despachado. None si no hay una sola coincidencia.

    Coincide si está a menos de la tolerancia o si solo difiere por la confusión entre 4 y 9.
    """
    if precio is None:
        return None
    coinciden = [
        v for v, p in precios.items()
        if p is not None and (abs(p - precio) <= tolerancia or confusion_7_segmentos(p, precio))
    ]
    return coinciden[0] if len(coinciden) == 1 else None


def filas_de_lectura(lectura: dict | None) -> list[dict]:
    """Filas candidatas de una foto: una por ventana leída, más el precio despachado.

    Si venta entre galones coincide con una ventana, esa fila usa el precio calculado, que es más exacto.
    Si no coincide con ninguna, queda una fila sin combustible para que las reglas la rechacen.
    """
    if lectura is None:
        return [{"combustible": None, "precio_q_galon": None, "motivo_previo": "lectura_fallida"}]

    precios = lectura["precios"]
    despachado = precio_despachado(lectura["venta_q"], lectura["galones"])
    combustible = combustible_despachado(despachado, precios)

    filas = []
    for ventana in VENTANAS:
        precio = despachado if ventana == combustible else precios.get(ventana)
        if ventana not in COMBUSTIBLES and precio is None:
            continue
        filas.append({"combustible": ventana, "precio_q_galon": precio, "motivo_previo": None})
    if despachado is not None and combustible is None:
        filas.append({"combustible": None, "precio_q_galon": despachado, "motivo_previo": None})
    return filas


def motivo_rechazo(
    combustible: str | None,
    precio: float | None,
    fecha: dt.date | None,
    referencia: float | None,
    hoy: dt.date,
    motivo_previo: str | None = None,
) -> str | None:
    """Primera regla de calidad que falla, o None si la fila es válida."""
    if motivo_previo:
        return motivo_previo
    if combustible is None:
        return "combustible_no_identificado"
    if combustible not in COMBUSTIBLES:
        return "combustible_fuera_de_catalogo"
    if precio is None or pd.isna(precio):
        return "precio_no_leido"
    if not PRECIO_MINIMO <= precio <= PRECIO_MAXIMO:
        return "precio_fuera_de_rango"
    if fecha is None:
        return "fecha_nula"
    if fecha > hoy:
        return "fecha_futura"
    if referencia is not None and not pd.isna(referencia) and abs(precio / referencia - 1) > DESVIACION_MAXIMA:
        return "desviado_de_referencia"
    return None


def agregar_referencia(filas: pd.DataFrame, oficiales: pd.DataFrame) -> pd.DataFrame:
    """Agrega el último precio oficial del MEM vigente en la fecha de cada fila, por combustible.

    `filas` necesita `fecha` y `combustible`. `oficiales` necesita `fecha`, `combustible` y `precio_q_galon`.
    """
    resultado = filas.copy()
    resultado["referencia"] = None
    if oficiales.empty:
        return resultado
    ofi = oficiales[["fecha", "combustible", "precio_q_galon"]].dropna().copy()
    ofi["fecha"] = pd.to_datetime(ofi["fecha"])
    ofi["precio_q_galon"] = ofi["precio_q_galon"].astype(float)
    for combustible in COMBUSTIBLES:
        mascara = (resultado["combustible"] == combustible) & resultado["fecha"].notna()
        if not mascara.any():
            continue
        izquierda = resultado.loc[mascara, ["fecha"]].copy()
        izquierda["_orden"] = izquierda.index
        izquierda["fecha"] = pd.to_datetime(izquierda["fecha"])
        derecha = ofi[ofi["combustible"] == combustible].sort_values("fecha")[["fecha", "precio_q_galon"]]
        unido = pd.merge_asof(izquierda.sort_values("fecha"), derecha, on="fecha", direction="backward")
        resultado.loc[unido["_orden"], "referencia"] = unido["precio_q_galon"].to_numpy()
    return resultado


def separar_duplicados(validas: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Deja una fila por llave fecha, ubicación, combustible y modalidad. Gana la foto más reciente por ruta.

    Devuelve las filas que se quedan y las que sobran, para mandarlas a cuarentena como duplicadas.
    """
    llave = ["fecha", "ubicacion", "combustible", "modalidad"]
    ordenado = validas.sort_values(llave + ["foto_origen"], ascending=[True, True, True, True, False])
    repetida = ordenado.duplicated(subset=llave, keep="first")
    return ordenado[~repetida], ordenado[repetida]


def _precio_de_texto(texto: str) -> float | None:
    """Convierte un texto de OCR como `28.59`, `28,59` o `2859` en precio. None si no parece precio."""
    limpio = texto.strip().replace(",", ".").replace(" ", "")
    if re.fullmatch(r"\d{2}\.\d{2}", limpio):
        return float(limpio)
    if re.fullmatch(r"\d{4}", limpio):
        return float(limpio[:2] + "." + limpio[2:])
    return None


def precios_desde_ocr(cajas: list[dict]) -> dict:
    """Línea base con OCR: a cada etiqueta de combustible le asigna el precio más cercano que esté encima.

    `cajas` es la salida del OCR: una lista de `{"texto": str, "caja": [x0, y0, x1, y1]}`.
    Devuelve un precio por combustible del catálogo, o None si no se encontró.
    """
    etiquetas = {}
    for caja in cajas:
        texto = caja["texto"].lower()
        for combustible in COMBUSTIBLES:
            if combustible in texto and combustible not in etiquetas:
                etiquetas[combustible] = caja["caja"]
    numeros = [(p, c["caja"]) for c in cajas if (p := _precio_de_texto(c["texto"])) is not None]

    resultado = dict.fromkeys(COMBUSTIBLES)
    for combustible, (x0, y0, x1, _) in etiquetas.items():
        ancho = x1 - x0
        candidatos = [
            (y0 - cy1, precio) for precio, (cx0, _, cx1, cy1) in numeros
            if cy1 <= y0 and x0 - ancho <= (cx0 + cx1) / 2 <= x1 + ancho
        ]
        if candidatos:
            resultado[combustible] = min(candidatos)[1]
    return resultado


def exactitud(extraido: pd.DataFrame, revision: pd.DataFrame) -> pd.DataFrame:
    """Compara los precios extraídos contra la revisión manual.

    `extraido`: `archivo`, `combustible` y `precio_q_galon`, con las filas válidas de plata.
    `revision`: una fila por foto con `archivo` y una columna por combustible con el precio real, vacío si no se ve.
    Devuelve una fila por foto y combustible visible, con lo extraído y si es correcto con tolerancia de un centavo.
    """
    real = revision.melt(id_vars="archivo", value_vars=list(COMBUSTIBLES), var_name="combustible",
                         value_name="precio_real").dropna(subset=["precio_real"])
    unido = real.merge(extraido[["archivo", "combustible", "precio_q_galon"]], on=["archivo", "combustible"], how="left")
    unido["correcto"] = (unido["precio_q_galon"].astype(float) - unido["precio_real"].astype(float)).abs() <= 0.011
    return unido
