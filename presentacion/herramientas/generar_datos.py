"""Genera presentacion/datos/datos.js con las series y métricas reales que usan las diapositivas.

Uso, desde la raíz del repo con el paquete instalado (pip install -e .):

    python presentacion/herramientas/generar_datos.py
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix

from gas_price import eia, features, mem, modelo

RAIZ = Path(__file__).resolve().parents[2]
DATOS = RAIZ / "data"
SALIDA = RAIZ / "presentacion" / "datos" / "datos.js"
CLASES = ["baja", "se_mantiene", "sube"]


def main() -> None:
    crudo = mem.extraer_crudo(mem.leer_hoja(DATOS / "mem" / "precios_promedio_nacionales_diarios.xlsx"))
    oficiales = mem.a_formato_largo(mem.limpiar(crudo))
    partes = []
    for serie, config in eia.SERIES.items():
        d = eia.leer(DATOS / "eia" / config["archivo"])
        d.insert(1, "serie", serie)
        partes.append(d)
    internacionales = pd.concat(partes, ignore_index=True)

    diarios = features.precios_diarios(oficiales)
    semanales = features.features_modelo(diarios, internacionales)

    # Serie semanal: precio de cierre por combustible
    serie = (
        semanales.pivot_table(index="semana", columns="combustible", values="precio")
        .sort_index()
    )
    serie.index = pd.to_datetime(serie.index)
    serie_out = {
        "semanas": [d.strftime("%Y-%m-%d") for d in serie.index],
        **{c: [None if pd.isna(v) else round(float(v), 2) for v in serie[c]] for c in serie.columns},
    }

    # Precio internacional convertido a quetzales, con la misma lógica que features_modelo
    ancho = diarios.pivot(index="fecha", columns="combustible", values="precio_oficial")
    ancho.index = pd.to_datetime(ancho.index)
    lunes = ancho.resample(features.DIA_DE_CAMBIO).last().index
    lunes = lunes[lunes <= ancho.index.max()]
    tc = diarios.groupby("fecha")["tipo_cambio"].first()
    tc.index = pd.to_datetime(tc.index)
    tc = tc.resample(features.DIA_DE_CAMBIO).last().reindex(lunes)
    intl_usd = features._internacional_antes_del_lunes(internacionales, lunes)
    intl = {}
    for c in ["super", "diesel"]:
        q = (intl_usd[features.SERIE_INTERNACIONAL[c]] * tc)
        q.index = (q.index - pd.Timedelta(days=6))
        q = q.reindex(serie.index)
        intl[c] = [None if pd.isna(v) else round(float(v), 2) for v in q]

    # Distribución de direcciones
    etiquetadas = modelo.con_etiqueta(semanales)
    dist = etiquetadas["etiqueta"].value_counts(normalize=True).round(3).to_dict()

    # Evaluación temporal
    entrenamiento, prueba = modelo.particion_temporal(semanales)
    m = modelo.construir_modelo()
    m.fit(entrenamiento[features.VARIABLES], entrenamiento["etiqueta"])
    pred = m.predict(prueba[features.VARIABLES])
    base = modelo.repetir_semana_pasada(prueba)
    cm_modelo = confusion_matrix(prueba["etiqueta"], pred, labels=CLASES).tolist()
    cm_base = confusion_matrix(prueba["etiqueta"], base, labels=CLASES).tolist()
    _, resultado = modelo.evaluar(semanales)

    # Peso de las variables: norma de los coeficientes por variable
    clf = m.named_steps["clasificador"]
    nombres = list(m.named_steps["preparacion"].get_feature_names_out())
    peso = np.abs(clf.coef_).mean(axis=0)
    pesos = sorted(
        [{"variable": n.split("__")[-1], "peso": round(float(w), 3)} for n, w in zip(nombres, peso)],
        key=lambda x: -x["peso"],
    )

    salida = {
        "serie": serie_out,
        "internacional": intl,
        "distribucion": dist,
        "evaluacion": {k: (round(v, 4) if isinstance(v, float) else str(v)) for k, v in resultado.items()},
        "confusion": {"clases": CLASES, "modelo": cm_modelo, "base": cm_base},
        "pesos": pesos[:10],
        "semanas_totales": int(semanales["semana"].nunique()),
        "columnas": list(semanales.columns),
    }
    SALIDA.write_text("window.DATOS = " + json.dumps(salida, ensure_ascii=False) + ";\n", encoding="utf-8")
    print("Escrito", SALIDA, f"{SALIDA.stat().st_size/1024:.0f} KB")
    print(json.dumps({k: salida[k] for k in ["distribucion", "evaluacion", "confusion", "pesos", "columnas"]}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
