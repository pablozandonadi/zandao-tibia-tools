"""Zandao Tibia Tools: calculadora de embuimentos, organizador de prints e controle do macro.

Interface em HTML/CSS/JS (pasta web/) dentro de uma janela nativa via PyWebView,
no mesmo esquema do Zandonadi Radar.  Rode com: python zandao_tibia_tools.py
"""

import os
import sys

# Sem console (PyInstaller --windowed) stdout/stderr vêm como None e
# qualquer print/log de biblioteca quebraria.
if getattr(sys, "frozen", False):
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")

import webview

from web_api import API

# web/ e icon.ico: no .exe ficam dentro do pacote (sys._MEIPASS); no código-fonte, ao lado deste arquivo.
if getattr(sys, "frozen", False):
    PASTA_RECURSOS = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
else:
    PASTA_RECURSOS = os.path.dirname(os.path.abspath(__file__))

if sys.platform == "win32":
    # Sem isso a barra de tarefas mostra o ícone do Python em vez do ícone do app.
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ZandaoTibiaTools.App")
    except Exception:
        pass


def main():
    api = API()
    janela = webview.create_window(
        "Zandao Tibia Tools",
        os.path.join(PASTA_RECURSOS, "web", "index.html"),
        js_api=api,
        width=1320,
        height=840,
        min_size=(420, 420),  # pequena o bastante para ficar num canto, por cima do Tibia
        background_color="#14171c",
    )
    api._window = janela
    webview.start(icon=os.path.join(PASTA_RECURSOS, "icon.ico"))


if __name__ == "__main__":
    main()
