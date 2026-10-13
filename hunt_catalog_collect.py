"""Coleta central retomável de páginas públicas. HTML e nomes de jogadores não são persistidos.

python hunt_catalog_collect.py --work-dir <cache temporario> --output data/hunt_catalog.json
Dependência exclusiva do coletor/testes: beautifulsoup4 (não é necessária ao leitor do app).
"""
import argparse
import gzip
import json
import math
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup
import monstros
from hunt_catalog_core import ELEMENTS, aggregate, canonical_creature, ident, key, title_candidates, validate_snapshot, sanitize_records

PUBLIC='https://www.hunt-analyser.com'
WIKIS={'br':'https://www.tibiawiki.com.br','en':'https://tibia.fandom.com'}
ALIASES={
 'Furious Crater':['soulwar crater','cratera soulwar'],
 'Rotten Wasteland':['soulwar rotten','rotten'],
 'Mirrored Nightmare':['soulwar mirrored','mirrored'],
 'Ebb and Flow':['soulwar ebb flow','ebb flow'],
 'Claustrophobic Inferno':['soulwar inferno','claustrophobic'],
 'Roshamuul Prison':['prison','prisao roshamuul'],
 'Upper Roshamuul':['upper rosha','rosha upper'],
 'Lower Roshamuul':['lower rosha','rosha lower'],
 'Summer Court':['summer elves','elves verao'],
 'Winter Court':['winter elves','elves inverno'],
 'Falcon Bastion':['falcon','falcons','falcoes'],
 'Nimmersatt\'s Breeding Ground':['wardragons','wardragon'],
}
for n in range(1,10):ALIASES['Warzone '+str(n)]=['wz'+str(n),'wz '+str(n)]


def atomic_json(path, value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(value,ensure_ascii=False,separators=(',',':')),encoding='utf-8');os.replace(tmp,path)


def read_json(path, default=None):
    try:return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError,ValueError):return {} if default is None else default


class Fetcher:
    def __init__(self, gap=.55):
        self.gap=gap;self.lock=threading.Lock();self.next={}

    def get(self,url):
        host=urllib.parse.urlsplit(url).netloc
        for attempt in range(3):
            with self.lock:
                wait=max(0,self.next.get(host,0)-time.monotonic())
                if wait:time.sleep(wait)
                self.next[host]=time.monotonic()+self.gap
            req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; ZandaoToolsCatalogue/1.0; public-data research)',
                                                    'Accept-Encoding':'gzip','Accept-Language':'en'})
            try:
                with urllib.request.urlopen(req,timeout=35) as r:
                    raw=r.read(12*1024*1024+1)
                    if len(raw)>12*1024*1024:raise ValueError('Resposta muito grande')
                    if r.headers.get('Content-Encoding')=='gzip':raw=gzip.decompress(raw)
                    return raw.decode('utf-8-sig')
            except urllib.error.HTTPError as e:
                if e.code not in (429,500,502,503,504):raise
                pause=min(60,int(e.headers.get('Retry-After','0') or 0) or 2**(attempt+2))
                time.sleep(pause)
            except (OSError,TimeoutError):
                if attempt==2:raise
                time.sleep(2**(attempt+1))
        raise ValueError('Fonte indisponível após tentativas limitadas')


def wiki_url(source,name):
    return WIKIS[source]+'/wiki/'+urllib.parse.quote(name.replace(' ','_'),safe='')


