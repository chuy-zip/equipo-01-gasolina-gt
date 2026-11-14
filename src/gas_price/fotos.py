"""Reglas compartidas para las fotos de precios.

La lectura y la escritura con Spark quedan en los notebooks. Aquí solo va la lógica que se puede probar sin Spark.
"""

from __future__ import annotations

# Formatos de imagen que se cargan a bronce. Las fotos del bucket son HEIC del iPhone y un JPG.
EXTENSIONES_IMAGEN = ("heic", "heif", "jpg", "jpeg", "png", "webp")


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
