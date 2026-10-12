"""Fichas complementares das Wikis BR/EN: valores explícitos e proveniência."""
import re
import unicodedata
import time
from urllib.parse import quote
import monstros
from damage_core import ROTULO

SCHEMA = 2
URLS = {'br':'https://www.tibiawiki.com.br/wiki/','en':'https://tibia.fandom.com/wiki/'}

def fonte(key, name):
    return URLS[key]+quote(name.replace(' ', '_'),safe='')

def parse_en(text, name):
    fields = monstros._campos_infobox(text, 'Infobox Creature')
    if not fields: raise ValueError('Sem Infobox Creature')
    attacks, warnings = [], []
    raw = fields.get('abilities','')
    idx = raw.find('{{Ability List')
    container = monstros._extrair_template(raw,idx) if idx >= 0 else raw
    for part in monstros._separar_params(container or ''):
        if not part.strip().startswith('{{'): continue
        body = monstros._extrair_template(part,0)
        if not body: continue
        params = monstros._separar_params(body)
        kind = params[0].strip().lower()
        if kind not in ('ability','melee'): continue
        pos, named = [], {}
        for param in params[1:]:
            k, sep, value = param.partition('=')
            if sep and '{{' not in k: named[k.strip().lower()] = value.strip()
            else: pos.append(param.strip())
        title = 'Melee' if kind == 'melee' else monstros._sem_links(pos[0] if pos else '')
        dmg = (pos[0] if pos else '') if kind == 'melee' else (pos[1] if len(pos)>1 else '')
        el = 'physical' if kind == 'melee' else monstros._norm_el(named.get('element') or (pos[2] if len(pos)>2 else ''))
        if el not in ROTULO or el == 'healing':
            if el is None and re.search(r'\d\s*[-–]\s*\d',dmg): warnings.append(f'TibiaWiki EN: {title} tem faixa, mas não informa elemento confirmado.')
            continue
        if '?' in dmg or not re.search(r'\d[\d,]*\s*[-–]\s*\d',dmg):
            warnings.append(f'TibiaWiki EN: {title} sem faixa confirmada.');continue
        lo,hi = monstros._faixa(dmg.split(';')[0])
        if lo is None or hi is None or hi<lo: continue
        attacks.append(dict(nome=title,elemento=el,min=lo,max=hi,origem='en',fontes=['en']))
    resist = {}
    for field,el in monstros.MOD_CHAVES.items():
        if el == 'healing': continue
        raw = fields.get(field,'')
        m = re.match(r'\s*(-?\d+)\s*%?',raw)
        if m and '?' not in raw: resist[el]=int(m.group(1))
    maxima = {}
    raw = fields.get('maxdmg','')
    idx = raw.lower().find('{{max damage')
    body = monstros._extrair_template(raw,idx) if idx >= 0 else None
    for part in monstros._separar_params(body or ''):
        key,sep,value = part.partition('=')
        el = monstros._norm_el(key)
        if sep and el in ROTULO and el != 'healing' and re.fullmatch(r'\s*\d[\d,]*\s*',value):
            maxima[el]=int(value.replace(',','').strip())
    out=dict(nome=fields.get('name') or name,ataques=attacks,resist=resist,avisos=warnings,
             maximos_elemento=maxima,fonte=fonte('en',name),consultado=time.time())
    for key,target in [('hp','hp'),('exp','xp'),('armor','armor'),('mitigation','mitigation'),('speed','speed')]:
        raw=fields.get(key,'').strip()
        if re.fullmatch(r'\d+(?:\.\d+)?',raw):out[target]=float(raw) if '.' in raw else int(raw)
    return out

def _key(attack):
    name = unicodedata.normalize('NFKD',attack['nome'].lower()).encode('ascii','ignore').decode()
    if 'corpo a corpo' in name or name == 'melee': name='melee'
    for a,b in [('terra','earth'),('fogo','fire'),('gelo','ice'),('energia','energy'),('morte','death'),('sagrado','holy')]:
        name=name.replace(a,b)
    return attack['elemento'],re.sub(r'[^a-z0-9]','',name)

