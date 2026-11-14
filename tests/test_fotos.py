import re

import pytest

from gas_price import fotos


@pytest.mark.parametrize("ruta", ["s3://b/img/IMG_1.HEIC", "s3://b/IMG_3605.JPG", "a/b.jpeg", "x.png"])
def test_reconoce_imagenes(ruta):
    assert fotos.es_imagen(ruta)
    assert re.search(fotos.regex_imagenes(), ruta)


@pytest.mark.parametrize("ruta", ["s3://b/notas.txt", "s3://b/.DS_Store", "s3://b/sin_extension"])
def test_ignora_lo_que_no_es_imagen(ruta):
    assert not fotos.es_imagen(ruta)
    assert not re.search(fotos.regex_imagenes(), ruta)


def test_url_sin_carpeta():
    assert fotos.url_fotos("s3://bucket/raw") == "s3://bucket/raw/"
    assert fotos.url_fotos("s3://bucket/raw/", "") == "s3://bucket/raw/"


def test_url_con_carpeta():
    assert fotos.url_fotos("s3://bucket/", "/fotos/") == "s3://bucket/fotos/"
    assert fotos.url_fotos("s3://bucket", "fotos/2026-11-10") == "s3://bucket/fotos/2026-11-10/"