def parse_br_index(html):
    soup=BeautifulSoup(html,'html.parser');places={}
    for table in soup.find_all('table'):
        first=table.find('tr');heads=[h.get_text(' ',strip=True) for h in first.find_all('th',recursive=False)] if first else []
        if heads[:2]!=['Nome','Level']:continue
        body=table.find('tbody',recursive=False) or table
        for row in body.find_all('tr',recursive=False):
            cells=row.find_all('td',recursive=False)
            if len(cells)<7:continue
            a=cells[0].find('a')
            if not a:continue
            name=a.get('title') or a.get_text(strip=True);id=ident(name)
            lvl=cells[1].get_text(' ',strip=True);m=re.fullmatch(r'(\d+)\+?',lvl)
            places[id]={'id':id,'name':name,'aliases':[name]+ALIASES.get(name,[]),'region':cells[5].get_text(' ',strip=True)[:100],
                        'level':int(m.group(1)) if m else None,'creatures':[],'conditional':[],'sources':{'br':{'url':wiki_url('br',name),'roster':False}},
                        'coverage':'indice BR; ficha pendente','parent_id':None}
    if len(places)<100:raise ValueError('Índice BR incompleto ou formato alterado')
    return places


def templates(text):
    stack=[];i=0
    while i<len(text)-1:
        if text[i:i+2]=='{{':stack.append(i);i+=2
        elif text[i:i+2]=='}}':
            if stack:
                start=stack.pop();yield start,text[start+2:i]
            i+=2
        else:i+=1


def split_template(raw):
    parts=[];start=0;depth=0;brackets=0;i=0
    while i<len(raw):
        two=raw[i:i+2]
        if two=='{{':depth+=1;i+=2;continue
        if two=='}}':depth=max(0,depth-1);i+=2;continue
        if two=='[[':brackets+=1;i+=2;continue
        if two==']]':brackets=max(0,brackets-1);i+=2;continue
        if raw[i]=='|' and not depth and not brackets:parts.append(raw[start:i]);start=i+1
        i+=1
    parts.append(raw[start:]);return parts


def parse_wiki_place(text,name,source,names):
    infobox=monstros._campos_infobox(text,'Infobox Hunt') or monstros._campos_infobox(text,'Infobox_Hunts')
    if source=='en' and not infobox:return None
    if re.search(r'\[\[Category:Deprecated\]\]',text,re.I):return None
    city=infobox.get('city','');region=monstros._sem_links(city).strip()[:100]
    sections=[];all_mobs=[];conditional=[]
    # BR documents respawns explicitly inside Infobox_Hunts; parse these lists, not incidental narrative links.
    in_respawns=False
    for line in text.splitlines():
        if re.search(r"\*\s*'''Respawns?:?'''",line,re.I):in_respawns=True;continue
        if in_respawns and (re.match(r'\s*\|\w',line) or re.match(r'\s*={2,5}',line)):in_respawns=False
        if not in_respawns:continue
        m=re.match(r"\s*\*{2,}\s*'''(.*?)'''\s*:?(.*)",line)
        if not m:continue
        label=m.group(1).rstrip(':').strip();mobs=[]
        for part in monstros._sem_links(m.group(2)).split(','):
            clean=re.sub(r'\([^)]*\)','',part).strip(' .;:')
            clean=re.sub(r'^\d+\s*','',clean)
            if clean and len(clean)<80 and re.fullmatch(r"[\w '\-]+",clean):mobs.append(canonical_creature(clean,names))
        is_conditional=bool(re.search(r'boss|quest|summon|invas|raid|event',label,re.I))
        (conditional if is_conditional else all_mobs).extend(mobs)
        floor=re.search(r'\(?-([1-9])\)?',label)
        if not is_conditional and mobs and (floor or re.search(r'andar|floor|setor|section|superficie|superfície',label,re.I)):
            sections.append({'name':label[:100],'floor':int(floor.group(1)) if floor else None,'creatures':sorted(set(mobs))})
    for offset,raw in sorted(templates(text)):
        bits=split_template(raw);kind=key(bits[0])
        if kind not in ('creaturelist','creature list','creature table','tabela criatura','tabela criaturas','tabela de criaturas'):continue
        label='';mobs=[]
        for b in bits[1:]:
            if '=' in b:
                k,v=b.split('=',1)
                if k.strip().lower()=='caption':label=monstros._sem_links(v).strip()
                continue
            clean=monstros._sem_links(b).strip()
            if clean and len(clean)<120 and re.search(r'[A-Za-z]',clean) and not any(c in clean for c in '{}<>'):
                mobs.append(canonical_creature(clean,names))
        headings=list(re.finditer(r'(?m)^\s*(={2,5})\s*(.*?)\s*\1\s*$',text[:offset]))
        heading=headings[-1].group(2).strip() if headings else ''
        label=label or heading
        is_conditional=bool(re.search(r'boss|quest|summon|invas|raid|event|summoned',label,re.I))
        target=conditional if is_conditional else all_mobs;target.extend(mobs)
        floor=re.search(r'\(?-([123456789])\)?',label)
        sector=bool(floor or re.search(r'floor|andar|section|setor|first|second|third|primeiro|segundo|terceiro',label,re.I))
        if sector and not is_conditional and mobs:sections.append({'name':label[:100],'floor':int(floor.group(1)) if floor else None,'creatures':sorted(set(mobs))})
    # Some pages use links only under a Creatures heading. Do not infer creatures from loot/strategy prose.
    for m in re.finditer(r'(?im)^\s*(={2,5})\s*(?:Creatures|Criaturas)\s*\1\s*$',text):
        tail=text[m.end():];end=re.search(r'(?m)^\s*={2,5}[^=]',tail);chunk=tail[:end.start()] if end else tail
        for link in re.findall(r'\[\[([^\]|#]+)',chunk):
            known=names.get(monstros.singularizar(link))
            if known:all_mobs.append(known)
    return {'region':region,'creatures':sorted(set(all_mobs)-set(conditional)),'conditional':sorted(set(conditional)),'sections':sections}


