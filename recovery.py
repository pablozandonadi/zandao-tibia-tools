"""Runtime rollback snapshot; never copy or remove user data."""
import json
import os
from pathlib import Path
import shutil
import tempfile
import sys
from app_paths import install_dir, data_dir
from package_tools import PUBLIC_DATA
from versao import VERSAO_APP

def _pasta_recovery(pasta):
    """Cria a pasta das cópias de segurança. Se ela já existe mas o Python não a reconhece como pasta (um atalho
    de pasta/junction para outro disco, usado para liberar o C:), segue o atalho até o destino real e usa ele."""
    try:
        pasta.mkdir(parents=True,exist_ok=True)
        return pasta
    except FileExistsError:
        real=Path(os.path.realpath(pasta))
        if real!=pasta and real.is_dir():return real
        raise

def prepare_snapshot(target_version, source=None, storage=None):
    if source is None and not getattr(sys,'frozen',False):return None
    source=Path(source or install_dir());base=Path(storage or data_dir());storage=_pasta_recovery(base/'recovery')
    exe=source/'ZandaoTibiaTools.exe'
    if not exe.is_file():raise ValueError('Executável atual ausente; atualização bloqueada.')
    items=[exe,source/'_internal']+[source/'data'/name for name in PUBLIC_DATA]
    required=sum(p.stat().st_size for item in items for p in ([item] if item.is_file() else item.rglob('*')) if p.is_file())
    if shutil.disk_usage(storage).free < required*2+32*1024*1024:
        raise ValueError('Espaço insuficiente para preservar a versão anterior.')
    snapshot=Path(tempfile.mkdtemp(prefix='version-',dir=storage))
    try:
        for item in items:
            if not item.exists():continue
            destination=snapshot/item.relative_to(source)
            destination.parent.mkdir(parents=True,exist_ok=True)
            if item.is_dir():shutil.copytree(item,destination)
            else:shutil.copy2(item,destination)
        record={'schema':1,'from_version':VERSAO_APP,'to_version':target_version,'snapshot':snapshot.name,'status':'prepared'}
        (snapshot/'recovery.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
        pending=base/'atualizacao-pendente.json'
        temp=pending.with_suffix('.tmp');temp.write_text(json.dumps(record,indent=2),encoding='utf-8');os.replace(temp,pending)
        return str(snapshot)
    except Exception:
        shutil.rmtree(snapshot,ignore_errors=True)
        raise

def record_startup():
    if not getattr(sys,'frozen',False):return
    pending=Path(data_dir())/'atualizacao-pendente.json'
    if not pending.exists():return
    try:
        record=json.loads(pending.read_text(encoding='utf-8'))
        if not isinstance(record,dict):return
        record['status']='completed' if record.get('to_version','').lstrip('v')==VERSAO_APP else 'interrupted'
        temp=pending.with_suffix('.tmp');temp.write_text(json.dumps(record,indent=2),encoding='utf-8');os.replace(temp,pending)
    except (OSError,ValueError,TypeError):
        return  # Recovery diagnostics cannot prevent opening the app.
