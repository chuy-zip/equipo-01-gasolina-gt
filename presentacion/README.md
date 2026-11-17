# Presentación para el jurado

Presentación web de 23 diapositivas: 21 para exponer y 2 de anexo como plan B. Usa HTML, CSS y JavaScript sin dependencias ni paso de compilación. Las gráficas usan los datos reales del repo y las diapositivas de la demo consultan la API pública en vivo.

| Archivo | Para qué |
|---|---|
| `index.html` | Las diapositivas y las notas de cada presentador |
| `presentacion_jurado.pdf` | Versión PDF para entregar. Se genera con `herramientas/exportar_pdf.py` |
| `servir.py` | Sirve la presentación y reenvía `/api/*` a la API del Droplet |
| `datos/datos.js` | Series del MEM y la EIA, métricas, matriz de confusión y pesos del modelo. Se genera con `herramientas/generar_datos.py` |
| `datos/api_respaldo.js` | Última respuesta guardada de la API. Se usa si no hay conexión |
| `capturas/` | Capturas del anexo. Ver [capturas/README.md](capturas/README.md) |

## Presentar

Solo hace falta Python 3 y Chrome, Edge o Safari. No hay nada que instalar.

**Un comando**, desde la raíz del repo:

```
python3 presentacion/servir.py
```

**O doble clic** en `presentacion/Presentar.command` (macOS) o `presentacion/presentar.bat` (Windows).

Se abre el navegador solo y la terminal muestra:

```
  Presentación:  http://localhost:8080/
  API:           en vivo, modelo versión 4
```

- Si el puerto 8080 está ocupado, usa el siguiente libre.
- Si no hay red, la terminal lo avisa y las diapositivas usan la última respuesta guardada, con un punto amarillo.
- Hace falta este servidor porque la API no envía encabezados CORS. Así el navegador puede consultarla en vivo.
- Para apagarla: `Ctrl+C` o cerrar la ventana.

| Tecla | Acción |
|---|---|
| Flecha derecha, espacio o clic | Siguiente paso o diapositiva |
| Flecha izquierda | Anterior |
| `F` | Pantalla completa |
| `P` | Abre la vista del presentador en otra ventana: notas, cronómetro y siguiente diapositiva. Las dos ventanas se mueven juntas |
| `O` o `Esc` | Vista general para saltar a cualquier diapositiva |
| `R` | Vuelve a consultar la API |
| Dos dígitos | Salta a esa diapositiva, por ejemplo `1` `7` |

Para proyectar: abrir la presentación en la pantalla del proyector con `F` y la vista del presentador (`P`) en la laptop.

## Reparto y tiempos

Cada integrante presenta un solo bloque seguido, en el orden de la portada. 10 minutos de exposición, 5 de demo y 5 de preguntas. Los tiempos objetivo están en las notas de cada diapositiva y suman unos 10 minutos.

| Diapositivas | Presenta | Tema |
|---|---|---|
| 1 a 3 | Daniel | Apertura, el problema y para quién |
| 4 a 6 | Diego | Nuestra respuesta, arquitectura y capas medallón |
| 7 y 8 | Rodrigo | De la foto al dato y reglas de calidad |
| 9 y 10 | Nelson | Revisión manual y fuentes complementarias |
| 11 a 14 | Chuy | Modelo, variables, resultados y limitaciones |
| 15 a 18 | Joaquín | Operación automática, API y demo en vivo |
| 19 a 21 | Sergio | Lecciones, siguientes pasos y cierre |
| 22 y 23 | | Anexo: capturas de respaldo |

El reparto se cambia en `js/motor.js`, en la constante `EQUIPO`, y en el atributo `data-presenta` de cada diapositiva.

## Actualizar

Después de cada corrida del job y del despliegue de la API:

```
python presentacion/herramientas/generar_datos.py
python presentacion/herramientas/exportar_pdf.py
```

`generar_datos.py` necesita el paquete instalado (`pip install -e .`) y red: trae el precio semanal de las fotos de la API, porque las fotos solo están en Databricks. Así entrena con las mismas 17 variables que el `champion` y sus métricas coinciden con `/modelo/metricas`. `exportar_pdf.py` solo necesita Chrome, Chromium o Edge. Cada página del PDF es una imagen exacta de la diapositiva, así que se ve igual en cualquier visor. Tarda cerca de un minuto y medio. Con `--png` también guarda cada diapositiva como imagen en `presentacion/png/`, que no se sube al repo.

Para actualizar el respaldo de la API, volver a guardar las respuestas de `/health`, `/precios/actual`, `/modelo/metricas` y `/prediccion` en `datos/api_respaldo.js`.
