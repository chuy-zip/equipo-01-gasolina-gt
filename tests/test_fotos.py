import datetime as dt
import re

import pandas as pd
import pytest

from gas_price import fotos

HOY = dt.date(2026, 11, 14)


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


def test_fecha_de_exif():
    assert fotos.fecha_de_exif("2026:11:10 19:05:33") == dt.date(2026, 11, 10)
    assert fotos.fecha_de_exif(None) is None
    assert fotos.fecha_de_exif("basura") is None


def test_parsea_json_dentro_de_bloque_de_codigo():
    texto = '```json\n{"venta_q": 100.00, "galones": 3.498, "precios": {"diesel": 27.79, "regular": "28,59", "super": null}}\n```'
    lectura = fotos.parsear_lectura(texto)
    assert lectura["venta_q"] == 100.0
    assert lectura["precios"] == {"diesel": 27.79, "regular": 28.59, "super": None, "v_power": None}


@pytest.mark.parametrize("texto", [None, "", "no pude leer", "{malo", "[1, 2]"])
def test_lectura_invalida(texto):
    assert fotos.parsear_lectura(texto) is None


def test_precio_despachado():
    assert fotos.precio_despachado(100.0, 3.498) == 28.59
    assert fotos.precio_despachado(None, 3.4) is None
    assert fotos.precio_despachado(100.0, 0) is None


def test_combustible_despachado_necesita_una_sola_coincidencia():
    precios = {"diesel": 27.79, "regular": 28.59, "super": 29.59, "v_power": 30.09}
    assert fotos.combustible_despachado(28.59, precios) == "regular"
    assert fotos.combustible_despachado(28.64, precios) == "regular"
    assert fotos.combustible_despachado(25.00, precios) is None
    assert fotos.combustible_despachado(28.99, {"diesel": 28.99, "super": 28.99}) is None


def test_filas_usa_el_precio_calculado_para_lo_despachado():
    lectura = {"venta_q": 200.0, "galones": 6.062,
               "precios": {"diesel": 31.23, "regular": None, "super": 32.94, "v_power": None}}
    filas = {f["combustible"]: f["precio_q_galon"] for f in fotos.filas_de_lectura(lectura)}
    assert filas == {"diesel": 31.23, "regular": None, "super": 32.99}


def test_filas_sin_coincidencia_deja_una_fila_sin_combustible():
    lectura = {"venta_q": 190.02, "galones": 5.691, "precios": dict.fromkeys(fotos.VENTANAS)}
    filas = fotos.filas_de_lectura(lectura)
    assert {"combustible": None, "precio_q_galon": 33.39, "motivo_previo": None} in filas
    assert [f["combustible"] for f in filas if f["combustible"]] == ["diesel", "regular", "super"]


def test_filas_incluye_v_power_solo_si_se_leyo():
    lectura = {"venta_q": None, "galones": None,
               "precios": {"diesel": 27.79, "regular": 28.59, "super": 29.59, "v_power": 30.09}}
    assert "v_power" in [f["combustible"] for f in fotos.filas_de_lectura(lectura)]


def test_lectura_fallida_es_una_fila():
    assert fotos.filas_de_lectura(None) == [{"combustible": None, "precio_q_galon": None,
                                             "motivo_previo": "lectura_fallida"}]


@pytest.mark.parametrize(
    "combustible, precio, fecha, referencia, motivo",
    [
        ("regular", 28.59, dt.date(2026, 11, 10), 28.0, None),
        ("regular", 28.59, dt.date(2026, 11, 10), None, None),
        (None, 28.59, dt.date(2026, 11, 10), None, "combustible_no_identificado"),
        ("v_power", 30.09, dt.date(2026, 11, 10), None, "combustible_fuera_de_catalogo"),
        ("super", None, dt.date(2026, 11, 10), None, "precio_no_leido"),
        ("diesel", 2.119, dt.date(2026, 11, 10), None, "precio_fuera_de_rango"),
        ("diesel", 280.0, dt.date(2026, 11, 10), None, "precio_fuera_de_rango"),
        ("super", 30.0, None, None, "fecha_nula"),
        ("super", 30.0, dt.date(2026, 12, 1), None, "fecha_futura"),
        ("diesel", 21.44, dt.date(2026, 11, 10), 27.5, "desviado_de_referencia"),
    ],
)
def test_reglas_de_calidad(combustible, precio, fecha, referencia, motivo):
    assert fotos.motivo_rechazo(combustible, precio, fecha, referencia, HOY) == motivo
    assert motivo is None or motivo in fotos.MOTIVOS


def test_motivo_previo_gana():
    assert fotos.motivo_rechazo(None, None, None, None, HOY, "lectura_fallida") == "lectura_fallida"


def test_referencia_toma_el_ultimo_precio_oficial_vigente():
    oficiales = pd.DataFrame({
        "fecha": [dt.date(2026, 11, 3), dt.date(2026, 11, 10), dt.date(2026, 11, 3)],
        "combustible": ["super", "super", "diesel"],
        "precio_q_galon": [32.0, 32.5, 41.0],
    })
    filas = pd.DataFrame({
        "fecha": [dt.date(2026, 11, 12), dt.date(2026, 11, 5), dt.date(2026, 11, 12), None, dt.date(2026, 11, 12)],
        "combustible": ["super", "super", "diesel", "super", "v_power"],
    })
    resultado = fotos.agregar_referencia(filas, oficiales)
    assert resultado["referencia"].tolist() == [32.5, 32.0, 41.0, None, None]


def test_separar_duplicados_deja_la_foto_mas_reciente():
    validas = pd.DataFrame({
        "fecha": [dt.date(2026, 11, 10)] * 3,
        "ubicacion": ["Mixco, Guatemala"] * 3,
        "combustible": ["super", "super", "diesel"],
        "modalidad": ["no_indicada"] * 3,
        "precio_q_galon": [32.99, 32.99, 41.0],
        "foto_origen": ["s3://b/IMG_1.HEIC", "s3://b/IMG_2.HEIC", "s3://b/IMG_1.HEIC"],
    })
    quedan, sobran = fotos.separar_duplicados(validas)
    assert len(quedan) == 2 and len(sobran) == 1
    assert sobran.iloc[0]["foto_origen"] == "s3://b/IMG_1.HEIC"


def test_exactitud_compara_con_tolerancia_de_un_centavo():
    extraido = pd.DataFrame({"archivo": ["A", "A", "B"], "combustible": ["super", "diesel", "super"],
                             "precio_q_galon": [32.99, 21.44, 30.0]})
    revision = pd.DataFrame({"archivo": ["A", "B"], "super": [32.99, 30.49], "regular": [None, None],
                             "diesel": [27.44, None]})
    resultado = fotos.exactitud(extraido, revision)
    assert len(resultado) == 3
    assert resultado["correcto"].sum() == 1
