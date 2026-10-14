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

from app_paths import initialize_data, data_dir
from single_instance import InstanceGuard
from versao import CANAL_APP, NOME_APP

# web/ e icon.ico: no .exe ficam dentro do pacote (sys._MEIPASS); no código-fonte, ao lado deste arquivo.
if getattr(sys, "frozen", False):
    PASTA_RECURSOS = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
else:
    PASTA_RECURSOS = os.path.dirname(os.path.abspath(__file__))

if sys.platform == "win32":
    # Sem isso a barra de tarefas mostra o ícone do Python em vez do ícone do app.
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ZandaoTibiaTools.Beta" if CANAL_APP == "beta" else "ZandaoTibiaTools.App")
    except Exception:
        pass


def main():
    guard = InstanceGuard(data_dir()) if getattr(sys, "frozen", False) else None
    if guard is not None and not guard.acquire():
        guard.request_activation()
        return
    initialize_data()
    from recovery import record_startup
    record_startup()
    from web_api import API, ler_prefs, TAMANHO_NORMAL, TAMANHO_GADGET
    api = API()
    prefs = ler_prefs()
    modo = prefs.get("modo", "normal")
    tamanho = prefs.get("tamanhos", {}).get(modo, TAMANHO_GADGET if modo == "gadget" else TAMANHO_NORMAL)
    api._modo_janela = modo
    api._trocando_modo = True
    janela = webview.create_window(
        NOME_APP,
        os.path.join(PASTA_RECURSOS, "web", "index.html"),
        js_api=api,
        text_select=True,
        width=tamanho[0],
        height=tamanho[1],
        min_size=(280, 320),  # bem pequena: vira um gadget num canto, por cima do Tibia (com o tamanho da interface menor)
        background_color="#14171c",
    )
    api._window = janela

    restaurada = False
    def restaurar_janela():
        nonlocal restaurada
        if restaurada:
            return
        restaurada = True
        api.janela_tamanho(modo)
        janela.events.resized += api.janela_redimensionada

    janela.events.shown += restaurar_janela
    if guard is not None:
        guard.watch(lambda: (janela.show(), janela.restore()))
    from tray_app import TrayController
    tray = None
    try:
        tray = TrayController(janela, os.path.join(PASTA_RECURSOS, "icon.ico"), NOME_APP)
        tray.start()
        def avisar_rede(message):
            if tray.ready.is_set():
                tray.icon.visible = True
                tray.icon.notify(message, "Tibia Tudo · Rede")
        api._rede.notifier = avisar_rede
    except Exception:
        pass  # If tray setup fails, the X still closes normally.
    if api._rede.config["enabled"]:
        api._rede.start()
    try:
        webview.start(icon=os.path.join(PASTA_RECURSOS, "icon.ico"), private_mode=False,
                      storage_path=os.path.join(data_dir(), "webview_session"))
    finally:
        api._rede.close()
        if tray is not None:
            tray.stop()
        if guard is not None:
            guard.close()


if __name__ == "__main__":
    main()
