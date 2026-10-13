"""Leitor do catálogo distribuído. Não coleta milhares de páginas em cada computador."""
import hashlib
import json
import os
import threading
import time
import urllib.request
from collections import defaultdict
from datetime import datetime,timedelta

import monstros
from hunt_catalog_core import SCHEMA, eligible_damage, key, profile, validate_snapshot
from versao import CANAL_APP

BASE=os.path.join(monstros.BASE_DIR,'data','hunt_catalog.json')
CACHE=os.path.join(monstros.BASE_DIR,'cache_hunt_catalog.json')
CHECK=os.path.join(monstros.BASE_DIR,'cache_hunt_catalog_check.json')
REMOTE='https://raw.githubusercontent.com/pablozandonadi/zandao-tibia-tools/'+('hunt-catalog-beta' if CANAL_APP=='beta' else 'hunt-catalog-data')+'/catalog.json'
_lock=threading.Lock();_data=None;_running=False;_last_error=''


def _read(path):
    try:
        with open(path,encoding='utf-8') as f:return validate_snapshot(json.load(f))
    except (OSError,ValueError,KeyError,TypeError):return None


def data():
    global _data
    with _lock:
        if _data is None:
            candidates=[d for d in (_read(CACHE),_read(BASE)) if d]
            _data=max(candidates,key=lambda d:d['metadata'].get('collected_timestamp',0)) if candidates else {'schema':SCHEMA,'metadata':{},'places':{},'records':{}}
        return _data


def refresh(force=False):
    global _data,_running,_last_error
    with _lock:
        if _running:return {'status':'atualizando'}
        _running=True
    try:
        try:
            with open(CHECK,encoding='utf-8') as f:last=json.load(f).get('at',0)
        except (OSError,ValueError):last=0
        if not force and time.time()-last<86400:return {'status':'atualizado'}
        def get(url,limit):
            with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'ZandaoTibiaTools hunt catalogue'}),timeout=20) as r:
                raw=r.read(limit+1)
                if len(raw)>limit:raise ValueError('Catalogo remoto muito grande')
                return raw
        digest=get(REMOTE+'.sha256',256).decode().strip()
        if len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):raise ValueError('Checksum invalido')
        current=data()
        try:
            with open(CACHE,'rb') as f:unchanged=hashlib.sha256(f.read()).hexdigest()==digest
        except OSError:unchanged=False
        if not unchanged:
            raw=get(REMOTE,32*1024*1024)
            if hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('Checksum divergente; base anterior preservada')
            new=validate_snapshot(json.loads(raw))
            if new['metadata'].get('collected_timestamp',0)<current['metadata'].get('collected_timestamp',0):raise ValueError('Snapshot remoto anterior ao disponivel')
            tmp=CACHE+'.tmp'
            with open(tmp,'wb') as f:f.write(raw)
            os.replace(tmp,CACHE)
            with _lock:_data=new
        with open(CHECK+'.tmp','w',encoding='utf-8') as f:json.dump({'at':time.time()},f)
        os.replace(CHECK+'.tmp',CHECK);_last_error=''
        return {'status':'atualizado'}
    except Exception:
        _last_error='Atualização remota indisponível; mantida a última base válida.'
        # Back off failures too; do not create one thread/request per navigation.
        try:
            with open(CHECK+'.tmp','w',encoding='utf-8') as f:json.dump({'at':time.time()-86400+3600},f)
            os.replace(CHECK+'.tmp',CHECK)
        except OSError:pass
        return {'status':'cache','aviso':_last_error}
    finally:
        with _lock:_running=False


def catalogo(atualizar=False):
    if atualizar:refresh(True)
    else:threading.Thread(target=refresh,daemon=True).start()
    d=data()
    return {'locais':[{'id':p['id'],'nome':p['name'],'regiao':p.get('region',''),'level':p.get('level'),'criaturas':len(p.get('creatures',[])),
                      'sessoes':p.get('observed',{}).get('sessions',0),'setor':bool(p.get('parent_id')),'aliases':p.get('aliases',[])} for p in sorted(d['places'].values(),key=lambda p:p['name'].lower())],
            'metadata':d['metadata'],'aviso':_last_error}


