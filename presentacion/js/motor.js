/* Motor de la presentación: escala, navegación por pasos, presentador, vista general y modo PDF. */
(function () {
  "use strict";

  /* Quién presenta cada parte. Cambiar aquí si se reparte distinto. */
  const EQUIPO = ["Daniel", "Diego", "Rodrigo", "Nelson", "Chuy", "Joaquín"];

  const params = new URLSearchParams(location.search);
  const MODO_PDF = params.has("pdf");
  const MODO_PRESENTADOR = params.has("presentador");

  const escenario = document.getElementById("escenario");
  const diapos = [...document.querySelectorAll(".diapo")];
  const total = diapos.length;
  const canal = "BroadcastChannel" in window ? new BroadcastChannel("gasolina-gt") : null;

  let actual = -1;
  let paso = 0;
  const pasosDe = (d) => [...d.querySelectorAll(".paso")];

  /* ---------------------------------------------------------------- Montaje */
  function montar() {
    document.getElementById("lista-equipo").textContent = EQUIPO.join(" · ");
    const l2 = document.getElementById("lista-equipo-2");
    if (l2) l2.textContent = EQUIPO.join(" · ");

    diapos.forEach((d, i) => {
      const quien = d.dataset.presenta;
      if (quien && quien !== "Todos" && quien !== "Plan B" && !d.classList.contains("portada")) {
        const f = document.createElement("div");
        f.className = "presenta";
        f.innerHTML = `<span class="avatar">${quien[0]}</span>${quien}`;
        d.appendChild(f);
      }
      d.dataset.n = i + 1;
    });

    // capturas del anexo: imagen si existe, si no un recuadro con el nombre esperado
    document.querySelectorAll("[data-captura]").forEach((c) => {
      const nombre = c.dataset.captura;
      const img = new Image();
      img.alt = c.dataset.pie;
      img.onload = () => { c.innerHTML = ""; c.appendChild(img); agregarPie(c); };
      img.onerror = () => {
        c.innerHTML = `<div class="falta">Captura pendiente<code>capturas/${nombre}</code></div>`;
        agregarPie(c);
      };
      img.src = "capturas/" + nombre;
    });
    function agregarPie(c) {
      const p = document.createElement("div");
      p.className = "pie";
      p.textContent = c.dataset.pie;
      c.appendChild(p);
    }

    // gráficas
    Graficas.historia(document.getElementById("g-historia"));
    Graficas.internacional(document.getElementById("g-internacional"));
    Graficas.pesos(document.getElementById("barras-pesos"));
    Graficas.matriz(document.getElementById("matriz-modelo"), "modelo");
    Graficas.arquitectura(document.getElementById("diagrama-arq"));
    Graficas.dag(document.getElementById("dag-job"));

    // vista general
    const general = document.getElementById("general");
    general.innerHTML = diapos.map((d, i) =>
      `<button data-ir="${i}"><small>${String(i + 1).padStart(2, "0")} · ${d.dataset.presenta || ""}</small>${d.dataset.titulo}</button>`
    ).join("");
    general.addEventListener("click", (e) => {
      const b = e.target.closest("[data-ir]");
      if (b) { alternarGeneral(false); ir(+b.dataset.ir, 0); }
    });
  }

  /* ------------------------------------------------------------------ Escala */
  function escalar() {
    if (MODO_PDF) return;
    let ancho = innerWidth, alto = innerHeight;
    if (MODO_PRESENTADOR) { ancho = innerWidth * 0.64; alto = innerHeight * 0.7; }
    const s = Math.min(ancho / 1920, alto / 1080);
    escenario.style.transform = `translate(-50%, -50%) scale(${s})`;
  }

  /* -------------------------------------------------------------- Navegación */
  function ir(n, p = 0, desdeCanal = false) {
    n = Math.max(0, Math.min(total - 1, n));
    const cambio = n !== actual;
    if (cambio) {
      diapos.forEach((d, i) => {
        d.classList.toggle("activa", i === n);
        d.classList.toggle("antes", i < n);
        d.classList.toggle("despues", i > n);
      });
      actual = n;
      alActivar(diapos[n]);
    }
    const pasos = pasosDe(diapos[n]);
    paso = p === "todos" ? pasos.length : Math.max(0, Math.min(pasos.length, p));
    pasos.forEach((el, i) => el.classList.toggle("visible", i < paso));
    alPaso(diapos[n]);

    document.getElementById("barra-progreso").style.setProperty("--p", `${((n + 1) / total) * 100}%`);
    document.getElementById("contador").textContent = `${n + 1} / ${total}`;
    document.querySelectorAll("#general [data-ir]").forEach((b) => b.classList.toggle("actual", +b.dataset.ir === n));
    history.replaceState(null, "", `#${n + 1}${paso ? "." + paso : ""}`);
    if (canal && !desdeCanal) canal.postMessage({ n, paso });
    if (MODO_PRESENTADOR) pintarPresentador();
  }
  function siguiente() {
    const pasos = pasosDe(diapos[actual]);
    if (paso < pasos.length) ir(actual, paso + 1);
    else if (actual < total - 1) ir(actual + 1, 0);
  }
  function anterior() {
    if (paso > 0) ir(actual, paso - 1);
    else if (actual > 0) ir(actual - 1, "todos");
  }

  /* --------------------------------------------- Efectos al entrar a una diapo */
  function alActivar(d) {
    // auroras con los colores de la diapositiva
    const colores = (d.dataset.aurora || "").split(",");
    const fondo = document.querySelector(".fondo");
    ["--a1", "--a2", "--a3"].forEach((v, i) => colores[i] && fondo.style.setProperty(v, colores[i]));

    // reiniciar trazos de las gráficas para que se dibujen de nuevo
    d.querySelectorAll(".trazo").forEach((p) => { p.style.animation = "none"; p.getBBox(); p.style.animation = ""; });

    contar(d);
    if (d.querySelector("#dag-job")) Graficas.correrDag(d.querySelector("#dag-job"));
    if (d.querySelector("#terminal-health")) API.terminal(d.querySelector("#terminal-health"));
    if (d.querySelector("#tarjetas-prediccion") || d.querySelector("#terminal-health")) API.cargar();
  }
  function alPaso(d) {
    const arq = d.querySelector("#diagrama-arq");
    if (arq) Graficas.actualizarArquitectura(arq);
  }

  /* Números que cuentan hasta su valor */
  function contar(d) {
    d.querySelectorAll("[data-cuenta]").forEach((el) => {
      const fin = parseFloat(el.dataset.cuenta);
      const dec = +(el.dataset.dec || 0);
      if (MODO_PDF) { el.textContent = fin.toFixed(dec); return; }
      const dur = 1600, t0 = performance.now() + 350;
      const paso = (t) => {
        const x = Math.min(1, Math.max(0, (t - t0) / dur));
        const e = 1 - Math.pow(1 - x, 4);
        el.textContent = (fin * e).toFixed(dec);
        if (x < 1) requestAnimationFrame(paso);
      };
      requestAnimationFrame(paso);
    });
  }

  /* ---------------------------------------------------------------- Entradas */
  function teclado(e) {
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    const k = e.key;
    if (["ArrowRight", "ArrowDown", "PageDown", " ", "Enter"].includes(k)) { e.preventDefault(); siguiente(); }
    else if (["ArrowLeft", "ArrowUp", "PageUp", "Backspace"].includes(k)) { e.preventDefault(); anterior(); }
    else if (k === "Home") ir(0, 0);
    else if (k === "End") ir(total - 1, 0);
    else if (k === "f" || k === "F") pantallaCompleta();
    else if (k === "o" || k === "O") alternarGeneral();
    else if (k === "Escape") { alternarGeneral(false); alternarAyuda(false); }
    else if (k === "?" || k === "h") alternarAyuda();
    else if (k === "p" || k === "P") abrirPresentador();
    else if (k === "r" || k === "R") API.cargar();
    else if (/^[0-9]$/.test(k)) {
      // dos dígitos seguidos saltan a esa diapositiva
      clearTimeout(teclado.t);
      teclado.buf = (teclado.buf || "") + k;
      teclado.t = setTimeout(() => { ir(+teclado.buf - 1, 0); teclado.buf = ""; }, 450);
    }
  }
  function pantallaCompleta() {
    if (document.fullscreenElement) document.exitFullscreen();
    else document.documentElement.requestFullscreen().catch(() => {});
  }
  function alternarGeneral(forzar) {
    const g = document.getElementById("general");
    g.classList.toggle("abierta", forzar);
  }
  function alternarAyuda(forzar) {
    document.getElementById("ayuda").classList.toggle("abierta", forzar);
  }
  function abrirPresentador() {
    const url = location.pathname + "?presentador" + location.hash;
    window.open(url, "presentador", "width=1400,height=860");
  }

  // gestos táctiles
  let x0 = null;
  addEventListener("touchstart", (e) => { x0 = e.touches[0].clientX; }, { passive: true });
  addEventListener("touchend", (e) => {
    if (x0 == null) return;
    const dx = e.changedTouches[0].clientX - x0;
    if (Math.abs(dx) > 50) (dx < 0 ? siguiente : anterior)();
    x0 = null;
  });

  // la interfaz aparece al mover el ratón y se oculta sola
  let ocultar;
  addEventListener("mousemove", (e) => {
    document.body.classList.add("mostrar-hud");
    clearTimeout(ocultar);
    ocultar = setTimeout(() => document.body.classList.remove("mostrar-hud"), 2200);
    brillo(e);
  });

  // brillo especular del vidrio que sigue al puntero
  let pendiente = null;
  function brillo(e) {
    if (pendiente) return;
    pendiente = requestAnimationFrame(() => {
      pendiente = null;
      const d = diapos[actual];
      if (!d) return;
      d.querySelectorAll(".vidrio").forEach((v) => {
        const r = v.getBoundingClientRect();
        v.style.setProperty("--mx", `${((e.clientX - r.left) / r.width) * 100}%`);
        v.style.setProperty("--my", `${((e.clientY - r.top) / r.height) * 100}%`);
      });
    });
  }

  /* ----------------------------------------------------------- Presentador */
  let inicioReloj = null;
  function montarPresentador() {
    document.body.classList.add("modo-presentador");
    const panel = document.createElement("aside");
    panel.className = "panel-presentador";
    panel.innerHTML = `
      <div class="pp-cab">
        <div><div class="pp-etq">Presenta</div><div class="pp-quien" id="pp-quien"></div></div>
        <div style="text-align:right"><div class="pp-etq">Tiempo</div><div class="pp-reloj" id="pp-reloj">00:00</div></div>
      </div>
      <div class="pp-etq">Notas</div>
      <div class="pp-notas" id="pp-notas"></div>
      <div class="pp-pie">
        <div><div class="pp-etq">Sigue</div><div id="pp-sigue" class="pp-sigue"></div></div>
        <button id="pp-reiniciar">Reiniciar reloj</button>
      </div>`;
    document.body.appendChild(panel);
    document.getElementById("pp-reiniciar").onclick = () => { inicioReloj = Date.now(); };
    setInterval(() => {
      if (!inicioReloj) return;
      const s = Math.floor((Date.now() - inicioReloj) / 1000);
      const el = document.getElementById("pp-reloj");
      el.textContent = `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
      el.classList.toggle("tarde", s > 600);
    }, 500);
  }
  function pintarPresentador() {
    const d = diapos[actual];
    if (!inicioReloj && actual > 0) inicioReloj = Date.now();
    const notas = d.querySelector(".notas");
    document.getElementById("pp-quien").textContent = d.dataset.presenta || "";
    document.getElementById("pp-notas").innerHTML = notas
      ? notas.innerHTML.trim().split(/\n\s*/).map((l) => `<p>${l}</p>`).join("")
      : "";
    const pasos = pasosDe(d).length;
    const sig = paso < pasos ? `Paso ${paso + 1} de ${pasos} en esta diapositiva` : diapos[actual + 1] ? `${actual + 2}. ${diapos[actual + 1].dataset.titulo} · ${diapos[actual + 1].dataset.presenta}` : "Fin";
    document.getElementById("pp-sigue").textContent = sig;
  }

  /* -------------------------------------------------------------- Partículas */
  function particulas() {
    const c = document.getElementById("particulas");
    if (!c || MODO_PDF || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const ctx = c.getContext("2d");
    let W, H, puntos;
    const dpr = Math.min(2, devicePixelRatio || 1);
    function tam() {
      W = c.width = innerWidth * dpr;
      H = c.height = innerHeight * dpr;
      const n = Math.round((innerWidth * innerHeight) / 26000);
      puntos = Array.from({ length: n }, () => ({
        x: Math.random() * W, y: Math.random() * H,
        vx: (Math.random() - 0.5) * 0.18 * dpr, vy: (Math.random() - 0.5) * 0.18 * dpr,
        r: (Math.random() * 1.2 + 0.4) * dpr,
      }));
    }
    tam();
    addEventListener("resize", tam);
    const lim = 150 * dpr;
    (function cuadro() {
      ctx.clearRect(0, 0, W, H);
      for (const p of puntos) {
        p.x += p.vx; p.y += p.vy;
        if (p.x < 0 || p.x > W) p.vx *= -1;
        if (p.y < 0 || p.y > H) p.vy *= -1;
      }
      for (let i = 0; i < puntos.length; i++) {
        const a = puntos[i];
        for (let j = i + 1; j < puntos.length; j++) {
          const b = puntos[j];
          const dx = a.x - b.x, dy = a.y - b.y;
          const dist = dx * dx + dy * dy;
          if (dist < lim * lim) {
            ctx.strokeStyle = `rgba(140,180,255,${0.08 * (1 - Math.sqrt(dist) / lim)})`;
            ctx.lineWidth = dpr * 0.8;
            ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
          }
        }
        ctx.fillStyle = "rgba(200,220,255,0.35)";
        ctx.beginPath(); ctx.arc(a.x, a.y, a.r, 0, 6.283); ctx.fill();
      }
      requestAnimationFrame(cuadro);
    })();
  }

  /* --------------------------------------------------------------- Modo PDF */
  function prepararPDF() {
    document.body.classList.add("modo-pdf");
    // ?pdf&solo=5 muestra solo esa diapositiva, para revisarla o sacar una imagen
    const solo = +params.get("solo");
    if (solo) diapos.forEach((d, i) => { if (i !== solo - 1) d.remove(); });
    document.querySelectorAll(".diapo").forEach((d) => {
      d.classList.add("activa");
      d.querySelectorAll(".paso").forEach((p) => p.classList.add("visible"));
      contar(d);
    });
    const arq = document.getElementById("diagrama-arq");
    if (arq) Graficas.actualizarArquitectura(arq);
    const dagJob = document.getElementById("dag-job");
    if (dagJob) Graficas.correrDag(dagJob, true);
    const t = document.getElementById("terminal-health");
    API.cargar().then(() => {
      if (t) API.terminal(t);
      setTimeout(() => { document.body.dataset.listo = "1"; }, 3200);
    });
  }

  /* ----------------------------------------------------------------- Inicio */
  function iniciar() {
    montar();
    if (MODO_PDF) { prepararPDF(); return; }
    if (MODO_PRESENTADOR) montarPresentador();
    escalar();
    addEventListener("resize", escalar);
    addEventListener("keydown", teclado);
    document.getElementById("b-sig").onclick = siguiente;
    document.getElementById("b-ant").onclick = anterior;
    document.getElementById("b-general").onclick = () => alternarGeneral();
    document.getElementById("b-pantalla").onclick = pantallaCompleta;
    document.getElementById("b-ayuda").onclick = () => alternarAyuda();
    document.getElementById("ayuda").onclick = () => alternarAyuda(false);
    escenario.addEventListener("click", (e) => {
      if (e.target.closest("a, button, .qr")) return;
      siguiente();
    });
    if (canal) canal.onmessage = (e) => ir(e.data.n, e.data.paso, true);

    const desdeHash = () => {
      const [n, p] = (location.hash.slice(1) || "1").split(".");
      const destino = (+n || 1) - 1;
      if (destino !== actual || (+p || 0) !== paso) ir(destino, +p || 0);
    };
    addEventListener("hashchange", desdeHash);
    desdeHash();
    particulas();
    API.cargar();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", iniciar);
  else iniciar();
})();
