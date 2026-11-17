/* Gráficas y diagramas en SVG, dibujados con los datos reales de datos/datos.js. */
(function () {
  "use strict";

  const D = window.DATOS;
  const NS = "http://www.w3.org/2000/svg";
  const COLORES = { super: "#bf5af2", regular: "#30d158", diesel: "#64d2ff" };
  const MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];

  const fecha = (s) => new Date(s + "T12:00:00");
  const fmtMes = (s) => { const d = fecha(s); return `${MESES[d.getMonth()]} ${d.getFullYear()}`; };

  function svg(ancho, alto) {
    const el = document.createElementNS(NS, "svg");
    el.setAttribute("viewBox", `0 0 ${ancho} ${alto}`);
    el.setAttribute("class", "grafica");
    el.setAttribute("preserveAspectRatio", "none");
    return el;
  }
  function nodo(tag, attrs, padre) {
    const el = document.createElementNS(NS, tag);
    for (const k in attrs) el.setAttribute(k, attrs[k]);
    if (padre) padre.appendChild(el);
    return el;
  }
  function texto(padre, x, y, contenido, attrs = {}) {
    const t = nodo("text", { x, y, ...attrs }, padre);
    t.textContent = contenido;
    return t;
  }
  function rutaDe(puntos) {
    let d = "";
    let abierto = false;
    for (const p of puntos) {
      if (p == null) { abierto = false; continue; }
      d += (abierto ? "L" : "M") + p[0].toFixed(1) + "," + p[1].toFixed(1);
      abierto = true;
    }
    return d;
  }
  function prepararTrazos(el) {
    el.querySelectorAll(".trazo").forEach((p) => {
      const largo = Math.ceil(p.getTotalLength());
      p.style.setProperty("--largo", largo);
    });
  }

  /* ------------------------------------------------------------ Historia 2013–2026 */
  function historia(contenedor) {
    const W = contenedor.clientWidth || 1560;
    const H = contenedor.clientHeight || 520;
    const m = { i: 64, d: 170, a: 24, b: 44 };
    const s = D.serie;
    const n = s.semanas.length;
    const yMin = 14, yMax = 50;
    const X = (i) => m.i + (i / (n - 1)) * (W - m.i - m.d);
    const Y = (v) => m.a + (1 - (v - yMin) / (yMax - yMin)) * (H - m.a - m.b);
    const el = svg(W, H);
    el.setAttribute("preserveAspectRatio", "xMidYMid meet");

    const defs = nodo("defs", {}, el);
    const grad = nodo("linearGradient", { id: "area-super", x1: 0, x2: 0, y1: 0, y2: 1 }, defs);
    nodo("stop", { offset: 0, "stop-color": "#bf5af2", "stop-opacity": 0.22 }, grad);
    nodo("stop", { offset: 1, "stop-color": "#bf5af2", "stop-opacity": 0 }, grad);

    for (const v of [20, 30, 40]) {
      nodo("line", { x1: m.i, x2: W - m.d, y1: Y(v), y2: Y(v), class: "guia" }, el);
      texto(el, m.i - 14, Y(v) + 6, `Q${v}`, { "text-anchor": "end" });
    }
    // años
    let anioPrevio = null;
    s.semanas.forEach((w, i) => {
      const a = w.slice(0, 4);
      if (a !== anioPrevio) {
        anioPrevio = a;
        if (+a % 2 === 1 || a === "2026") {
          nodo("line", { x1: X(i), x2: X(i), y1: H - m.b, y2: H - m.b + 8, class: "eje" }, el);
          texto(el, X(i), H - 10, a, { "text-anchor": "middle" });
        }
      }
    });
    nodo("line", { x1: m.i, x2: W - m.d, y1: H - m.b, y2: H - m.b, class: "eje" }, el);

    // banda del subsidio de 2026
    const iDe = (f) => s.semanas.findIndex((w) => w >= f);
    const sub0 = iDe("2026-04-28"), sub1 = iDe("2026-07-07");
    if (sub0 > 0 && sub1 > 0) {
      nodo("rect", { x: X(sub0), y: m.a, width: X(sub1) - X(sub0), height: H - m.a - m.b, fill: "rgba(100,210,255,0.10)", class: "area" }, el);
    }

    // área bajo la súper
    const ptsSuper = s.super.map((v, i) => (v == null ? null : [X(i), Y(v)]));
    const area = rutaDe(ptsSuper) + `L${X(n - 1)},${H - m.b}L${X(0)},${H - m.b}Z`;
    nodo("path", { d: area, fill: "url(#area-super)", class: "area" }, el);

    ["diesel", "regular", "super"].forEach((c, k) => {
      const pts = s[c].map((v, i) => (v == null ? null : [X(i), Y(v)]));
      const p = nodo("path", { d: rutaDe(pts), class: "linea trazo", stroke: COLORES[c] }, el);
      p.style.setProperty("--retardo", `${0.35 + k * 0.25}s`);
      if (c !== "super") p.setAttribute("stroke-opacity", 0.75);
      p.setAttribute("stroke-width", c === "super" ? 3.4 : 2.4);
    });

    // anotaciones
    let iMax = 0;
    s.super.forEach((v, i) => { if (v != null && v > s.super[iMax]) iMax = i; });
    let iCaida = 1, caida = 0;
    for (let i = 1; i < n; i++) {
      const c = s.super[i] - s.super[i - 1];
      if (c < caida) { caida = c; iCaida = i; }
    }
    const notas = nodo("g", { class: "area" }, el);
    const piso = H - m.b;
    marcador(notas, X(iMax), Y(s.super[iMax]), X(iMax) - 120, Y(49), `Máximo Q${s.super[iMax].toFixed(2)}`, fmtMes(s.semanas[iMax]), "end");
    if (sub0 > 0) {
      const xm = (X(sub0) + X(sub1)) / 2;
      texto(notas, xm - 8, piso - 14, "Subsidio", { transform: `rotate(-90 ${xm - 8} ${piso - 14})`, style: "fill: #64d2ff; font-size: 16px; font-weight: 600" });
    }
    marcador(notas, X(iCaida), Y(s.super[iCaida]), X(iCaida) - 120, piso - 60, `−Q${Math.abs(caida).toFixed(2)} en una semana`, "exención de impuestos, oct 2026", "end");
    const ult = n - 1;
    marcador(notas, X(ult), Y(s.super[ult]), X(ult) + 26, Y(s.super[ult]) + 6, `Q${s.super[ult].toFixed(2)}`, "súper hoy", "start", true);

    contenedor.innerHTML = "";
    contenedor.appendChild(el);
    prepararTrazos(el);
  }

  function marcador(padre, x, y, tx, ty, titulo, detalle, ancla, pulso) {
    const g = nodo("g", { class: "marcador" }, padre);
    if (Math.hypot(tx - x, ty - y) > 40) {
      const fin = ancla === "end" ? tx + 10 : tx - 10;
      nodo("path", { d: `M${x},${y} L${fin},${ty - 6}`, stroke: "rgba(255,255,255,0.35)", "stroke-width": 1.5, fill: "none" }, g);
    }
    if (pulso) nodo("circle", { cx: x, cy: y, r: 7, fill: "#bf5af2", class: "pulso" }, g);
    nodo("circle", { cx: x, cy: y, r: 6.5, fill: "#0a0c12", stroke: "#fff", "stroke-width": 2.5 }, g);
    texto(g, tx, ty, titulo, { "text-anchor": ancla, class: "nota-grafica" });
    texto(g, tx, ty + 24, detalle, { "text-anchor": ancla, style: "font-size: 16px" });
  }

  /* ------------------------------------------------- Local contra internacional */
  function internacional(contenedor) {
    const W = contenedor.clientWidth || 1000;
    const H = contenedor.clientHeight || 420;
    const m = { i: 60, d: 20, a: 14, b: 40 };
    const s = D.serie;
    const desde = Math.max(0, s.semanas.length - 156);
    const loc = s.super.slice(desde);
    const intl = (D.internacional && D.internacional.super ? D.internacional.super : []).slice(desde);
    const semanas = s.semanas.slice(desde);
    const n = loc.length;
    const valores = loc.concat(intl).filter((v) => v != null);
    const yMin = Math.floor(Math.min(...valores) / 5) * 5;
    const yMax = Math.ceil(Math.max(...valores) / 5) * 5;
    const X = (i) => m.i + (i / (n - 1)) * (W - m.i - m.d);
    const Y = (v) => m.a + (1 - (v - yMin) / (yMax - yMin)) * (H - m.a - m.b);
    const el = svg(W, H);
    el.setAttribute("preserveAspectRatio", "xMidYMid meet");

    for (let v = yMin; v <= yMax; v += 5) {
      nodo("line", { x1: m.i, x2: W - m.d, y1: Y(v), y2: Y(v), class: "guia" }, el);
      texto(el, m.i - 12, Y(v) + 6, `Q${v}`, { "text-anchor": "end" });
    }
    let anio = null;
    semanas.forEach((w, i) => {
      const a = w.slice(0, 4);
      if (a !== anio) {
        anio = a;
        if (i > 4) texto(el, X(i), H - 8, a, { "text-anchor": "middle" });
      }
    });

    // brecha sombreada
    const arriba = [], abajo = [];
    for (let i = 0; i < n; i++) {
      if (loc[i] == null || intl[i] == null) continue;
      arriba.push([X(i), Y(loc[i])]);
      abajo.unshift([X(i), Y(intl[i])]);
    }
    if (arriba.length) {
      nodo("path", { d: rutaDe(arriba) + rutaDe(abajo).replace(/^M/, "L") + "Z", fill: "rgba(100,210,255,0.10)", class: "area" }, el);
    }
    const pI = nodo("path", { d: rutaDe(intl.map((v, i) => (v == null ? null : [X(i), Y(v)]))), class: "linea trazo", stroke: "#64d2ff", "stroke-width": 2.4 }, el);
    pI.style.setProperty("--retardo", "0.4s");
    const pL = nodo("path", { d: rutaDe(loc.map((v, i) => (v == null ? null : [X(i), Y(v)]))), class: "linea trazo", stroke: "#bf5af2", "stroke-width": 3.2 }, el);
    pL.style.setProperty("--retardo", "0.7s");
    const notas = nodo("g", { class: "area" }, el);
    const mid = Math.round(n * 0.62);
    if (loc[mid] != null && intl[mid] != null) {
      const y0 = Y(loc[mid]), y1 = Y(intl[mid]);
      nodo("line", { x1: X(mid), x2: X(mid), y1: y0 + 6, y2: y1 - 6, stroke: "rgba(255,255,255,0.55)", "stroke-width": 2, "stroke-dasharray": "3 5" }, notas);
      texto(notas, X(mid) + 14, (y0 + y1) / 2 + 6, "brecha", { class: "nota-grafica", style: "fill:rgba(245,245,247,0.8); font-size:18px" });
    }

    contenedor.innerHTML = "";
    contenedor.appendChild(el);
    prepararTrazos(el);
  }

  /* -------------------------------------------------------- Pesos de variables */
  const DESCRIPCION = {
    brecha_vs_8: "local vs. internacional",
    tendencia_8: "precio vs. media de 8 sem.",
    intl_cambio_1: "cambio internacional, sem. pasada",
    intl_cambio_2: "cambio internacional, hace 2 sem.",
    intl_cambio_3: "cambio internacional, hace 3 sem.",
    otro_super_l1: "cambio de la súper",
    otro_regular_l1: "cambio de la regular",
    otro_diesel_l1: "cambio del diésel",
    tipo_cambio_cambio: "cambio del tipo de cambio",
    cambio_l1: "cambio de la semana",
    cambio_l2: "cambio hace 1 semana",
    cambio_l3: "cambio hace 2 semanas",
    cambio_l4: "cambio hace 3 semanas",
    tendencia_4: "precio vs. media de 4 sem.",
    mes: "mes del año",
  };
  function pesos(contenedor) {
    const lista = D.pesos.slice(0, 8);
    const max = lista[0].peso;
    contenedor.innerHTML = lista.map((p, i) => {
      const intl = /^(intl|brecha)/.test(p.variable);
      return `<div class="barra${intl ? " intl" : ""}" style="--i:${i}; --w:${((p.peso / max) * 100).toFixed(1)}%">
        <div class="nombre">${p.variable}<div style="font-family: var(--fuente); font-size: 15px; color: var(--texto-3); margin-top: 2px;">${DESCRIPCION[p.variable] || ""}</div></div>
        <div class="riel"><div class="relleno"></div></div>
        <div class="valor">${p.peso.toFixed(2)}</div>
      </div>`;
    }).join("");
  }

  /* --------------------------------------------------------- Matriz de confusión */
  function matriz(contenedor, cual = "modelo") {
    const m = D.confusion[cual];
    const nombres = { baja: "Baja", se_mantiene: "Se mantiene", sube: "Sube" };
    const max = Math.max(...m.flat());
    let html = `<div></div>` + D.confusion.clases.map((c) => `<div class="cab">${nombres[c]}</div>`).join("");
    let k = 0;
    m.forEach((fila, i) => {
      html += `<div class="lat">${nombres[D.confusion.clases[i]]}</div>`;
      fila.forEach((v, j) => {
        html += `<div class="celda${i === j ? " diag" : ""}" style="--v:${(v / max).toFixed(3)}; --i:${k++}">${v}</div>`;
      });
    });
    contenedor.innerHTML = html;
    if (cual === "base") contenedor.classList.add("base");
  }

  /* --------------------------------------------- Conexiones entre nodos (diagramas) */
  function centro(el) {
    return { x: el.offsetLeft, y: el.offsetTop, w: el.offsetWidth, h: el.offsetHeight };
  }
  function curva(a, b) {
    const A = centro(a), B = centro(b);
    const dx = B.x + B.w / 2 - (A.x + A.w / 2);
    const dy = B.y + B.h / 2 - (A.y + A.h / 2);
    let x1, y1, x2, y2, horizontal;
    if (Math.abs(dx) > Math.abs(dy) * 0.9) {
      horizontal = true;
      x1 = dx > 0 ? A.x + A.w : A.x; y1 = A.y + A.h / 2;
      x2 = dx > 0 ? B.x : B.x + B.w; y2 = B.y + B.h / 2;
    } else {
      horizontal = false;
      x1 = A.x + A.w / 2; y1 = dy > 0 ? A.y + A.h : A.y;
      x2 = B.x + B.w / 2; y2 = dy > 0 ? B.y : B.y + B.h;
    }
    if (horizontal) {
      const c = (x2 - x1) / 2;
      return `M${x1},${y1} C${x1 + c},${y1} ${x2 - c},${y2} ${x2},${y2}`;
    }
    const c = (y2 - y1) / 2;
    return `M${x1},${y1} C${x1},${y1 + c} ${x2},${y2 - c} ${x2},${y2}`;
  }

  const CONEXIONES_ARQ = [
    ["n-fotos", "n-bronce"], ["n-mem", "n-bronce"], ["n-eia", "n-bronce"],
    ["n-bronce", "n-plata"], ["n-plata", "n-oro"], ["n-oro", "n-mlflow"],
    ["n-git", "n-bronce"], ["n-job", "n-plata"],
    ["n-oro", "n-api"], ["n-mlflow", "n-api"], ["n-api", "n-usuario"],
  ];
  function arquitectura(contenedor) {
    const lienzo = contenedor.querySelector("svg.conexiones");
    lienzo.innerHTML = "";
    CONEXIONES_ARQ.forEach(([a, b]) => {
      const A = document.getElementById(a), B = document.getElementById(b);
      if (!A || !B) return;
      const d = curva(A, B);
      const base = nodo("path", { d, "data-a": a, "data-b": b, class: "base" }, lienzo);
      const flujo = nodo("path", { d, "data-a": a, "data-b": b, class: "flujo" }, lienzo);
      base.style.transition = "opacity .6s";
    });
    actualizarArquitectura(contenedor);
  }
  function visible(el) {
    return !el.classList.contains("paso") || el.classList.contains("visible");
  }
  function actualizarArquitectura(contenedor) {
    contenedor.querySelectorAll("svg.conexiones path").forEach((p) => {
      const A = document.getElementById(p.dataset.a), B = document.getElementById(p.dataset.b);
      const on = visible(A) && visible(B);
      if (p.classList.contains("flujo")) p.classList.toggle("on", on);
      else p.style.opacity = on ? 1 : 0;
    });
  }

  /* --------------------------------------------------------------- DAG del job */
  const ARISTAS_JOB = [["10", "21"], ["11", "20"], ["12", "22"], ["20", "30"], ["21", "30"], ["22", "30"], ["30", "40"], ["40", "50"]];
  const ORDEN_JOB = [["10", "11", "12"], ["20", "22"], ["21"], ["30"], ["40"], ["50"]];
  let temporizadoresDag = [];
  function dag(contenedor) {
    const lienzo = contenedor.querySelector("svg");
    lienzo.innerHTML = "";
    const t = (id) => contenedor.querySelector(`[data-t="${id}"]`);
    ARISTAS_JOB.forEach(([a, b]) => {
      nodo("path", { d: curva(t(a), t(b)), "data-a": a, "data-b": b }, lienzo);
    });
  }
  function correrDag(contenedor, instantaneo) {
    temporizadoresDag.forEach(clearTimeout);
    temporizadoresDag = [];
    const tareas = contenedor.querySelectorAll(".tarea");
    const t = (id) => contenedor.querySelector(`[data-t="${id}"]`);
    const aristas = contenedor.querySelectorAll("svg path");
    if (instantaneo) {
      tareas.forEach((x) => { x.classList.remove("corriendo"); x.classList.add("lista"); });
      aristas.forEach((p) => p.classList.add("activa"));
      return;
    }
    tareas.forEach((x) => x.classList.remove("corriendo", "lista"));
    aristas.forEach((p) => p.classList.remove("activa"));
    let tiempo = 900;
    ORDEN_JOB.forEach((grupo) => {
      const inicio = tiempo;
      temporizadoresDag.push(setTimeout(() => grupo.forEach((id) => t(id).classList.add("corriendo")), inicio));
      const fin = inicio + 1100;
      temporizadoresDag.push(setTimeout(() => {
        grupo.forEach((id) => {
          t(id).classList.remove("corriendo");
          t(id).classList.add("lista");
          aristas.forEach((p) => { if (p.dataset.a === id) p.classList.add("activa"); });
        });
      }, fin));
      tiempo = fin + 150;
    });
  }

  window.Graficas = { historia, internacional, pesos, matriz, arquitectura, actualizarArquitectura, dag, correrDag };
})();
