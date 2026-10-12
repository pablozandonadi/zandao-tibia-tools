"""Atualiza o snapshot factual das duas Wikis com consultas em lotes de 50 páginas."""
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlencode
from pathlib import Path
import monstros
import planejador
import creature_sources


def fetch_batch(key,names):
    api=planejador.API if key=='br' else monstros.WIKI
    params=dict(action='query',prop='revisions',rvprop='content|timestamp|ids',rvslots='main',
                titles='|'.join(names),redirects=1,format='json',formatversion=2)
    try:
        q=monstros._get_json(api+'?'+urlencode(params)).get('query',{})
        normalize=lambda n:n.replace('_',' ').lower()
        redirects={normalize(r['from']):normalize(r['to']) for r in q.get('normalized',[])+q.get('redirects',[])}
        pages={normalize(p['title']):p for p in q.get('pages',[])}
        out={}
        for name in names:
            title=normalize(name)
            for _ in range(10):
                target=redirects.get(title)
                if not target or target==title:break
                title=target
            page=pages.get(title,{})
            revisions=page.get('revisions',[])
            if not revisions:continue
            revision=revisions[0];slot=revision.get('slots',{}).get('main',{})
            text=slot.get('content') or slot.get('*')
            if not text:continue
            if key=='br':
                if not monstros._campos_infobox(text,'Infobox_Criatura'):continue
                f=planejador.parse_wiki(text,page['title'])
            else:
                try:f=creature_sources.parse_en(text,page['title'])
                except ValueError:continue
            f['revisao']=revision.get('revid');f['revisao_em']=revision.get('timestamp');out[name]=f
        return key,out,None
    except Exception as e:return key,{},type(e).__name__


def main():
    names=[c['name'] for c in planejador.catalogo_visual()['lista']]
    jobs=[(key,names[i:i+50]) for key in ['br','en'] for i in range(0,len(names),50)]
    sources={'br':{},'en':{}};errors=[]
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures=[pool.submit(fetch_batch,key,batch) for key,batch in jobs]
        for i,future in enumerate(as_completed(futures),1):
            key,data,error=future.result();sources[key].update(data)
            if error:errors.append(f'{key}: {error}')
            if i%5==0 or i==len(jobs):print(f'Lotes {i}/{len(jobs)}; BR {len(sources["br"])}; EN {len(sources["en"])}',flush=True)
    entries={name:creature_sources.merge(name,sources['br'].get(name),sources['en'].get(name),
                [f'{key.upper()}: não foi possível obter uma ficha válida.' for key in ['br','en'] if name not in sources[key]]) for name in names}
    if len(sources['en'])<len(names)//2:raise RuntimeError('Consulta EN incompleta; snapshot anterior preservado.')
    summary={'total':len(entries),'com_faixas':sum(bool(f['ataques']) for f in entries.values()),
             'preenchidas_pela_en':sum(not sources['br'].get(n,{}).get('ataques') and bool(f['ataques']) for n,f in entries.items()),
             'com_divergencias':sum(bool(f['divergencias']) for f in entries.values()),'erros':errors}
    data={'schema':creature_sources.SCHEMA,'gerado_em':time.time(),'fontes':creature_sources.URLS,'resumo':summary,'criaturas':entries}
    path=Path(planejador.BASE_CONHECIMENTO);path.parent.mkdir(exist_ok=True)
    temp=path.with_suffix('.json.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')),encoding='utf-8');temp.replace(path)
    print(json.dumps(summary,ensure_ascii=False),flush=True)
    dworc=entries.get('Dworc Shadowstalker');print('Dworc:',[(a['elemento'],a['min'],a['max']) for a in (dworc or {}).get('ataques',[])],flush=True)

if __name__=='__main__':main()
