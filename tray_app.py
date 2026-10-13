"""Close to tray with an explicit exit path; keep the window if tray fails."""
import threading
class TrayController:
    def __init__(self, window, icon_path, title, icon_factory=None):
        self.window = window
        self.exiting = False
        self.ready = threading.Event()
        self.error = None
        if icon_factory is None:
            import pystray
            from PIL import Image
            self.icon = pystray.Icon('TibiaTudo', Image.open(icon_path), title,
                pystray.Menu(pystray.MenuItem('Abrir Tibia Tudo', self.show, default=True),
                             pystray.MenuItem('Sair', self.exit)))
        else:
            self.icon = icon_factory(self.show, self.exit)
        window.events.closing += self.on_closing
        window.events.closed += self.stop
    def start(self):
        def run():
            try:
                self.icon.run(setup=lambda icon: self.ready.set())
            except Exception as exc:
                self.error = exc
            finally:
                self.ready.clear()
                if not self.exiting:
                    self.error = self.error or RuntimeError("Tray loop stopped")
                    try:
                        self.window.show()
                        self.window.restore()
                    except Exception:
                        pass
        threading.Thread(target=run, name='tibia-tudo-tray', daemon=True).start()
    def on_closing(self):
        if self.exiting:
            return True
        if self.error or not self.ready.wait(1):
            return True  # Never hide a window without a working way to restore it.
        self.icon.visible = True
        self.window.hide()
        return False
    def show(self, *args):
        self.window.show()
        self.window.restore()
        self.icon.visible = False
    def exit(self, *args):
        self.exiting = True
        self.window.destroy()
    def stop(self, *args):
        self.icon.stop()