def detalhes(id,contexto='all',dias=90):
    d=data();p=d['places'].get(id)
    if not p:return {'erro':'Local não encontrado no catálogo.'}
    if contexto not in ('all','solo','party','solo_EK','solo_ED','solo_RP','solo_MS','solo_EM'):return {'erro':'Contexto inválido.'}
    if dias not in (0,30,90,180,365):return {'erro':'Período inválido.'}
    samples=[d['records'][i] for i in p.get('observed',{}).get('sample_ids',[]) if i in d['records']]
    if dias:
        cutoff=(datetime.now()-timedelta(days=dias)).date().isoformat()
        samples=[r for r in samples if r.get('date','')>=cutoff]
    if contexto=='solo':samples=[r for r in samples if r.get('members',1)==1]
    elif contexto=='party':samples=[r for r in samples if r.get('members',1)>1]
    elif contexto.startswith('solo_'):samples=[r for r in samples if r.get('members',1)==1 and r.get('vocation')==contexto[5:]]
    composition=defaultdict(float)
    for r in samples:
        total=sum(r['kills'].values())
        for n,c in r['kills'].items():composition[n]+=c/total if total else 0
    observed={n:round(v/len(samples)*100,5) for n,v in composition.items()} if samples else {}
    return {'local':p,'sessoes':len(samples),'composicao':observed,'perfil':profile(eligible_damage(p,samples)),
            'sessoes_com_input':sum(bool(r.get('inputs')) for r in samples),'party_parcial':sum(bool(r.get('input_partial')) for r in samples),
            'amostras':[{'id':r['id'],'data':r.get('date',''),'membros':r.get('members',1),'inputs':len(r.get('inputs',[])),
                         'url':r['public_url'],'abates':sum(r['kills'].values())} for r in sorted(samples,key=lambda r:r.get('date',''),reverse=True)],
            'dias':dias,'contexto':contexto,'atualizado':d['metadata'].get('collected_at')}


def preset(id,modo='wiki',sessao='',input_index=0,contexto='all',dias=90):
    detail=detalhes(id,contexto,dias)
    if 'erro' in detail:return detail
    p=detail['local'];record=None;input_=None
    if modo=='session':
        record=data()['records'].get(str(sessao))
        if not record or (record.get('assignment') or {}).get('place_id')!=id:return {'erro':'Sessão não confirmada neste local.'}
        weights=record['kills']
        if record.get('inputs'):
            if not isinstance(input_index,int) or not 0<=input_index<len(record['inputs']):return {'erro':'Registro de Input inválido.'}
            input_=record['inputs'][input_index]
        origem='Sessão pública #'+str(sessao)
    elif modo=='observed':
        weights=detail['composicao'];origem='Composição observada em '+str(detail['sessoes'])+' sessões'
        if not weights:return {'erro':'Sem amostras confirmadas neste período/contexto.'}
    elif modo=='wiki':weights={n:1 for n in p['creatures']};origem='Criaturas documentadas na Wiki; pesos iguais, ajustáveis'
    else:return {'erro':'Composição inválida.'}
    import planejador
    available={monstros.singularizar(c['name']):c['name'] for c in planejador.catalogo_visual()['lista']}
    selected=[];missing=[]
    for name,weight in weights.items():
        if weight<=0:continue
        n=available.get(monstros.singularizar(name))
        if n:selected.append({'nome':n,'peso':weight})
        else:missing.append(name)
    if len(selected)>30:return {'erro':f'Este local tem {len(selected)} criaturas disponíveis. Escolha um piso/setor ou monte a composição manualmente. Nenhuma criatura foi cortada.'}
    if not selected:return {'erro':'Ainda não há fichas/GIFs disponíveis para carregar este local. Consulte as fontes listadas.'}
    damage=''
    if input_:
        from damage_core import ROTULO
        total=sum(input_['types'].values())
        damage='Received Damage\nTotal: '+str(total)+'\nDamage Types:\n'+'\n'.join(f"{ROTULO[el] if el in ('lifedrain','manadrain') else el.title()} {v} ({v/total*100:.6f}%)" for el,v in input_['types'].items())
        damage+='\nDamage Sources:\n'+'\n'.join(f"{n} {v} ({v/total*100:.6f}%)" for n,v in input_.get('sources',{}).items())
    warnings=['Criaturas não carregadas por falta de ficha/GIF: '+', '.join(missing)] if missing else []
    if record and record.get('input_partial'):warnings.append('Input disponível de apenas parte dos membros da party; não representa o dano recebido por todos.')
    return {'selecao':selected,'dano_texto':damage,'real':bool(damage),'total':sum(v['peso'] for v in selected),
            'total_log':sum(weights.values()),'origem':origem,'avisos':warnings,'public_url':record['public_url'] if record else None}
