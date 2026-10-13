"""Allowlist and content hashes for distribution, not user data."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import sys
from app_paths import PRIVATE_FILES
PUBLIC_DATA={'imbuements.json','task_items.json','creature_knowledge.json','hunt_catalog.json'}

def sha256(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def validate_resources(source):
    source=Path(source)
    allowed=set(json.loads((source/'packaging-resources.json').read_text(encoding='utf-8'))['files'])
    actual={p.relative_to(source).as_posix() for directory in ['web','sons_padrao'] for p in (source/directory).rglob('*') if p.is_file()}
    actual.add('icon.ico')
    if actual!=allowed:
        raise ValueError('Recursos fora da allowlist: '+', '.join(sorted(actual^allowed)[:10]))

def validate_layout(app,source):
    app,source=Path(app),Path(source)
    allowed_resources=set(json.loads((source/'packaging-resources.json').read_text(encoding='utf-8'))['files'])
    paths=[]
    for path in app.rglob('*'):
        if path.is_symlink():raise ValueError('Link não permitido no pacote')
        if not path.is_file():continue
        name=path.relative_to(app).as_posix()
        if path.name in PRIVATE_FILES or any(part.startswith(('cache_','sons_usuario')) for part in path.relative_to(app).parts):
            raise ValueError('Dados privados/cache no pacote: '+name)
        if '/' not in name and name not in {'ZandaoTibiaTools.exe','sbom.json','package-manifest.json'}:
            raise ValueError('Arquivo não autorizado na raiz: '+name)
        if name.startswith('data/') and name[5:] not in PUBLIC_DATA:
            raise ValueError('Catálogo não autorizado: '+name)
        if name.startswith(('_internal/web/','_internal/sons_padrao/')) and name[len('_internal/'):] not in allowed_resources:
            raise ValueError('Recurso não autorizado: '+name)
        if '/' in name and not name.startswith(('_internal/','data/')):
            raise ValueError('Diretório não autorizado: '+name)
        paths.append((name,path))
    if not (app/'ZandaoTibiaTools.exe').is_file():raise ValueError('Executável ausente')
    return paths

def create_manifest(app,source,version,channel,commit):
    app=Path(app)
    validate_resources(source)
    # Dependency inventory is build metadata, without username or private paths.
    packages=sorted([{'name':d.metadata['Name'],'version':d.version} for d in importlib.metadata.distributions()],key=lambda x:x['name'].lower())
    (app/'sbom.json').write_text(json.dumps({'schema':1,'format':'TibiaTudo dependency inventory','python':platform.python_version(),'packages':packages},indent=2),encoding='utf-8')
    files=[{'path':name,'bytes':path.stat().st_size,'sha256':sha256(path)} for name,path in validate_layout(app,source) if name!='package-manifest.json']
    manifest={'schema':1,'version':version,'channel':channel,'source_sha':commit,'files':sorted(files,key=lambda x:x['path'])}
    (app/'package-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    verify_manifest(app)
    return manifest

def verify_manifest(app):
    app=Path(app)
    manifest=json.loads((app/'package-manifest.json').read_text(encoding='utf-8'))
    for entry in manifest['files']:
        rel=Path(entry['path'])
        if rel.is_absolute() or '..' in rel.parts or '\\' in entry['path'] or ':' in entry['path']:
            raise ValueError('Caminho inválido no manifesto')
        file=app/rel
        if file.is_symlink() or not file.is_file() or file.stat().st_size!=entry['bytes'] or sha256(file)!=entry['sha256']:
            raise ValueError('Arquivo incompleto ou alterado: '+entry['path'])
    return manifest

if __name__=='__main__':
    if sys.argv[1]=='resources':validate_resources(sys.argv[2])
    elif sys.argv[1]=='create':create_manifest(*sys.argv[2:7])
    elif sys.argv[1]=='verify':verify_manifest(sys.argv[2])
    elif sys.argv[1]=='hashes':
        paths=[Path(x) for x in sys.argv[3:]]
        Path(sys.argv[2]).write_text(''.join(sha256(x)+'  '+x.name+'\n' for x in paths),encoding='utf-8')
