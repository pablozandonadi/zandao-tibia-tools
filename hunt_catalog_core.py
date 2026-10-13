"""Catálogo de locais, correlação conservadora e estatísticas sem dados pessoais."""
import math
import re
import statistics
import unicodedata
from urllib.parse import urlsplit
from collections import Counter, defaultdict

SCHEMA = 1
ELEMENTS = ('physical','fire','earth','energy','ice','death','holy','drowning','lifedrain','manadrain')


def key(text):
    s=unicodedata.normalize('NFKD',str(text)).encode('ascii','ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+',' ',s).strip()


def ident(text):
    return key(text).replace(' ','-')


def canonical_creature(text, names):
    from monstros import singularizar
    clean=str(text).strip().replace('_',' ')
    return names.get(singularizar(clean),clean)


def title_candidates(text, places):
    normalized=' '+key(text)+' '
    candidates=[]
    for p in places.values():
        for alias in p.get('aliases',[]) + [p['name']]:
            a=key(alias)
            if len(a)<4 and not re.fullmatch(r'wz\d+',a):continue
            if ' '+a+' ' in normalized:
                candidates.append((p['id'],len(a)))
    # A specific title wins over a parent/location substring, not over other independent titles.
    longest=max((n for _,n in candidates),default=0)
    return sorted({i for i,n in candidates if n==longest})


def correlate(record, places):
    kills=record.get('kills',{})
    total=sum(kills.values())
    if not total:return {'status':'incomplete','reason':'sem abates','candidates':[]}
    candidates=[]
    hinted=record.get('title_candidates',[])
    for p in places.values():
        roster=set(p.get('creatures',[]))
        coverage=sum(v for n,v in kills.items() if n in roster)/total if roster else 0
        hits=len(roster.intersection(kills))
        if coverage>=.8:
            candidates.append({'id':p['id'],'coverage':round(coverage,4),'hits':hits})
    trusted=[c for c in candidates if c['id'] in hinted]
    if len(trusted)==1:
        return {'status':'confirmed','place_id':trusted[0]['id'],'method':'titulo + abates','coverage':trusted[0]['coverage'],'candidates':trusted}
    # Never pick a floor because its monsters also occur on another floor.
    parents=[c for c in candidates if not places[c['id']].get('parent_id')]
    parents.sort(key=lambda c:(-c['coverage'],-c['hits'],c['id']))
    if not hinted and len(parents)==1 and parents[0]['hits']>=2 and parents[0]['coverage']>=.95:
        return {'status':'confirmed','place_id':parents[0]['id'],'method':'composicao unica','coverage':parents[0]['coverage'],'candidates':parents}
    reason='titulo contradiz abates' if hinted and not trusted else 'local ou setor ambiguo' if candidates else 'sem local compativel'
    return {'status':'review','reason':reason,'candidates':candidates[:8]}


def percentile(values, q):
    if not values:return None
    ordered=sorted(values);position=(len(ordered)-1)*q;lo=int(position);hi=math.ceil(position)
    return ordered[lo]+(ordered[hi]-ordered[lo])*(position-lo)


def profile(records):
    shares=defaultdict(list);totals=Counter();source_shares=defaultdict(list);seen=set();inputs=0
    for r in records:
        for i,p in enumerate(r.get('inputs',[])):
            # Party pages can embed another session. Use the original record when identifiable.
            origin=p.get('origin',f"{r['id']}:{i}")
            if origin in seen:continue
            seen.add(origin)
            vals=p.get('types',{});den=sum(vals.values())
            if not den:continue
            inputs+=1;totals.update(vals)
            for el in ELEMENTS:shares[el].append(vals.get(el,0)/den*100)
            sources=p.get('sources',{});sd=sum(sources.values())
            if sd:
                for n,v in sources.items():source_shares[n].append(v/sd*100)
    rows=[]
    for el in ELEMENTS:
        values=shares[el]
        if values:
            rows.append({'element':el,'mean_pct':round(statistics.mean(values),3),'p25':round(percentile(values,.25),3),
                         'p75':round(percentile(values,.75),3),'amount':totals[el]})
    return {'inputs':inputs,'elements':sorted(rows,key=lambda e:-e['mean_pct']),
            'quality':'insuficiente' if inputs<5 else 'amostra inicial' if inputs<20 else 'amostra ampliada',
            'policy':'media dos percentuais por registro; mana separada visualmente; variacao interquartil',
            'sources':dict(totals_sources(records))}


def totals_sources(records):
    out=Counter();seen=set()
    for r in records:
        for i,p in enumerate(r.get('inputs',[])):
            origin=p.get('origin',f"{r['id']}:{i}")
            if origin in seen:continue
            seen.add(origin);out.update(p.get('sources',{}))
    return out


def local_roster(place):
    """Whitelist do setor escolhido; nunca usa a lista do local pai ou abates públicos."""
    from monstros import singularizar
    excluded={singularizar(n) for n in place.get('conditional',[])}
    return {singularizar(n):n for n in place.get('creatures',[]) if singularizar(n) not in excluded}


def local_kills(place,kills):
    from monstros import singularizar
    roster=local_roster(place);out=Counter()
    for name,count in kills.items():
        canonical=roster.get(singularizar(name))
        if canonical and count>0:out[canonical]+=count
    return dict(out)


