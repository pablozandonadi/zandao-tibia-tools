"""Configuração administrativa; ausência de identidade bloqueia a API protegida."""
import os
from pathlib import Path
from .auth import Verifier
from .domain import Invalid
from .store import Store
from .transport import FakeTransport,BridgeTransport
from .api import create_app

def components():
    state=Path(os.environ['AUTOMATION_STATE_DIR']).resolve();state.mkdir(parents=True,exist_ok=True)
    if os.name!='nt': os.chmod(state,0o700)
    key_path=Path(os.environ['AUTOMATION_KEY_FILE']).resolve()
    if key_path==state or state in key_path.parents: raise Invalid('Guarde a chave fora do diretório de estado.')
    key=key_path.read_bytes().strip()
    # Overrides exclusivos deste processo servidor, antes da primeira consulta.
    import tibia_info
    tibia_info.CACHE_PATH=str(state/'cache_tibia.json')
    store=Store(state/'automation.sqlite',key)
    mode=os.environ.get('AUTOMATION_TRANSPORT','fake')
    if mode=='fake': transport=FakeTransport()
    elif mode=='bridge' and os.environ.get('AUTOMATION_ENABLE_REAL')=='I_ACCEPT_UNOFFICIAL_WHATSAPP':
        token=Path(os.environ['AUTOMATION_BRIDGE_TOKEN_FILE']).read_text().strip()
        transport=BridgeTransport(os.environ.get('AUTOMATION_BRIDGE_URL','http://127.0.0.1:8788'),token)
    else: raise Invalid('Transporte real não autorizado.')
    return store,transport

def application():
    store,transport=components()
    verifier=Verifier(store)
    origins=tuple(x.strip() for x in os.environ.get('AUTOMATION_ORIGINS','').split(',') if x.strip())
    if any(not x.startswith('https://') or x.endswith('/') for x in origins): raise Invalid('Origens devem ser HTTPS exatas, sem barra final.')
    return create_app(store,transport,verifier,origins)
