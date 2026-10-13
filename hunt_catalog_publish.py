"""Prepara apenas dados públicos validados para a branch de catálogo."""
import argparse
import hashlib
import json
from pathlib import Path
from hunt_catalog_core import validate_snapshot


def prepare(snapshot,state,output):
    raw=Path(snapshot).read_bytes();data=validate_snapshot(json.loads(raw));out=Path(output)
    out.mkdir(parents=True,exist_ok=True);(out/'state').mkdir(exist_ok=True)
    (out/'catalog.json').write_bytes(raw)
    (out/'catalog.json.sha256').write_text(hashlib.sha256(raw).hexdigest(),encoding='ascii')
    # Records come exclusively from the validated/sanitized snapshot, never raw collector checkpoints.
    (out/'state/records.json').write_text(json.dumps(data['records'],ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    for name in ('wiki.json','br-index.json','index.json','failed.json'):
        path=Path(state)/name
        if not path.exists():continue
        obj=json.loads(path.read_text(encoding='utf-8'))
        # Reuse the same recursive ban on player fields in every persisted checkpoint.
        validate_snapshot({'schema':data['schema'],'places':data['places'],'records':{},'metadata':obj})
        (out/'state'/name).write_text(json.dumps(obj,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    (out/'README.md').write_text('Dados públicos do catálogo de hunts do Zandao Tibia Tools.\n\nFontes: Tibia Wiki BR, TibiaWiki EN e sessões públicas de hunt-analyser.com. Contém fatos estruturados; não contém nomes de jogadores, títulos livres, HTML ou dados pessoais do aplicativo.\n\nAbates são exatos por sessão; composições e danos agregados são amostras observadas. Registros ambíguos não entram nos perfis.\n',encoding='utf-8')
    return data['metadata']

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--snapshot',required=True);p.add_argument('--state',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    print(json.dumps(prepare(a.snapshot,a.state,a.output),ensure_ascii=False))