def merge(name,br=None,en=None,errors=None):
    br,en=br or {},en or {}
    attacks=[dict(a,origem='en',fontes=['en']) for a in en.get('ataques',[])]
    differences=[]; matched=set()
    for raw in br.get('ataques',[]):
        a=dict(raw,origem='br',fontes=['br'])
        index=next((i for i,b in enumerate(attacks) if i not in matched and b['origem']=='en' and _key(a)==_key(b)),None)
        if index is None and _key(a)[1] not in ('strike','wave','beam','berserk','ball','melee'):
            index=next((i for i,b in enumerate(attacks) if i not in matched and b['origem']=='en' and _key(a)[1]==_key(b)[1] and (a['min'],a['max'])==(b['min'],b['max'])),None)
        if index is None:
            index=next((i for i,b in enumerate(attacks) if i not in matched and b['origem']=='en' and (a['elemento'],a['min'],a['max'])==(b['elemento'],b['min'],b['max'])),None)
        if index is None:attacks.append(a);continue
        matched.add(index);b=attacks[index];b['fontes']=['en','br']
        if a['elemento'] != b['elemento']:
            differences.append(f"{b['nome']}: elemento BR {ROTULO[a['elemento']]}; EN {ROTULO[b['elemento']]}. Usada a classificação EN.")
            b['fontes']=['en']
        if (a['min'],a['max'])!=(b['min'],b['max']):
            differences.append(f"{b['nome']} ({ROTULO[b['elemento']]}): BR {a['min']}–{a['max']}; EN {b['min']}–{b['max']}. Usada a faixa EN.")
            b['fontes']=['en'];b['alternativa_br']={'min':a['min'],'max':a['max']}
    resist=dict(br.get('resist',{})); origins={e:'br' for e in resist}
    for el,value in en.get('resist',{}).items():
        if el in resist and resist[el]!=value:
            differences.append(f'{ROTULO[el]}: resistência BR {resist[el]}%; EN {value}%. Usado o valor EN.')
        resist[el]=value;origins[el]='en'
    warnings=list(en.get('avisos',[]))
    for warning in br.get('avisos',[]):
        if warning.startswith('Sem ataques com faixas conhecidas') and attacks:continue
        if 'sem faixa numérica' in warning and any(warning.startswith(ROTULO[a['elemento']]+':') for a in attacks):continue
        warnings.append(warning)
    warnings.extend(errors or [])
    maxima=en.get('maximos_elemento',{})
    for el,value in maxima.items():
        if not any(a['elemento']==el for a in attacks):
            warnings.append(f'{ROTULO[el]}: máximo {value} no resumo EN, sem faixa de ataque; não entra na estimativa.')
    if not attacks and not any('Sem ataques com faixas' in w for w in warnings):warnings.append('Sem ataques com faixas conhecidas nas fontes consultadas.')
    out=dict(nome=en.get('nome') or br.get('nome') or name,ataques=attacks,resist=resist,
             resist_fontes=origins,maximos_elemento=maxima,avisos=list(dict.fromkeys(warnings)),
             divergencias=differences,fontes={key:{'url':fonte(key,name),'disponivel':bool(value),
                       'revisao':value.get('revisao'),'consultado':value.get('consultado')} for key,value in [('br',br),('en',en)]},
             fonte=fonte('en' if en else 'br',name),consultado=time.time(),schema=SCHEMA,
             dados_fontes={'br':br,'en':en}, validade=3600 if errors else 7*86400)
    for key in ['hp','xp','armor','mitigation','speed']:
        value=en.get(key,br.get(key))
        if value is not None:out[key]=value
        if key in en and key in br and en[key]!=br[key]:differences.append(f'{key}: BR {br[key]}; EN {en[key]}. Usado o valor EN.')
    return out
