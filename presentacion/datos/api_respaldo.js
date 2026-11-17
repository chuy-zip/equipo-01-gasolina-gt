/* Última respuesta guardada de la API pública. Se usa si no hay red o se abre index.html sin servir.py. */
window.API_RESPALDO = {
  "capturado_en": "2026-11-17T18:39:51Z",
  "health": {"estado":"ok","modelo":"equipo_01.gold.modelo_tendencia_precio","version_modelo":"4","datos_exportados_en":"2026-11-17T16:03:24+00:00","semana_mas_reciente":"2026-11-03"},
  "actual": [{"combustible":"diesel","fecha_referencia":"2026-11-10","precio_referencia":41.01,"limite_normal":42.01,"tipo_cambio":7.63846,"regimen_fiscal":"exento","proximo_cambio":"2026-11-16"},{"combustible":"regular","fecha_referencia":"2026-11-10","precio_referencia":29.98,"limite_normal":30.98,"tipo_cambio":7.63846,"regimen_fiscal":"exento","proximo_cambio":"2026-11-16"},{"combustible":"super","fecha_referencia":"2026-11-10","precio_referencia":32.49,"limite_normal":33.49,"tipo_cambio":7.63846,"regimen_fiscal":"exento","proximo_cambio":"2026-11-16"}],
  "metricas": {"version_modelo":"4","entrenado_en":"2026-11-17T02:30:13.682000+00:00","inicio_prueba":"2024-11-05","filas_entrenamiento":1818,"filas_prueba":312,"modelo_balanced_accuracy":0.564110565809595,"modelo_f1_macro":0.5613749664552269,"modelo_direccion_con_movimiento":0.7359550561797753,"linea_base_balanced_accuracy":0.45811521272686323,"linea_base_f1_macro":0.45808905115708715,"linea_base_direccion_con_movimiento":0.64,"supera_linea_base":true},
  "prediccion": {
    "super": {"semana_datos":"2026-11-03","semana":"2026-11-10","combustible":"super","prediccion":"baja","probabilidad":0.9494,"prob_sube":0.0034,"prob_baja":0.9494,"prob_se_mantiene":0.0472,"coincide_con_databricks":true,"version_modelo":"4"},
    "regular": {"semana_datos":"2026-11-03","semana":"2026-11-10","combustible":"regular","prediccion":"baja","probabilidad":0.9259,"prob_sube":0.005,"prob_baja":0.9259,"prob_se_mantiene":0.0691,"coincide_con_databricks":true,"version_modelo":"4"},
    "diesel": {"semana_datos":"2026-11-03","semana":"2026-11-10","combustible":"diesel","prediccion":"baja","probabilidad":0.9205,"prob_sube":0.0033,"prob_baja":0.9205,"prob_se_mantiene":0.0762,"coincide_con_databricks":true,"version_modelo":"4"}
  }
};
