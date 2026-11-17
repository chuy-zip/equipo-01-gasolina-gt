"""Exporta la presentación a PDF y, si se pide, cada diapositiva a PNG, con Chrome sin ventana.

Cada página del PDF es una imagen exacta de la diapositiva en 1920 x 1080. Así el vidrio, los
degradados y las gráficas se ven igual en cualquier visor de PDF, incluso en Vista Previa o Acrobat.

No necesita dependencias de Python. Necesita Google Chrome, Chromium o Microsoft Edge instalado.
Levanta su propio servidor con el proxy de la API, así que los datos salen en vivo si hay red.

Uso, desde la raíz del repo:

    python presentacion/herramientas/exportar_pdf.py              # presentacion/presentacion_jurado.pdf
    python presentacion/herramientas/exportar_pdf.py --png        # además, presentacion/png/diapo_01.png ...
    python presentacion/herramientas/exportar_pdf.py --png 5 7    # solo esas diapositivas a PNG, sin PDF
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

CARPETA = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CARPETA))
import servir  # noqa: E402

CANDIDATOS = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "google-chrome", "chromium", "chromium-browser", "microsoft-edge",
]


def buscar_chrome() -> str:
    for c in CANDIDATOS:
        if os.path.isfile(c) or shutil.which(c):
            return c if os.path.isfile(c) else shutil.which(c)
    sys.exit("No encontré Chrome, Chromium ni Edge. Instala uno o agrega su ruta a CANDIDATOS.")


def chrome(binario: str, *args: str) -> None:
    perfil = tempfile.mkdtemp(prefix="chrome-presentacion-")
    try:
        subprocess.run(
            [binario, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
             "--no-default-browser-check", f"--user-data-dir={perfil}", "--force-device-scale-factor=1",
             "--run-all-compositor-stages-before-draw", "--virtual-time-budget=20000", *args],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180,
        )
    finally:
        shutil.rmtree(perfil, ignore_errors=True)


def total_diapositivas() -> int:
    return len(re.findall(r'<section class="diapo', (CARPETA / "index.html").read_text(encoding="utf-8")))


def captura(binario: str, base: str, n: int, destino: Path) -> None:
    chrome(binario, "--window-size=1920,1080", f"--screenshot={destino}", f"{base}&solo={n}")


def main() -> None:
    binario = buscar_chrome()
    puerto = 8765
    srv = servir.Servidor(("127.0.0.1", puerto), servir.Manejador)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://localhost:{puerto}/?pdf"
    total = total_diapositivas()

    pedidas = []
    if "--png" in sys.argv:
        pedidas = [int(a) for a in sys.argv[sys.argv.index("--png") + 1:] if a.isdigit()]
        carpeta_png = CARPETA / "png"
        carpeta_png.mkdir(exist_ok=True)
        for n in pedidas or range(1, total + 1):
            destino = carpeta_png / f"diapo_{n:02d}.png"
            captura(binario, base, n, destino)
            print(f"PNG: {destino}")

    if not pedidas:
        temporal = Path(tempfile.mkdtemp(prefix="pdf-presentacion-"))
        try:
            for n in range(1, total + 1):
                captura(binario, base, n, temporal / f"{n:02d}.jpg")
                print(f"Diapositiva {n} de {total}")
            paginas = "".join(f'<img src="{n:02d}.jpg">' for n in range(1, total + 1))
            (temporal / "pdf.html").write_text(
                "<!doctype html><meta charset='utf-8'><style>@page{size:1920px 1080px;margin:0}"
                "html,body{margin:0;background:#040507}img{display:block;width:1920px;height:1080px;"
                "break-after:page}img:last-child{break-after:auto}</style>" + paginas,
                encoding="utf-8",
            )
            salida = CARPETA / "presentacion_jurado.pdf"
            chrome(binario, "--no-pdf-header-footer", f"--print-to-pdf={salida}", (temporal / "pdf.html").as_uri())
            print(f"PDF: {salida}")
        finally:
            shutil.rmtree(temporal, ignore_errors=True)
    srv.shutdown()


if __name__ == "__main__":
    main()
