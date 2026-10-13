import unittest
from types import SimpleNamespace
from tray_app import TrayController
class Event(list):
    def __iadd__(self, callback):
        self.append(callback)
        return self
class Window:
    def __init__(self):
        self.events=SimpleNamespace(closing=Event(),closed=Event())
        self.hidden=False
        self.destroyed=False
    def hide(self): self.hidden=True
    def show(self): self.hidden=False
    def restore(self): pass
    def destroy(self): self.destroyed=True
class Icon:
    visible=False
    def stop(self): pass
class TestTray(unittest.TestCase):
    def make(self):
        window=Window()
        tray=TrayController(window,'unused','Tibia Tudo',lambda *_:Icon())
        return window,tray
    def test_close_hides_only_when_tray_ready(self):
        window,tray=self.make();tray.ready.set()
        self.assertFalse(tray.on_closing());self.assertTrue(window.hidden)
        self.assertTrue(tray.icon.visible)
        tray.show();self.assertFalse(window.hidden);self.assertFalse(tray.icon.visible)
    def test_exit_really_closes(self):
        window,tray=self.make();tray.ready.set();tray.exit()
        self.assertTrue(window.destroyed);self.assertTrue(tray.on_closing())
    def test_failure_never_strands_hidden_window(self):
        window,tray=self.make();tray.error=RuntimeError('tray unavailable')
        self.assertTrue(tray.on_closing());self.assertFalse(window.hidden)

    def test_late_tray_failure_restores_window(self):
        import threading
        window,tray=self.make()
        done=threading.Event()
        def failed_run(setup):
            setup(tray.icon)
            window.hide()
            raise RuntimeError('tray crashed')
        tray.icon.run=failed_run
        original_restore=window.restore
        def restored():
            original_restore()
            done.set()
        window.restore=restored
        tray.start()
        self.assertTrue(done.wait(2))
        self.assertFalse(window.hidden)
        self.assertIsNotNone(tray.error)
        self.assertFalse(tray.ready.is_set())
