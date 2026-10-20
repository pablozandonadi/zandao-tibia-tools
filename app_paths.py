"""Separate immutable resources from per-user, per-channel data."""
import json
import os
from pathlib import Path
import shutil
import sys
from versao import CANAL_APP
PRIVATE_FILES = ('assistente-tibiano.json','assistente-tibiano.json.tmp','assistente-tibiano.json.antes-do-backup','historico_hunts.json','meus_personagens.json','settings.json','preferencias.json',
    'hunt_atual.json','sets.json','rodas.json','audio_timers.json','world_board_registros.json',
    'dados_embuimentos.json','precos_historico.json','sessoes_classificador.json','prints_schedule.json','mirrors.json','mirrors.json.bak',
    'voice-online.json','voice-online.dpapi','voice-online.tmp','voice-online.json.tmp','voice-online.dpapi.tmp','admin-online.dpapi','admin-online.dpapi.tmp',
    'voice-device.id','voice-device.id.tmp','conversao-tc.json','conversao-tc.tmp')
PRIVATE_DIRS = ('sons_usuario',)

def install_dir():
    return Path(sys.executable).parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parent

def resource_dir():
    return Path(getattr(sys,'_MEIPASS',install_dir()))

def data_dir():
    if not getattr(sys,'frozen',False):
        return str(install_dir())
    local = os.environ.get('LOCALAPPDATA')
    if not local:
        raise RuntimeError('LOCALAPPDATA indisponível para guardar os dados do aplicativo.')
    return str(Path(local)/'TibiaTudo'/('beta' if CANAL_APP=='beta' else 'stable'))

def migrate_legacy(source, destination):
    """Copy only missing user files; source remains available for rollback."""
    source,destination=Path(source),Path(destination)
    destination.mkdir(parents=True,exist_ok=True)
    marker=destination/'migracao-v1.json'
    if marker.exists():
        return []
    copied=[]
    for name in PRIVATE_FILES:
        old,new=source/name,destination/name
        if old.is_file() and not old.is_symlink() and not new.exists():
            temp=new.with_suffix(new.suffix+'.migrating')
            try:
                shutil.copy2(old,temp)
                os.replace(temp,new)
                copied.append(name)
            finally:
                if temp.exists(): temp.unlink()
    for name in PRIVATE_DIRS:
        old,new=source/name,destination/name
        if old.is_dir() and not old.is_symlink():
            for item in old.rglob('*'):
                if item.is_file() and not item.is_symlink() and not any(p.is_symlink() for p in item.parents if p!=source):
                    dest=new/item.relative_to(old)
                    if not dest.exists():
                        dest.parent.mkdir(parents=True,exist_ok=True)
                        shutil.copy2(item,dest)
    # No source paths, names of characters or content in diagnostics.
    temp=marker.with_suffix('.tmp')
    temp.write_text(json.dumps({'schema':1,'copied':copied}),encoding='utf-8')
    os.replace(temp,marker)
    return copied

def initialize_data():
    target=data_dir()
    if getattr(sys,'frozen',False):
        migrate_legacy(install_dir(),target)
    return target