def normalize_places(places):
    remap={}
    for id,p in list(places.items()):
        if not p.get('parent_id'):continue
        equivalent=ident(p['name'].replace(' · ',' '))
        if equivalent!=id and equivalent in places and not places[equivalent].get('parent_id'):
            target=places[equivalent];target['sources'].update(p['sources']);target['parent_id']=p['parent_id']
            target['creatures']=sorted(set(target['creatures'])|set(p['creatures']));target['aliases']=list(set(target['aliases']+p['aliases']+[p['name']]))
            target['coverage']='setor correlacionado BR/EN';remap[id]=equivalent;del places[id]
    for p in places.values():
        p['creatures']=sorted(set(p['creatures'])-set(p.get('conditional',[])))
        n=key(p['name'])
        if 'secret library' in n:
            for el,pt in [('fire','fogo'),('ice','gelo'),('energy','energia'),('earth','terra')]:
                if el in n:p['aliases']+=['livraria '+pt,'livraria de '+pt,'biblioteca '+pt,'biblioteca de '+pt,el+' library',el+' lib']
        if p['name']=='Asura Vaults':p['aliases']+=['asura mirror','asuras mirror','asuras espelho']
        p['aliases']=sorted(set(p['aliases']))
    return remap


def wiki_catalog(fetcher,work_dir,names,refresh=False):
    cached=read_json(Path(work_dir)/'wiki.json')
    if cached and not refresh and time.time()-cached.get('checked_at',0)<7*86400:return cached
    warnings=[];places={};counts={}
    try:
        places=parse_br_index(fetcher.get(WIKIS['br']+'/wiki/Locais_de_Ca%C3%A7a'));counts['br_index']=len(places)
        atomic_json(Path(work_dir)/'br-index.json',places)
    except Exception:
        places=read_json(Path(work_dir)/'br-index.json') or cached.get('places',{});counts['br_index']=len(places)
        warnings.append('Índice BR indisponível nesta consulta; preservado o cadastro anterior.');counts['br_index_cached']=True
    en_names=[];params={'action':'query','list':'categorymembers','cmtitle':'Category:Hunting Places','cmnamespace':0,'cmlimit':500,'format':'json'}
    while True:
        r=json.loads(fetcher.get(WIKIS['en']+'/api.php?'+urllib.parse.urlencode(params)))
        en_names.extend(p['title'] for p in r.get('query',{}).get('categorymembers',[]))
        if not r.get('continue'):break
        params.update(r['continue'])
    if not en_names:raise ValueError('Índice EN indisponível')
    counts['en_index']=len(en_names)
    # Batch revisions are public MediaWiki data and avoid hundreds of individual requests.
    for source,titles in [('en',en_names),('br',[p['name'] for p in places.values() if 'br' in p.get('sources',{})])]:
        source_failed=False
        for start in range(0,len(titles),35):
            params={'action':'query','titles':'|'.join(titles[start:start+35]),'prop':'revisions','rvprop':'content|ids|timestamp',
                    'rvslots':'main','format':'json','formatversion':2,'redirects':1}
            try:r=json.loads(fetcher.get(WIKIS[source]+'/api.php?'+urllib.parse.urlencode(params)))
            except Exception:
                warnings.append('Fichas '+source.upper()+' indisponíveis; lacunas não foram preenchidas por suposição.');source_failed=True;break
            for page in r.get('query',{}).get('pages',[]):
                if not page.get('revisions'):continue
                rev=page['revisions'][0];text=rev.get('slots',{}).get('main',{}).get('content','');name=page['title']
                parsed=parse_wiki_place(text,name,source,names)
                if not parsed:continue
                id=ident(name);p=places.setdefault(id,{'id':id,'name':name,'aliases':[name]+ALIASES.get(name,[]),'region':'','level':None,'creatures':[],
                                                     'conditional':[],'sources':{},'coverage':'','parent_id':None})
                p['sources'][source]={'url':wiki_url(source,name),'revision':rev.get('revid'),'revision_date':rev.get('timestamp'),'roster':bool(parsed['creatures'])}
                if p['creatures'] and parsed['creatures'] and set(p['creatures'])!=set(parsed['creatures']):p['divergence']=True
                p['creatures']=sorted(set(p['creatures'])|set(parsed['creatures']));p['conditional']=sorted(set(p['conditional'])|set(parsed['conditional']))
                p['region']=p['region'] or parsed['region'];p['coverage']='ficha '+source.upper() if parsed['creatures'] else 'ficha sem criaturas extraíveis'
                for sec in parsed['sections']:
                    label=('Andar -'+str(sec['floor'])) if sec['floor'] else sec['name'];sid=id+'--'+ident(label)
                    alias=[name+' '+label,name+' -'+str(sec['floor'])] if sec['floor'] else [name+' '+label]
                    if sec['floor']:
                        alias += [a+' -'+str(sec['floor']) for a in ALIASES.get(name,[])]
                    places[sid]={'id':sid,'name':name+' · '+label,'aliases':alias,'region':p['region'],'level':p['level'],'creatures':sec['creatures'],
                                 'conditional':[],'sources':{source:dict(p['sources'][source])},'coverage':'setor documentado '+source.upper(),'parent_id':id}
        counts[source+'_revision_blocked']=source_failed
        print('wiki',source,len(places),'locais/setores',flush=True)
    normalize_places(places)
    out={'checked_at':time.time(),'places':places,'counts':counts,'warnings':warnings};atomic_json(Path(work_dir)/'wiki.json',out);return out