def local_composition(place,records):
    """Cada sessão contribui com abates locais normalizados, sem contar o trajeto."""
    shares=defaultdict(float);kills=Counter();excluded=0;species=set();sessions=0
    for r in records:
        selected=local_kills(place,r.get('kills',{}));total=sum(selected.values())
        excluded+=sum(r.get('kills',{}).values())-total
        species.update(n for n in r.get('kills',{}) if not local_kills(place,{n:r['kills'][n]}))
        if not total:continue
        sessions+=1;kills.update(selected)
        for n,count in selected.items():shares[n]+=count/total
    return {'sessions':sessions,'kills':dict(kills),'composition':{n:round(v/sessions*100,5) for n,v in shares.items()} if sessions else {},
            'excluded_kills':excluded,'excluded_species':len(species)}


def local_input(place,input_):
    """Marginais não permitem subtrair dano por elemento de criaturas do caminho."""
    sources={n:v for n,v in input_.get('sources',{}).items() if v>0}
    return bool(sources) and sum(local_kills(place,sources).values())==sum(sources.values())


def aggregate(places, records, metadata):
    groups=defaultdict(list);review=Counter();confirmed=0
    for record in records.values():
        assignment=correlate(record,places);record['assignment']=assignment
        if assignment['status']=='confirmed':
            groups[assignment['place_id']].append(record);confirmed+=1
        else:review[assignment.get('reason','incompleto')]+=1
    for p in places.values():
        samples=groups[p['id']];local=local_composition(p,samples)
        safe_samples=eligible_damage(p,samples)
        p['observed']={'sessions':len(samples),'kills':local['kills'],'composition':local['composition'],
                       'excluded_kills':local['excluded_kills'],'excluded_species':local['excluded_species'],
                       'profile':profile(safe_samples),'profiles_by_context':{},'sample_ids':[r['id'] for r in sorted(samples,key=lambda r:r.get('date',''),reverse=True)],
                       'period':[min((r.get('date','') for r in samples),default=''),max((r.get('date','') for r in samples),default='')]}
        contexts=defaultdict(list)
        for r in safe_samples:
            contexts['party' if r.get('members',1)>1 else 'solo'].append(r)
            if r.get('members',1)==1 and r.get('vocation'):contexts['solo_'+r['vocation']].append(r)
        p['observed']['profiles_by_context']={c:profile(rs) for c,rs in contexts.items()}
    metadata.update(sessions_collected=len(records),sessions_confirmed=confirmed,review_reasons=dict(review),
                    places=len(places),places_with_creatures=sum(bool(p.get('creatures')) for p in places.values()),
                    sessions_with_input=sum(bool(r.get('inputs')) for r in records.values()))
    return {'schema':SCHEMA,'metadata':metadata,'places':places,'records':records}


def eligible_damage(place,records):
    """Mantém somente Inputs cujas fontes positivas pertencem ao setor documentado."""
    return [dict(r,inputs=[dict(p,location_damage_coverage=1.0) for p in r.get('inputs',[]) if local_input(place,p)]) for r in records]


def validate_snapshot(data):
    if not isinstance(data,dict) or data.get('schema')!=SCHEMA:raise ValueError('Versao de catalogo incompatível')
    places=data.get('places');records=data.get('records');meta=data.get('metadata')
    if not isinstance(places,dict) or not places or len(places)>10000 or not isinstance(records,dict) or len(records)>200000 or not isinstance(meta,dict):raise ValueError('Catalogo invalido')
    stamp=meta.get('collected_timestamp',0)
    if not isinstance(stamp,(int,float)) or not math.isfinite(stamp):raise ValueError('Data invalida')
    for id,p in places.items():
        if p.get('id')!=id or not isinstance(p.get('name'),str) or len(p['name'])>180:raise ValueError('Local invalido')
        if not isinstance(p.get('creatures',[]),list) or len(p.get('creatures',[]))>1000:raise ValueError('Criaturas invalidas')
        for source in p.get('sources',{}).values():
            u=urlsplit(source.get('url',''))
            if u.scheme!='https' or u.netloc not in ('www.tibiawiki.com.br','tibiawiki.com.br','tibia.fandom.com') or not u.path.startswith('/wiki/'):raise ValueError('Fonte Wiki invalida')
    forbidden={'author','character','player','title','description','html','email','world'}
    def check(obj):
        if isinstance(obj,dict):
            if forbidden.intersection(obj):raise ValueError('Dados pessoais/brutos não permitidos no catalogo')
            for v in obj.values():check(v)
        elif isinstance(obj,list):
            for v in obj:check(v)
    check(data)
    for id,r in records.items():
        if not str(id).isdigit() or str(r.get('id'))!=str(id):raise ValueError('ID de sessao invalido')
        if r.get('public_url')!='https://www.hunt-analyser.com/hunt_sessions/'+str(id):raise ValueError('URL de sessao invalida')
        for n,c in r.get('kills',{}).items():
            if not isinstance(n,str) or len(n)>120 or not isinstance(c,int) or c<0:raise ValueError('Abates invalidos')
        for p in r.get('inputs',[]):
            if any(el not in ELEMENTS or not isinstance(v,(int,float)) or not math.isfinite(v) or v<0 for el,v in p.get('types',{}).items()):raise ValueError('Dano invalido')
    return data


def sanitize_records(records,names):
    """Texto livre desconhecido nunca é publicado como nome de criatura (pode conter dados pessoais)."""
    from monstros import singularizar
    def clean(counter):
        out=Counter()
        for n,v in counter.items():
            known=names.get(singularizar(n))
            label=known or ('(other)' if key(n)=='other' else '(não catalogado)')
            out[label]+=v
        return dict(out)
    for r in records.values():
        r['kills']=clean(r.get('kills',{}))
        for p in r.get('inputs',[]):p['sources']=clean(p.get('sources',{}))
    return records
