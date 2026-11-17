"""Sirve la presentación en http://localhost:8080 y reenvía /api/* a la API del Droplet.

La API no envía encabezados CORS, así que una página abierta desde otro origen no puede
consultarla. Este servidor resuelve eso sin tocar la API: la página pide /api/health y
el servidor lo reenvía a http://157.230.171.204:8001/health.

Uso, desde la raíz del repo y sin dependencias externas:

    python presentacion/servir.py            # puerto 8080
    python presentacion/servir.py 9000       # otro puerto
"""

import http.server
import socketserver
import sys
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

API = "http://157.230.171.204:8001"
CARPETA = Path(__file__).resolve().parent


class Manejador(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(CARPETA), **kwargs)

    def do_GET(self):
        if self.path.startswith("/api/"):
            self.reenviar()
        else:
            super().do_GET()

    def reenviar(self):
        destino = API + self.path[len("/api"):]
        try:
            with urllib.request.urlopen(destino, timeout=5) as r:
                cuerpo = r.read()
                self.send_response(r.status)
                self.send_header("Content-Type", r.headers.get("Content-Type", "application/json"))
        except urllib.error.HTTPError as e:
            cuerpo = e.read()
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
        except Exception as e:  # sin red o API caída: la página usa el respaldo
            cuerpo = f'{{"error": "{type(e).__name__}"}}'.encode()
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def end_headers(self):
        if not self.path.startswith("/api/"):
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def log_message(self, formato, *args):
        if self.path.startswith("/api/"):
            sys.stderr.write("api  %s\n" % (formato % args))


class Servidor(socketserver.ThreadingMixIn, http.server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    PUERTO = next((int(a) for a in sys.argv[1:] if a.isdigit()), 8080)
    with Servidor(("127.0.0.1", PUERTO), Manejador) as servidor:
        url = f"http://localhost:{PUERTO}/"
        print(f"Presentación en {url}  ·  vista del presentador: tecla P  ·  Ctrl+C para salir")
        if "--sin-navegador" not in sys.argv:
            webbrowser.open(url)
        try:
            servidor.serve_forever()
        except KeyboardInterrupt:
            pass
