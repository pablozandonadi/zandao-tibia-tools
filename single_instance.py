"""One writer per data directory; second launch requests restoration."""
from pathlib import Path
import os
import threading
class InstanceGuard:
    def __init__(self,directory):
        self.directory=Path(directory)
        self.file=None
        self.done=threading.Event()
    def acquire(self):
        self.directory.mkdir(parents=True,exist_ok=True)
        self.file=open(self.directory/'instance.lock','a+b')
        self.file.seek(0)
        if os.path.getsize(self.directory/'instance.lock')==0: self.file.write(b'1');self.file.flush()
        self.file.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(self.file.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self.file,fcntl.LOCK_EX|fcntl.LOCK_NB)
            return True
        except OSError:
            self.file.close();self.file=None
            return False
    def request_activation(self):
        (self.directory/'activate.request').write_text('1',encoding='ascii')
    def watch(self,callback):
        def run():
            request=self.directory/'activate.request'
            while not self.done.wait(.5):
                if request.exists():
                    try: request.unlink();callback()
                    except OSError: pass
        threading.Thread(target=run,daemon=True,name='tibia-instance').start()
    def close(self):
        self.done.set()
        if self.file:
            self.file.close();self.file=None

