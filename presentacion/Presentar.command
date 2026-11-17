#!/bin/bash
# Doble clic en macOS para abrir la presentación. Cierra esta ventana para apagarla.
cd "$(dirname "$0")"
exec python3 servir.py