def number(text):
    m=re.match(r'\s*(\d[\d.,]*)',text)
    return int(re.sub(r'\D','',m.group(1))) if m else None


def parse_public_index(html,places):
    soup=BeautifulSoup(html,'html.parser');text=soup.get_text(' ',strip=True)
    total=re.search(r'Displaying hunt sessions.*?of\s+([\d,]+)\s+in total',text,re.I)
    if not total:raise ValueError('Índice público não reconhecido')
    rows={}
    for card in soup.select('[data-row-click-url-value]'):
        m=re.fullmatch(r'/hunt_sessions/(\d+)',card.get('data-row-click-url-value',''))
        if not m or not card.find('h3'):continue
        id=m.group(1);title=card.find('h3').get_text(' ',strip=True)
        notes=' '.join(e.get('title','') for e in card.select('span[title]'))
        text=card.get_text(' ',strip=True);date=''
        dm=re.search(r'[A-Z][a-z]{2}\s+\d{1,2},\s+\d{4}\s+\d{2}:\d{2}',text)
        if dm:
            try:date=datetime.strptime(dm.group(),'%b %d, %Y %H:%M').isoformat(timespec='minutes')
            except ValueError:pass
        duration=re.search(r'(\d{1,3}):(\d{2})h',text)
        members=re.search(r'\bx([2-9])\b',text);count=int(members.group(1)) if members else 2 if re.search(r'\bDuo\b',text) else 1
        roles=[]
        for span in card.find_all('span'):
            v=span.get_text(strip=True)
            if v in ('EK','ED','MS','RP','EM'):
                nxt=span.find_next_sibling('span');level=number(nxt.get_text()) if nxt else None;roles.append({'vocation':v,'level':level})
        rows[id]={'id':id,'date':date,'minutes':int(duration.group(1))*60+int(duration.group(2)) if duration else None,
                  'members':count,'vocation':roles[0]['vocation'] if count==1 and len(roles)==1 else None,
                  'level':roles[0]['level'] if count==1 and len(roles)==1 else None,'title_candidates':title_candidates(title+' '+notes,places)}
    return {'total':int(total.group(1).replace(',','')),'rows':rows}


