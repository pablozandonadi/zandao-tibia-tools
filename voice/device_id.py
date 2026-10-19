import os, threading, uuid
from pathlib import Path

_lock = threading.Lock()


def carregar(pasta):
    """ID anônimo da instalação (UUID v4 em texto puro); criado na primeira chamada."""
    arquivo = Path(pasta) / 'voice-device.id'
    with _lock:
        try:
            texto = arquivo.read_text(encoding='ascii').strip()
            if str(uuid.UUID(texto, version=4)) == texto:
                return texto
        except (OSError, ValueError, UnicodeError):
            pass
        novo = str(uuid.uuid4())
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        tmp = arquivo.with_name(arquivo.name + '.tmp')
        tmp.write_text(novo, encoding='ascii')
        os.replace(tmp, arquivo)
        return novo
