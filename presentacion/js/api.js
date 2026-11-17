/* Datos en vivo de la API del Droplet, con respaldo guardado si no hay conexión.

   La API no envía encabezados CORS, así que el navegador no puede consultarla
   directo desde otra página. Por eso servir.py publica la presentación y reenvía
   /api/* al Droplet. Si se abre el archivo sin servir.py, se usa el respaldo. */
(function () {
  "use strict";

  const BASE = "http://157.230.171.204:8001";
  const R = window.API_RESPALDO;
  const COMBUSTIBLES = ["super", "regular", "diesel"];
  const NOMBRE = { super: "Súper", regular: "Regular", diesel: "Diésel" };
  const COLOR = { super: "var(--super)", regular: "var(--regular)", diesel: "var(--diesel)" };
  const MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
  const fmtFecha = (s) => { const d = new Date(s + "T12:00:00"); return `${d.getDate()} de ${MESES[d.getMonth()]}`; };

  const estado = { modo: "respaldo", datos: null };

  async function conLimite(url, ms) {
    const ctl = new AbortController();
    const t = setTimeout(() => ctl.abort(), ms);
    try {
      const r = await fetch(url, { signal: ctl.signal, cache: "no-store" });
      if (!r.ok) throw new Error(r.status);
      return await r.json();
    } finally {
      clearTimeout(t);
    }
  }

  async function obtener(ruta) {
    const intentos = [];
    if (location.protocol.startsWith("http")) intentos.push("/api" + ruta);
    intentos.push(BASE + ruta);
    for (const url of intentos) {
      try { return await conLimite(url, 3500); } catch (e) { /* siguiente intento */ }
    }
    throw new Error("sin conexión");
  }

  async function cargar() {
    try {
      const [health, actual, metricas, ...preds] = await Promise.all([
        obtener("/health"),
        obtener("/precios/actual"),
        obtener("/modelo/metricas"),
        ...COMBUSTIBLES.map((c) => obtener("/prediccion?combustible=" + c)),
      ]);
      const prediccion = {};
      COMBUSTIBLES.forEach((c, i) => (prediccion[c] = preds[i]));
      // /precios/actual responde { nota, datos: [...] }
      estado.datos = { health, actual: actual.datos || actual, metricas, prediccion };
      estado.modo = "vivo";
    } catch (e) {
      estado.datos = R;
      estado.modo = "respaldo";
    }
    pintar();
    return estado;
  }

  function pintarEstado() {
    const vivo = estado.modo === "vivo";
    const txt = vivo
      ? "En vivo · 157.230.171.204:8001"
      : `Respaldo guardado · ${new Date(R.capturado_en).toLocaleString("es-GT", { dateStyle: "medium", timeStyle: "short" })}`;
    document.querySelectorAll("#estado-api, [data-estado-api]").forEach((el) => {
      el.classList.toggle("ok", vivo);
      el.classList.toggle("respaldo", !vivo);
      el.querySelector("span").textContent = txt;
    });
  }

  function jsonColor(obj, sangria = "  ") {
    const lineas = Object.entries(obj).map(([k, v]) => {
      let val;
      if (typeof v === "number") val = `<span class="n">${Number.isInteger(v) ? v : v.toFixed(2)}</span>`;
      else if (typeof v === "string") val = `<span class="s">"${v}"</span>`;
      else val = `<span class="p">${JSON.stringify(v)}</span>`;
      return `${sangria}<span class="k">"${k}"</span><span class="p">:</span> ${val}`;
    });
    return `<span class="p">{</span>\n${lineas.join('<span class="p">,</span>\n')}\n<span class="p">}</span>`;
  }

  function pintar() {
    const d = estado.datos;
    pintarEstado();

    // precios de la portada
    d.actual.forEach((fila) => {
      document.querySelectorAll(`[data-api="actual.${fila.combustible}"]`).forEach((el) => {
        el.textContent = fila.precio_referencia.toFixed(2);
      });
    });

    // medidor de la portada: el marcador se ubica según la probabilidad de subir menos la de bajar
    const pm = d.prediccion.super;
    const aguja = document.getElementById("aguja");
    if (aguja) {
      aguja.style.setProperty("--giro", `${((pm.prob_sube - pm.prob_baja) * 86).toFixed(1)}deg`);
      const color = { baja: "var(--regular)", se_mantiene: "#e5e5ea", sube: "var(--sube)" };
      const nombre = { baja: "Baja", se_mantiene: "Igual", sube: "Sube" };
      ["baja", "se_mantiene", "sube"].forEach((c) => {
        document.getElementById(`tramo-${c}`).classList.toggle("activo", c === pm.prediccion);
        document.getElementById(`etq-${c}`).classList.toggle("activo", c === pm.prediccion);
        const p = Math.round(pm[`prob_${c}`] * 100);
        document.getElementById(`p-${c}`).textContent = p < 1 ? "<1" : p;
      });
      const dirEl = document.getElementById("medidor-dir");
      dirEl.textContent = nombre[pm.prediccion];
      dirEl.style.setProperty("--c", color[pm.prediccion]);
      const prob = document.getElementById("medidor-prob");
      prob.dataset.cuenta = Math.round(pm.probabilidad * 100);
      prob.textContent = prob.dataset.cuenta;
    }

    // ejemplo de respuesta en la diapositiva 4
    const ps = d.prediccion.super;
    const ej = document.getElementById("json-ejemplo");
    if (ej) {
      ej.innerHTML = jsonColor({
        semana: ps.semana,
        combustible: ps.combustible,
        prediccion: ps.prediccion,
        probabilidad: Math.round(ps.probabilidad * 100) / 100,
      });
    }

    // tarjetas de predicción
    const cont = document.getElementById("tarjetas-prediccion");
    if (cont) {
      cont.innerHTML = COMBUSTIBLES.map((c, i) => {
        const p = d.prediccion[c];
        const ref = d.actual.find((x) => x.combustible === c);
        const dir = p.prediccion;
        const color = dir === "baja" ? "var(--regular)" : dir === "sube" ? "var(--sube)" : "var(--texto-2)";
        const rot = dir === "baja" ? 90 : dir === "sube" ? -90 : 0;
        const etiqueta = dir === "se_mantiene" ? "Se mantiene" : dir;
        return `<div class="vidrio pred" data-a style="--i:${3 + i}">
          <div class="comb" style="color:${COLOR[c]}"><i></i>${NOMBRE[c]}</div>
          <svg class="flecha-g" viewBox="0 0 140 140" style="color:${color}">
            <circle cx="70" cy="70" r="66" fill="none" stroke="currentColor" stroke-opacity=".25" stroke-width="2"/>
            <circle cx="70" cy="70" r="66" fill="currentColor" fill-opacity=".1"/>
            <g transform="rotate(${rot} 70 70)"><path d="M42 70h56M76 48l22 22-22 22" fill="none" stroke="currentColor" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/></g>
          </svg>
          <div class="dir" style="color:${color}">${etiqueta}</div>
          <div class="prob">${Math.round(p.probabilidad * 100)} % de probabilidad</div>
          <div class="dist" title="Probabilidad de cada clase">
            <span style="--w:${(p.prob_baja * 100).toFixed(1)}%; background: var(--regular)"></span>
            <span style="--w:${(p.prob_se_mantiene * 100).toFixed(1)}%; background: rgba(255,255,255,.45)"></span>
            <span style="--w:${(p.prob_sube * 100).toFixed(1)}%; background: var(--sube)"></span>
          </div>
          <div class="ref"><span>Baja ${Math.round(p.prob_baja * 100)} · Igual ${Math.round(p.prob_se_mantiene * 100)} · Sube ${Math.round(p.prob_sube * 100)}</span><span>Hoy Q${ref ? ref.precio_referencia.toFixed(2) : "—"}</span></div>
        </div>`;
      }).join("");
      const sem = document.getElementById("semana-objetivo");
      if (sem) sem.textContent = fmtFecha(ps.semana);
      const pie = document.getElementById("pie-prediccion");
      if (pie) {
        const ref = d.actual[0];
        pie.textContent = `Con datos hasta la semana del ${fmtFecha(ps.semana_datos)}. Referencia vigente del MEM del ${fmtFecha(ref.fecha_referencia)}; próximo cambio esperado el ${fmtFecha(ref.proximo_cambio)}.`;
      }
    }
    document.dispatchEvent(new CustomEvent("api-lista", { detail: estado }));
  }

  /* Terminal que escribe la consulta a /health */
  let escribiendo = null;
  function terminal(el) {
    if (!el) return;
    clearTimeout(escribiendo);
    const comando = "curl 157.230.171.204:8001/health";
    const h = (estado.datos || R).health;
    const salida = jsonColor({
      estado: h.estado,
      version_modelo: h.version_modelo,
      datos_exportados_en: h.datos_exportados_en.slice(0, 16).replace("T", " "),
      semana_mas_reciente: h.semana_mas_reciente,
    });
    let i = 0;
    const tecla = () => {
      el.innerHTML = `<span class="prompt">equipo-01 $</span> ${comando.slice(0, i)}<span class="cursor"></span>`;
      if (i++ < comando.length) escribiendo = setTimeout(tecla, 28 + Math.random() * 30);
      else escribiendo = setTimeout(() => {
        el.innerHTML = `<span class="prompt">equipo-01 $</span> ${comando}\n<span class="c-regular">HTTP/1.1 200 OK</span>\n${salida}`;
      }, 380);
    };
    tecla();
  }

  window.API = { cargar, terminal, estado };
})();