def cells(table):
    return [[c.get_text(' ',strip=True) for c in tr.find_all(['th','td'],recursive=False)] for tr in table.find_all('tr')]


def parse_public_session(html,metadata,names):
    id=metadata['id'];soup=BeautifulSoup(html,'html.parser');main=soup.find(id='hunt_session_'+id)
    if main is None:raise ValueError('Sessão pública indisponível ou formato alterado')
    tables=[(t,cells(t)) for t in main.find_all('table')];kills={};inputs=[]
    for index,(t,rows) in enumerate(tables):
        if not rows:continue
        heads=[key(h) for h in rows[0]]
        if heads==['','monster','killed'] or heads==['monster','killed']:
            for row in rows[1:]:
                if len(row)<2:continue
                n=canonical_creature(row[-2],names);v=number(row[-1])
                if v is not None and v>0:kills[n]=kills.get(n,0)+v
        if heads not in (['','type','damage'],['type','damage']):continue
        types={}
        for row in rows[1:]:
            if len(row)<2:continue
            el=key(row[-2]).replace(' ','');v=number(row[-1])
            if el in ELEMENTS and v is not None:types[el]=v
        if not any(v>0 for el,v in types.items() if el!='manadrain'):continue
        sources={}
        if index+1<len(tables):
            source_rows=tables[index+1][1]
            if source_rows and [key(h) for h in source_rows[0]] in (['','monster','damage'],['monster','damage']):
                for row in source_rows[1:]:
                    if len(row)<2:continue
                    n=canonical_creature(row[-2],names);v=number(row[-1])
                    if v is not None:sources[n]=sources.get(n,0)+v
        ancestors=[p.get('id','') for p in t.parents if p.get('id','').startswith('hunt_session_')]
        origin=ancestors[0].replace('hunt_session_','') if ancestors else id
        inputs.append({'origin':origin+':'+str(len(inputs)),'scope':'party_member' if metadata.get('members',1)>1 else 'solo',
                       'types':types,'sources':sources,'vocation':metadata.get('vocation'),'level':metadata.get('level')})
    return dict(metadata,kills=kills,inputs=inputs,public_url=PUBLIC+'/hunt_sessions/'+id,
                input_partial=metadata.get('members',1)>1 and len(inputs)<metadata['members'],checked_at=time.time())


def collect(args):
    work=Path(args.work_dir);work.mkdir(parents=True,exist_ok=True);fetcher=Fetcher(args.gap)
    knowledge=read_json(args.creatures).get('criaturas',{});names={monstros.singularizar(n):n for n in knowledge}
    wiki=wiki_catalog(fetcher,work,names,args.refresh_wiki);places=wiki['places']
    for p in places.values():
        for n in p['creatures']+p.get('conditional',[]):names.setdefault(monstros.singularizar(n),n)
    first=parse_public_index(fetcher.get(PUBLIC+'/hunt_sessions?hunt_sessions_by=is_public'),places)
    index=dict(first['rows']);pages=math.ceil(first['total']/20);errors=[]
    def listing(page):return parse_public_index(fetcher.get(PUBLIC+'/hunt_sessions?'+urllib.parse.urlencode({'hunt_sessions_by':'is_public','page':page})),places)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures={pool.submit(listing,page):page for page in range(2,pages+1)}
        for f in as_completed(futures):
            try:index.update(f.result()['rows'])
            except Exception:errors.append('index_page_'+str(futures[f]))
            if len(futures)%25==0 or len(index)%200<20:print('indice',len(index),'/',first['total'],flush=True)
    atomic_json(work/'index.json',index)
    records=read_json(work/'records.json');failed=read_json(work/'failed.json');done=0
    for id,m in index.items():
        if id in records:records[id].update(m)
    to_fetch=[m for id,m in index.items() if id not in records or args.revalidate or time.time()-records[id].get('checked_at',0)>30*86400]
    if args.limit:to_fetch=to_fetch[:args.limit]
    def detail(m):return parse_public_session(fetcher.get(PUBLIC+'/hunt_sessions/'+m['id']),m,names)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures={pool.submit(detail,m):m['id'] for m in to_fetch}
        for f in as_completed(futures):
            id=futures[f]
            try:records[id]=f.result();failed.pop(id,None)
            except Exception as e:failed[id]={'at':time.time(),'kind':type(e).__name__}
            done+=1
            if done%25==0 or done==len(to_fetch):
                atomic_json(work/'records.json',records);atomic_json(work/'failed.json',failed)
                print('sessoes',len(records),'coletadas;',done,'/',len(to_fetch),'novas/revalidacao;',len(failed),'falhas',flush=True)
    # Index must be complete before removing sessions no longer public. Transient failures keep the previous valid base.
    index_complete=not errors and len(index)>=first['total']*.98
    if index_complete:
        records={id:r for id,r in records.items() if id in index}
    if not records:raise ValueError('Sem sessões válidas; snapshot não publicado')
    previous=read_json(args.output)
    if previous.get('records') and len(records)<len(previous['records'])*.9:raise ValueError('Queda anormal na cobertura; snapshot anterior preservado')
    metadata={'collected_at':datetime.now(timezone.utc).isoformat(),'collected_timestamp':time.time(),'index_count':len(index),'index_reported':first['total'],
              'index_complete':index_complete,'wiki_counts':wiki['counts'],'warnings':wiki['warnings'],'detail_failures':len(failed),'index_failures':errors,
              'update_policy':'indice diario; detalhes novos; revalidacao mensal; Wikis semanais','source_urls':[PUBLIC+'/hunt_sessions?hunt_sessions_by=is_public',
              WIKIS['br']+'/wiki/Locais_de_Ca%C3%A7a',WIKIS['en']+'/wiki/Hunting_Places']}
    sanitize_records(records,names)
    snapshot=aggregate(places,records,metadata);validate_snapshot(snapshot)
    atomic_json(args.output,snapshot);atomic_json(work/'records.json',records)
    print('SNAPSHOT',json.dumps(snapshot['metadata'],ensure_ascii=False),flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--work-dir',required=True);parser.add_argument('--output',default='data/hunt_catalog.json')
    parser.add_argument('--creatures',default='data/creature_knowledge.json');parser.add_argument('--workers',type=int,default=2);parser.add_argument('--gap',type=float,default=.55)
    parser.add_argument('--refresh-wiki',action='store_true');parser.add_argument('--revalidate',action='store_true');parser.add_argument('--limit',type=int,default=0)
    args=parser.parse_args();args.workers=max(1,min(3,args.workers));args.gap=max(.4,args.gap);collect(args)


if __name__=='__main__':main()
