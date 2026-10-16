"""Domínios locais do Assistente Tibiano. Nenhuma integração com o cliente do jogo."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import statistics
import threading
import unicodedata
import uuid

import boss_catalog
from tibia_info import faixa_shared

UTC = timezone.utc
LOCAL = timezone(timedelta(hours=-4))
LOCK = threading.RLock()
MAX_STORE_BYTES = 16*1024*1024
RULES = {'shared':'https://www.tibia.com/support/?entryid=92&subtopic=gethelp',
         'stamina':'https://www.tibia.com/support/?entryid=75&subtopic=gethelp',
         'bosstiary':'https://www.tibia.com/gameguides/?section=interface&subtopic=manual'}
GOALS = {'bane':[25,100,300], 'archfoe':[5,20,60], 'nemesis':[1,3,5]}
SEED = boss_catalog.catalog_seed()

def merge_catalog(stored):
    """Catálogo embutido atualiza cópias antigas dele mesmo; importações e cooldowns informados pelo jogador continuam valendo."""
    merged={b['boss_id']:deepcopy(b) for b in SEED}
    for b in stored:
        known=merged.get(b['boss_id'])
        if known and b.get('status') in ('partial','wiki'):known['aliases']=list(dict.fromkeys(known['aliases']+b['aliases']))[:10]
        else:merged[b['boss_id']]=b
    return list(merged.values())

def integer(value, low=1, high=100000):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f'Informe um inteiro entre {low} e {high}.')
    return value

def label(value):
    if not isinstance(value,str) or not value.strip() or len(value)>120 or any(ord(c)<32 for c in value):
        raise ValueError('Informe um nome de até 120 caracteres.')
    return value.strip()

def instant(value):
    try:
        d=datetime.fromisoformat(value.replace('Z','+00:00')) if isinstance(value,str) else value
        if not isinstance(d,datetime) or d.utcoffset() is None: raise ValueError()
        return d.astimezone(UTC)
    except (ValueError,TypeError,AttributeError):
        raise ValueError('Informe data e hora completas com fuso horário.') from None

def iso(value): return instant(value).isoformat()

def price_gp(value):
    if type(value) is int: return integer(value,1,10**12)
    if not isinstance(value,str): raise ValueError('Informe o preço em GP, K ou KK.')
    m=re.fullmatch(r'\s*(\d+)(?:([.,])(\d+))?\s*(kk|k|gp|gold)?\s*',value.lower())
    if not m or (m[2] and not m[4]): raise ValueError('Preço ambíguo. Confirme o inteiro em GP ou use K/KK.')
    try: gp=Decimal(m[1]+('.'+m[3] if m[3] else '')) * {'k':1000,'kk':1000000,'gp':1,'gold':1,None:1}[m[4]]
    except InvalidOperation: raise ValueError('Preço inválido.') from None
    if gp != gp.to_integral_value(): raise ValueError('O preço deve resultar em GP inteiros.')
    return integer(int(gp),1,10**12)

def item_name(value):
    value=label(value)
    return {'tc':'Tibia Coin','tibia coin':'Tibia Coin','tibia coins':'Tibia Coin','te ce':'Tibia Coin',
            'gold token':'Gold Token','silver token':'Silver Token'}.get(value.lower(),value)

def boss_key(text):
    """Chave de comparação: sem acento, caixa, pontuação nem artigo inicial ("The Pale Worm" == "pale worm")."""
    text=''.join(c for c in unicodedata.normalize('NFD',text.lower()) if not unicodedata.combining(c))
    return re.sub(r'^(?:the|o|a|os|as) ','',' '.join(re.sub(r'[^a-z0-9]+',' ',text).split()))

def recovery_minutes(start, target):
    integer(start,0,2520);integer(target,0,2520)
    if target<=start: return 0
    return 10 + max(0,min(target,2340)-start)*3 + max(0,target-max(start,2340))*6

def stamina_at(start, elapsed):
    integer(start,0,2520)
    elapsed=max(0,elapsed-10)
    below=min(max(0,2340-start),int(elapsed//3))
    elapsed-=below*3
    return min(2520,start+below+(int(elapsed//6) if start+below>=2340 else 0))

class Store:
    def __init__(self, folder, clock=None):
        self.folder=Path(folder);self.path=self.folder/'assistente-tibiano.json'
        self.clock=clock or (lambda: datetime.now(UTC))
        self._cache=None  # (mtime_ns, size) do arquivo já validado + estado serializado
        with LOCK: self._read()

    def _read(self):
        if not self.path.exists():
            return {'version':1,'timers':[],'kills':[],'totals':{},'stamina':{},'prices':[],
                    'watchlist':{},'alerts':[],'events':[],'requests':{},'catalog_version':1,'catalog':deepcopy(SEED)}
        try:
            st=self.path.stat()
            if st.st_size>MAX_STORE_BYTES: raise ValueError()
            # UI e alertas leem várias vezes por segundo; só revalida quando o arquivo muda.
            # shortcut: escrita externa com mesmo tamanho no mesmo tique de mtime passa despercebida; trocar por hash se surgir restauração externa frequente.
            if self._cache and self._cache[0]==(st.st_mtime_ns,st.st_size): return json.loads(self._cache[1])
            d=validate_state(json.loads(self.path.read_text(encoding='utf-8-sig')))
            if not isinstance(d,dict) or d.get('version')!=1: raise ValueError()
            empty={'timers':list,'kills':list,'totals':dict,'stamina':dict,'prices':list,'watchlist':dict,'alerts':list,'events':list,'requests':dict,'catalog':list}
            if any(type(d.get(k)) is not t for k,t in empty.items()): raise ValueError()
            for t in d['timers']:
                label(t['id']);label(t['label']);integer(t['duration_seconds'],1,604800);instant(t['ends_at'])
                if t['status'] not in ('active','completed','cancelled'): raise ValueError()
            for p in d['prices']:
                label(p['id']);label(p['world_id']);item_name(p['item']);price_gp(p['price_gp']);instant(p['at']);self._offer(p['offer_type'])
            d['catalog']=merge_catalog(d['catalog'])
            self._cache=((st.st_mtime_ns,st.st_size),json.dumps(d,ensure_ascii=False))
            return d
        except (ValueError,TypeError,KeyError,UnicodeError):
            raise ValueError('Dados do Assistente inválidos ou de versão desconhecida. Arquivo preservado; restaure um backup válido.') from None

    def _save(self, data):
        validate_state(data)
        serialized=json.dumps(data,ensure_ascii=False,separators=(',',':')).encode('utf-8')
        if len(serialized)>MAX_STORE_BYTES:
            raise ValueError('Histórico do Assistente atingiu o limite de 16 MiB. Exporte um backup antes de arquivar seus dados; nenhuma alteração foi gravada.')
        self.folder.mkdir(parents=True,exist_ok=True)
        tmp=self.path.with_name(self.path.name+'.tmp')
        try:
            with tmp.open('w',encoding='utf-8') as f:
                f.write(serialized.decode('utf-8'));f.flush();os.fsync(f.fileno())
            os.replace(tmp,self.path)
            st=self.path.stat();self._cache=((st.st_mtime_ns,st.st_size),serialized.decode('utf-8'))
        finally:
            tmp.unlink(missing_ok=True)

    def context(self):
        try:
            d=json.loads((self.folder/'meus_personagens.json').read_text(encoding='utf-8-sig'))
            p=next((p for p in d['lista'] if p['nome']==d.get('atual')), {})
            return {'character_id':p.get('nome',''),'world_id':p.get('mundo',''),'level':p.get('level')}
        except (OSError,ValueError,KeyError,TypeError): return {'character_id':'','world_id':'','level':None}

    def _profile(self, ctx):
        name=label(ctx.get('character_id'))
        try:
            d=json.loads((self.folder/'meus_personagens.json').read_text(encoding='utf-8-sig'))
            if not any(p.get('nome')==name for p in d['lista']): raise ValueError()
        except (OSError,ValueError,KeyError,TypeError): raise ValueError('O personagem capturado não está mais cadastrado. Selecione um personagem.') from None
        return name

    @staticmethod
    def _offer(value):
        if value not in ('buy','sell','traded'): raise ValueError('Escolha compra, venda ou negociado.')
        return value

    def _boss(self,d,identity):
        """Nome exato, depois palavras contidas, depois parecido (erro de transcrição); nunca escolhe entre dois."""
        key=boss_key(label(identity));keys={}
        for b in d['catalog']:
            for n in (b['boss_id'],b['name'],*b['aliases']):keys.setdefault(boss_key(n),{})[b['boss_id']]=b
        def one(found):
            if len(found)==1:return next(iter(found.values()))
            raise ValueError(f'Qual boss? {", ".join(sorted(b["name"] for b in found.values())[:5])}.')
        if key in keys:return one(keys[key])
        if key=='oberom':key='oberon'
        contained={i:b for k,bs in keys.items() if re.search(rf'\b{re.escape(key)}\b',k) for i,b in bs.items()}
        if contained:return one(contained)
        close=difflib.get_close_matches(key,keys,n=5,cutoff=.6)
        sure={i:b for k in close if difflib.SequenceMatcher(None,key,k).ratio()>=.85 for i,b in keys[k].items()}
        if sure:return one(sure)
        guesses=sorted({b['name'] for k in close for b in keys[k].values()})[:3]
        raise ValueError(f'Não achei o boss "{identity}". '+(f'Você quis dizer: {", ".join(guesses)}?' if guesses else 'Confira o nome na aba Bosstiary.'))

    def _boss_view(self,d,boss,char,now):
        kills=[k for k in d['kills'] if k['character_id']==char and k['boss_id']==boss['boss_id'] and not k['undone']]
        last=max((instant(k['at']) for k in kills),default=None)
        total=d['totals'].get(char,{}).get(boss['boss_id'],0)
        targets=GOALS.get(boss['category'],[]);target=next((g for g in targets if g>total),None)
        available=last+timedelta(minutes=boss['cooldown_minutes']) if last and boss['cooldown_type']=='fixed' and boss['cooldown_minutes'] is not None else None
        return {**boss,'progress':total,'real_kills':len(kills),'last_killed_at':iso(last) if last else None,
                'available_at':iso(available) if available else None,'remaining_seconds':max(0,(available-now).total_seconds()) if available else None,
                'goals':targets,'next_goal':target,'missing':target-total if target else None,'complete':bool(targets and total>=targets[-1])}

    def _timer(self,d,args,ctx,now,history=False):
        timers=[t for t in d['timers'] if (not t['character_id'] or t['character_id']==ctx.get('character_id')) and (history or t['status']=='active' and instant(t['ends_at'])>now)]
        if args.get('timer_id'): timers=[t for t in timers if t['id']==args['timer_id']]
        elif args.get('last'): timers=timers[-1:]
        elif args.get('label'): timers=[t for t in timers if t['label'].casefold()==label(args['label']).casefold()]
        elif args.get('duration_seconds'): timers=[t for t in timers if t['duration_seconds']==args['duration_seconds']]
        if len(timers)!=1: raise ValueError('Qual timer? Selecione o ID na lista.' if timers else 'Nenhum timer correspondente.')
        return timers[0]

    def execute(self,intent,args=None,context=None,request_id=None,source="manual"):
        if not isinstance(intent,str) or not isinstance(args or {},dict): raise ValueError('Comando inválido.')
        args=args or {}
        if source not in ('manual','voice'):raise ValueError('Origem inválida.')
        if context is not None and not isinstance(context,dict):raise ValueError('Contexto inválido.')
        for flag in ('personal','last','include_active','boosted'):
            if flag in args and type(args[flag]) is not bool:raise ValueError('Confirmação inválida.')
        if intent not in FIELDS or set(args)-FIELDS[intent]: raise ValueError('Ação ou campos não permitidos.')
        ctx=deepcopy(context if context is not None else self.context());now=instant(self.clock())
        if len(json.dumps(args,ensure_ascii=False))>32000: raise ValueError('Comando muito grande.')
        with LOCK:
            data=self._read()
            digest=hashlib.sha256(json.dumps([intent,args,ctx,source],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            if request_id is not None:
                label(request_id)
                previous=data['requests'].get(request_id)
                if previous:
                    if previous['hash']!=digest: raise ValueError('request_id reutilizado com outro comando.')
                    return deepcopy(previous['result'])
            result,write=self._run(data,intent,deepcopy(args),ctx,now)
            if write:
                event_id=uuid.uuid4().hex
                if intent=='market.price.add':
                    result['observation']['source']=source
                    result['observation']['event_id']=event_id
                data['events'].append({'id':event_id,'entity_id':result.get('observation',{}).get('id'),'intent':intent,'at':iso(now),'character_id':ctx.get('character_id'),'world_id':ctx.get('world_id'),'arguments':args,'source':source,**result.pop('_audit',{})})
                if request_id: data['requests'][request_id]={'hash':digest,'result':result}
                self._save(data)
            return deepcopy(result)

    def _run(self,d,action,p,ctx,now):
        if action=='history':
            return {'events':[e for e in d['events'] if e['character_id'] in (None,'',ctx.get('character_id'))][-200:]},False
        if action.startswith('shared.'):
            levels=p.get('party_levels')
            reference=integer(p.get('reference_level',ctx.get('level'))) if action=='shared.range' or p.get('include_active') else None
            if action=='shared.range': return {'range':list(faixa_shared(reference)),'reference_level':reference,'source':RULES['shared'],'note':'Compatibilidade por level; distância e participação não verificadas.'},False
            if not isinstance(levels,list) or not 1<=len(levels)<=20: raise ValueError('Informe de 1 a 20 levels da party.')
            levels=[integer(v) for v in levels]
            if p.get('include_active'): levels.append(reference)
            if len(levels)<2: raise ValueError('Informe pelo menos dois levels.')
            compatible=3*min(levels)>=2*max(levels)
            return {'compatible':compatible,'range':[(2*max(levels)+2)//3,3*min(levels)//2],'levels':levels,'source':RULES['shared'],'note':'Somente compatibilidade por level.'},False
        if action.startswith('timer.'):
            if action=='timer.list':
                timers=[{**t,'remaining_seconds':max(0,(instant(t['ends_at'])-now).total_seconds())} for t in d['timers'] if not t['character_id'] or t['character_id']==ctx.get('character_id')]
                return {'timers':timers},False
            if action in ('timer.create','timer.repeat'):
                if action=='timer.repeat':
                    old=self._timer(d,p,ctx,now,True);p={'duration_seconds':old['duration_seconds'],'label':old['label'],'personal':bool(old['character_id'])}
                seconds=integer(p.get('duration_seconds'),1,604800)
                char=self._profile(ctx) if p.get('personal') is True else None
                t={'id':uuid.uuid4().hex,'label':label(p.get('label') or f'{seconds} segundos'),'duration_seconds':seconds,'character_id':char,'ends_at':iso(now+timedelta(seconds=seconds)),'created_at':iso(now),'status':'active','alerted':False}
                d['timers'].append(t);return {'timer':t},True
            t=self._timer(d,p,ctx,now,action=='timer.get')
            if action=='timer.get': return {'timer':{**t,'remaining_seconds':max(0,(instant(t['ends_at'])-now).total_seconds())}},False
            if action=='timer.cancel': t['status']='cancelled'
            elif action=='timer.extend':
                seconds=integer(p.get('delta_seconds'),1,604800)
                t['ends_at']=iso(instant(t['ends_at'])+timedelta(seconds=seconds));t['duration_seconds']+=seconds
                integer(t['duration_seconds'],1,604800)
            elif action=='timer.edit':
                if 'label' in p:t['label']=label(p['label'])
                if 'duration_seconds' in p:
                    t['duration_seconds']=integer(p['duration_seconds'],1,604800);t['ends_at']=iso(now+timedelta(seconds=t['duration_seconds']))
            else: raise ValueError('Ação de timer desconhecida.')
            return {'timer':t,'operation':action},True
        if action=='boss.catalog': return {'version':d['catalog_version'],'bosses':d['catalog']},False
        if action=='boss.catalog.import':
            entries=p.get('bosses')
            if not isinstance(entries,list) or not 1<=len(entries)<=100: raise ValueError('Importe entre 1 e 100 bosses por vez.')
            cleaned=[]
            for b in entries:
                if not isinstance(b,dict): raise ValueError('Boss inválido.')
                bid=label(b.get('boss_id'))
                if not re.fullmatch('[a-z0-9-]{1,80}',bid): raise ValueError('ID de boss inválido.')
                name=label(b.get('name'));aliases=b.get('aliases',[])
                if not isinstance(aliases,list) or len(aliases)>10: raise ValueError('Aliases inválidos.')
                aliases=[label(v) for v in aliases];category=b.get('category','unknown');kind=b.get('cooldown_type','unknown')
                if category not in (*GOALS,'unknown','not_applicable') or kind not in ('fixed','unknown','server_save','event','spawn'): raise ValueError('Regra desconhecida.')
                minutes=integer(b.get('cooldown_minutes'),1,525600) if kind=='fixed' else None
                source=label(b.get('source'));verified=b.get('verified_at')
                if verified is not None:
                    try: datetime.strptime(verified,'%Y-%m-%d')
                    except (ValueError,TypeError): raise ValueError('Data de verificação inválida.') from None
                if kind=='fixed' and (b.get('status')!='verified' or not verified or not source.startswith('https://')): raise ValueError('Cooldown fixo exige fonte HTTPS, data e status verified.')
                cleaned.append(dict(boss_id=bid,name=name,aliases=aliases,category=category,cooldown_type=kind,cooldown_minutes=minutes,source=source,verified_at=verified,status=b.get('status','unverified')))
            for b in cleaned:d['catalog']=[x for x in d['catalog'] if x['boss_id']!=b['boss_id']]+[b]
            d['catalog_version']+=1;return {'imported':len(cleaned),'version':d['catalog_version']},True
        if action.startswith(('boss.','bosstiary.')):
            char=self._profile(ctx)
            if action=='boss.cooldown.list': return {'bosses':[self._boss_view(d,b,char,now) for b in d['catalog']]},False
            b=self._boss(d,p.get('boss_id'));bid=b['boss_id'];totals=d['totals'].setdefault(char,{})
            if action in ('bosstiary.get','boss.cooldown.get'):return {'boss':self._boss_view(d,b,char,now)},False
            if action=='boss.kill':
                at=instant(p.get('killed_at',now))
                if at>now:raise ValueError('Abate não pode estar no futuro.')
                if type(p.get('boosted',False)) is not bool: raise ValueError('Confirme se o boss Archfoe foi boosted elegível.')
                progress=3 if p.get('boosted') and b['category']=='archfoe' else 1
                d['kills'].append({'id':uuid.uuid4().hex,'character_id':char,'boss_id':bid,'at':iso(at),'progress':progress,'undone':False,'boost_source':'player' if p.get('boosted') else None,'boosted_eligible':p.get('boosted',False)})
                totals[bid]=totals.get(bid,0)+progress
            elif action in ('bosstiary.set_total','bosstiary.increment'):
                amount=integer(p.get('total_kills') if action.endswith('set_total') else p.get('delta_kills'),0 if action.endswith('set_total') else 1,1000000)
                totals[bid]=amount if action.endswith('set_total') else totals.get(bid,0)+amount
            elif action in ('boss.kill.undo','boss.kill.correct_time'):
                kills=[k for k in d['kills'] if k['character_id']==char and k['boss_id']==bid and not k['undone'] and (not p.get('event_id') or k['id']==p['event_id'])]
                if not kills: raise ValueError('Nenhum abate correspondente.')
                k=kills[-1]
                if action.endswith('undo'):k['undone']=True;totals[bid]=max(0,totals.get(bid,0)-k['progress'])
                else:
                    at=instant(p.get('corrected_at'))
                    if at>now:raise ValueError('Abate não pode estar no futuro.')
                    k['at']=iso(at)
            elif action=='boss.alert':
                view=self._boss_view(d,b,char,now)
                if not view['available_at']:raise ValueError('Cooldown desconhecido. Não é possível criar alerta confiável.')
                if any(v['kind']=='boss' and v.get('boss_id')==bid and v['character_id']==char and v['at']==view['available_at'] and not v.get('cancelled') for v in d['alerts']):return {'boss':view},False
                d['alerts'].append({'id':uuid.uuid4().hex,'kind':'boss','boss_id':bid,'character_id':char,'world_id':None,'at':view['available_at'],'message':b['name']+' disponível (estimativa).','fired':False})
            elif action=='boss.cooldown.set':
                b.update(cooldown_type='fixed',cooldown_minutes=integer(p.get('cooldown_minutes'),1,525600),status='player',
                         source='Informado pelo jogador',verified_at=instant(now).astimezone(LOCAL).date().isoformat())
            else: raise ValueError('Ação de boss desconhecida.')
            view=self._boss_view(d,b,char,now)
            if action in ('boss.kill','boss.kill.correct_time','boss.kill.undo'):
                for alert in d['alerts']:
                    if alert['kind']=='boss' and alert.get('boss_id')==bid and alert['character_id']==char:
                        if action=='boss.kill.undo' or not view['available_at']:alert['cancelled']=True
                        else:
                            previous_at=alert['at'];alert['at']=view['available_at'];alert['cancelled']=False
                            if action=='boss.kill' or action=='boss.kill.correct_time' and previous_at!=view['available_at'] and instant(view['available_at'])>now:alert['fired']=False
            return {'boss':view},True
        if action.startswith('stamina.'):
            char=self._profile(ctx);ref=d['stamina'].get(char)
            if action in ('stamina.logout','stamina.correct'):
                minutes=integer(p.get('stamina_minutes'),0,2520);at=instant(p.get('logged_out_at',p.get('reference_at',now)))
                if at>now:raise ValueError('Referência declarada não pode estar no futuro. Use projeção hipotética.')
                ref={'stamina_minutes':minutes,'reference_at':iso(at),'offline':True};d['stamina'][char]=ref
                for alert in d['alerts']:
                    if alert['kind']=='stamina' and alert['character_id']==char and not alert['fired']:alert['cancelled']=True
                return {'stamina':ref,'note':'Offline declarado; estimativa sem leitura do jogo.'},True
            if action=='stamina.reverse':
                target=integer(p.get('desired_stamina_minutes'),0,2520);start=integer(p.get('starting_stamina_minutes',ref['stamina_minutes'] if ref else None),0,2520)
                return {'at':iso(instant(p.get('desired_at'))-timedelta(minutes=recovery_minutes(start,target))),'note':'Último logout estimado; pressupõe offline contínuo.'},False
            if action=='stamina.project' and ('starting_stamina_minutes' in p or 'logged_out_at' in p):
                ref={'stamina_minutes':integer(p.get('starting_stamina_minutes',ref['stamina_minutes'] if ref else None),0,2520),'reference_at':iso(p.get('logged_out_at')),'offline':True}
            if not ref: raise ValueError('Registre stamina e horário de logout primeiro.')
            if action=='stamina.get':
                at=instant(ref['reference_at']);elapsed=max(0,(now-at).total_seconds()/60);start=ref['stamina_minutes']
                if not ref['offline']:return {'stamina':ref,'online_minutes':int(elapsed),'note':'Online declarado; o app não sabe quanto você gastou.'},False
                return {'stamina':ref,'estimate_minutes':stamina_at(start,elapsed),'green_at':iso(at+timedelta(minutes=recovery_minutes(start,2340))),
                        'full_at':iso(at+timedelta(minutes=recovery_minutes(start,2520))),'note':'Valores declarados; projeção exige offline contínuo.'},False
            if action=='stamina.login':
                at=instant(p.get('logged_in_at',now))
                if not instant(ref['reference_at'])<=at<=now: raise ValueError('Horário de login inválido.')
                ref['stamina_minutes']=stamina_at(ref['stamina_minutes'],(at-instant(ref['reference_at'])).total_seconds()/60) if ref['offline'] else ref['stamina_minutes']
                ref.update(offline=False,reference_at=iso(at))
                for alert in d['alerts']:
                    if alert['kind']=='stamina' and alert['character_id']==char and not alert['fired']:alert['cancelled']=True
                return {'stamina':ref,'note':'Online declarado. Informe valor real para novo cálculo.'},True
            if not ref['offline']:raise ValueError('Personagem declarado online. Registre o valor real no próximo logout.')
            if action=='stamina.project':
                at=instant(p.get('target_datetime',now));elapsed=(at-instant(ref['reference_at'])).total_seconds()/60
                if elapsed<0:raise ValueError('Projeção anterior à referência.')
                return {'stamina_minutes':stamina_at(ref['stamina_minutes'],elapsed),'at':iso(at),'note':'Estimativa se permanecer offline; não considera resting areas ou itens.'},False
            if action in ('stamina.time_to','stamina.alert'):
                target=integer(p.get('target_stamina_minutes'),0,2520);at=instant(ref['reference_at'])+timedelta(minutes=recovery_minutes(ref['stamina_minutes'],target))
                if action=='stamina.alert':d['alerts'].append({'id':uuid.uuid4().hex,'kind':'stamina','character_id':char,'world_id':None,'at':iso(at),'message':f'Stamina estimada em {target//60}h{target%60:02d}, se permaneceu offline.','fired':False})
                return {'at':iso(at),'target_stamina_minutes':target},action=='stamina.alert'
            raise ValueError('Ação de stamina desconhecida.')
        if action.startswith('market.'):
            if ctx.get('character_id'):self._profile(ctx)
            world=label(ctx.get('world_id'));offer=self._offer(p.get('offer_type','sell'))
            if action=='market.alert.list': return {'alerts':[v for v in d['alerts'] if v.get('world_id')==world and v['kind']=='market']},False
            if action=='market.watch.list':return {'items':d['watchlist'].get(world,['Tibia Coin','Silver Token','Gold Token'])},False
            if action in ('market.price.correct','market.price.delete'):
                candidates=[v for v in d['prices'] if v['world_id']==world and not v.get('deleted') and (v['id']==p.get('observation_id') if p.get('observation_id') else v['item']==item_name(p.get('item')) and v['offer_type']==offer)]
                if not candidates: raise ValueError('Registro não encontrado neste mundo.')
                obs=candidates[-1];before=deepcopy(obs);label(p.get('reason'))
                if action.endswith('delete'):obs['deleted']=True
                else:obs['price_gp']=price_gp(p.get('price'))
                return {'observation':obs,'_audit':{'before':before,'after':deepcopy(obs)}},True
            item=item_name(p.get('item'))
            if action=='market.item.watch':
                watched=d['watchlist'].setdefault(world,['Tibia Coin','Silver Token','Gold Token'])
                if item not in watched: watched.append(item)
                return {'items':watched},True
            if action=='market.price.add':
                at=instant(p.get('observed_at',now))
                if at>now:raise ValueError('Preço observado não pode estar no futuro.')
                obs={'id':uuid.uuid4().hex,'world_id':world,'item':item,'offer_type':offer,'price_gp':price_gp(p.get('price')),'at':iso(at),'deleted':False}
                d['prices'].append(obs)
                for alert in d['alerts']:
                    if alert['kind']=='market' and alert['world_id']==world and alert['item']==item and alert['offer_type']==offer and not alert['fired']:
                        if (obs['price_gp']<alert['threshold'] if alert['direction']=='below' else obs['price_gp']>alert['threshold']):alert['matched_at']=iso(now)
                return {'observation':obs},True
            if action=='market.alert.create':
                if p.get('direction') not in ('below','above'):raise ValueError('Escolha abaixo ou acima.')
                alert={'id':uuid.uuid4().hex,'kind':'market','character_id':None,'world_id':world,'item':item,'offer_type':offer,'threshold':price_gp(p.get('price')),'direction':p['direction'],'fired':False,'matched_at':None}
                d['alerts'].append(alert);return {'alert':alert},True
            if action=='market.stats':
                days=integer(p.get('days',30),1,36500);cutoff=now-timedelta(days=days)
                rows=sorted([v for v in d['prices'] if not v.get('deleted') and v['world_id']==world and v['item']==item and v['offer_type']==offer and instant(v['at'])>=cutoff],key=lambda v:v['at'])
                values=[r['price_gp'] for r in rows];n=len(values)
                result={'item':item,'world_id':world,'offer_type':offer,'days':days,'count':n,'insufficient':n<3,'observations':rows,'source':'Observações locais privadas; sem preço em tempo real.'}
                result.update(median=statistics.median(values) if n else None,mean=statistics.mean(values) if n else None,minimum=min(values) if n else None,maximum=max(values) if n else None,spread=max(values)-min(values) if n else None,variation_percent=round(100*(values[-1]-values[0])/values[0],2) if n>1 else None,age_seconds=(now-instant(rows[-1]['at'])).total_seconds() if n else None)
                if p.get('price') is not None:
                    price=price_gp(p['price']);result['comparison']='Amostra insuficiente para avaliar.' if n<3 else ('Abaixo da mediana local.' if price<result['median'] else 'Acima da mediana local.' if price>result['median'] else 'Igual à mediana local.')
                return result,False
            raise ValueError('Ação de Market desconhecida.')
        raise ValueError('Intenção não permitida.')

    def poll(self):
        with LOCK:
            d=self._read();now=instant(self.clock());messages=[]
            for t in d['timers']:
                if t['status']=='active' and instant(t['ends_at'])<=now:
                    t['status']='completed';t['alerted']=True;messages.append({'id':t['id'],'message':f"Timer {t['label']} terminou.",'at':iso(now)})
            for alert in d['alerts']:
                ready=alert.get('matched_at') if alert['kind']=='market' else alert.get('at')
                if not alert['fired'] and not alert.get('cancelled') and ready and instant(ready)<=now:
                    alert['fired']=True;messages.append({'id':alert['id'],'message':alert.get('message',f"Preço observado de {alert.get('item','item')} atingiu seu limite."),'at':iso(now)})
            if messages:
                for m in messages:d['events'].append({'id':uuid.uuid4().hex,'intent':'alert.fired','at':m['at'],'character_id':None,'world_id':None,'arguments':{'message':m['message'],'alert_id':m['id']}})
                self._save(d)
            return messages

# Only these typed fields may reach a domain operation, from UI or NLU.
FIELDS = {
 'history':set(),'shared.range':{'reference_level'},'shared.check':{'party_levels','reference_level','include_active'},'shared.party_range':{'party_levels','reference_level','include_active'},
 'timer.create':{'duration_seconds','label','personal'},'timer.list':set(),
 'timer.get':{'timer_id','label','duration_seconds','last'},'timer.cancel':{'timer_id','label','duration_seconds','last'},
 'timer.extend':{'timer_id','label','duration_seconds','last','delta_seconds'},'timer.repeat':{'timer_id','label','duration_seconds','last'},'timer.edit':{'timer_id','label','duration_seconds'},
 'boss.catalog':set(),'boss.catalog.import':{'bosses'},'boss.kill':{'boss_id','killed_at','boosted'},'boss.cooldown.get':{'boss_id'},'boss.cooldown.list':set(),
 'bosstiary.get':{'boss_id'},'bosstiary.set_total':{'boss_id','total_kills'},'bosstiary.increment':{'boss_id','delta_kills'},'boss.kill.undo':{'boss_id','event_id'},'boss.kill.correct_time':{'boss_id','event_id','corrected_at'},'boss.alert':{'boss_id'},'boss.cooldown.set':{'boss_id','cooldown_minutes'},
 'stamina.logout':{'stamina_minutes','logged_out_at'},'stamina.correct':{'stamina_minutes','reference_at'},'stamina.login':{'logged_in_at'},'stamina.get':set(),
 'stamina.project':{'target_datetime','starting_stamina_minutes','logged_out_at'},'stamina.time_to':{'target_stamina_minutes'},'stamina.reverse':{'desired_stamina_minutes','desired_at','starting_stamina_minutes'},'stamina.alert':{'target_stamina_minutes'},
 'market.price.add':{'item','price','offer_type','observed_at'},'market.stats':{'item','price','offer_type','days'},'market.price.correct':{'observation_id','item','price','offer_type','reason'},'market.price.delete':{'observation_id','item','offer_type','reason'},'market.item.watch':{'item'},'market.watch.list':set(),'market.alert.create':{'item','offer_type','direction','price'},'market.alert.list':set()
}

LABELS = {
 'history':'Consultar histórico', 'shared.range':'Consultar shared', 'shared.check':'Verificar levels da party', 'shared.party_range':'Consultar shared da party',
 'timer.create':'Criar timer', 'timer.list':'Listar timers', 'timer.get':'Consultar timer', 'timer.cancel':'Cancelar timer',
 'timer.extend':'Adicionar tempo ao timer', 'timer.repeat':'Repetir timer', 'timer.edit':'Editar timer',
 'boss.catalog':'Consultar catálogo de bosses', 'boss.catalog.import':'Importar catálogo de bosses', 'boss.kill':'Registrar abate',
 'boss.cooldown.get':'Consultar cooldown', 'boss.cooldown.list':'Consultar cooldowns', 'boss.cooldown.set':'Definir cooldown',
 'bosstiary.get':'Consultar Bosstiary', 'bosstiary.set_total':'Definir progresso Bosstiary', 'bosstiary.increment':'Adicionar progresso Bosstiary',
 'boss.kill.undo':'Desfazer abate', 'boss.kill.correct_time':'Corrigir horário do abate', 'boss.alert':'Avisar quando o boss liberar',
 'stamina.logout':'Registrar logout', 'stamina.correct':'Corrigir stamina', 'stamina.login':'Registrar login', 'stamina.get':'Consultar stamina',
 'stamina.project':'Projetar stamina', 'stamina.time_to':'Quando a stamina chega a', 'stamina.reverse':'Calcular quando deslogar', 'stamina.alert':'Avisar quando a stamina chegar a',
 'market.price.add':'Registrar preço', 'market.stats':'Consultar preços', 'market.price.correct':'Corrigir preço', 'market.price.delete':'Apagar preço',
 'market.item.watch':'Acompanhar item', 'market.watch.list':'Listar itens acompanhados', 'market.alert.create':'Criar alerta de preço', 'market.alert.list':'Listar alertas de preço'
}


def describe(intent, args):
    parts = [LABELS.get(intent, 'Comando não reconhecido')]
    for key in ('boss_id', 'item', 'label'):
        if args.get(key):
            value = args[key]
            if key == 'boss_id':
                value = next((b['name'] for b in SEED if b['boss_id'] == value), value)
            parts.append(str(value))
    for key in ('stamina_minutes', 'target_stamina_minutes', 'desired_stamina_minutes', 'starting_stamina_minutes'):
        if args.get(key) is not None:
            minutes = args[key]
            parts.append(f'{minutes // 60}h{minutes % 60:02d}')
    for key in ('duration_seconds', 'delta_seconds'):
        if args.get(key) is not None:
            seconds = args[key]
            parts.append(f'{seconds // 60} min' if seconds % 60 == 0 else f'{seconds} s')
    if args.get('cooldown_minutes') is not None: parts.append(f"{args['cooldown_minutes']} min")
    if args.get('reference_level') is not None: parts.append(f"level {args['reference_level']}")
    if args.get('party_levels'): parts.append('levels ' + ', '.join(map(str, args['party_levels'])))
    for key in ('total_kills', 'delta_kills'):
        if args.get(key) is not None: parts.append(f"{args[key]} de progresso")
    if args.get('boosted'): parts.append('boosted')
    if args.get('price') is not None: parts.append(str(args['price']))
    if args.get('offer_type'): parts.append({'buy':'compra', 'sell':'venda', 'traded':'negociado'}.get(args['offer_type'], args['offer_type']))
    if args.get('direction'): parts.append({'below':'abaixo', 'above':'acima'}.get(args['direction'], args['direction']))
    if args.get('days') is not None: parts.append(f"{args['days']} dias")
    for key in ('killed_at', 'corrected_at', 'logged_out_at', 'logged_in_at', 'reference_at', 'target_datetime', 'desired_at', 'observed_at'):
        if args.get(key): parts.append(instant(args[key]).astimezone(LOCAL).strftime('%d/%m às %H:%M'))
    return ' · '.join(parts)


def local_datetime(text, now):
    from voice.spike_assistente import normalize
    text=normalize(text);local=instant(now).astimezone(LOCAL)
    if text in ('agora','hoje'):return iso(now)
    if text in ('ha meia hora','meia hora atras'):return iso(instant(now)-timedelta(minutes=30))
    m=re.fullmatch(r'ha (\d+) (minutos?|horas?)',text)
    if m:return iso(instant(now)-timedelta(minutes=int(m[1])*(60 if m[2].startswith('hora') else 1)))
    m=re.fullmatch(r'(hoje|amanha|ontem)?\s*(?:as?|pelas?)\s*(\d{1,2})(?:\s*(?:h|horas?))?(?:\s+(\d{1,2})(?:\s+minutos?)?)?',text)
    if not m:raise ValueError('Confirme a data completa e o horário, por exemplo amanhã às 13.')
    day=m[1];hour=int(m[2]);minute=int(m[3] or 0)
    if hour>23 or minute>59:raise ValueError('Horário inválido.')
    at=local.replace(hour=hour,minute=minute,second=0,microsecond=0)+timedelta(days={'amanha':1,'ontem':-1}.get(day,0))
    if day is None and at>local:raise ValueError('Esse horário ainda não ocorreu hoje. Confirme hoje ou ontem.')
    return iso(at)

def parse(text, now=None):
    import unicodedata
    from voice.spike_assistente import normalize, negated, number_from, duration_from, duration_seconds
    if not isinstance(text,str) or not text.strip() or len(text)>500:raise ValueError('Comando vazio ou muito longo.')
    if negated(text):raise ValueError('Tudo bem. Nenhuma ação executada.')
    now=instant(now or datetime.now(UTC))
    raw=''.join(c for c in unicodedata.normalize('NFD',text.strip().rstrip('.?!')) if not unicodedata.combining(c))
    # Tolerância: pontuação fora de números ("36.5k" e "22:30" ficam), "eu"/"por favor" nas pontas e espaços extras não mudam o comando.
    raw=' '.join(re.sub(r'(?<!\d)[,.;:!?"“”()]+|[,.;:!?"“”()]+(?!\d)',' ',raw).split())
    raw=re.sub(r'^(?:(?:hey|ei|hei|ok|entao|bom|olha|tipo|ai|eu|por favor|tibia tudo)\s+)+','',raw,flags=re.I)
    raw=re.sub(r'(?:\s+(?:por favor|pra mim|ai|obrigado))+$','',raw,flags=re.I)
    t=normalize(raw)
    def match(pattern):return re.fullmatch(pattern,raw,flags=re.I)
    def number(value):
        n=number_from(normalize(value))
        if n is None:raise ValueError('Número ambíguo. Confirme usando algarismos.')
        return n
    def duration(value):
        d=duration_from(normalize(value))
        if d:return duration_seconds(d)
        m=re.fullmatch(r'(.+?) ?(?:horas?|h)(?: e (.+?) minutos?)?',normalize(value))
        if m:return number(m[1])*3600+(number(m[2])*60 if m[2] else 0)
        raise ValueError('Informe duração clara em horas, minutos ou segundos.')
    if 'unk' in t.split():return None
    if re.search(r'\b(?:talvez|ou|quinze cinquenta)\b',t):raise ValueError('Comando ambíguo. Confirme os valores e a operação.')
    if t in ('quais timers estao rodando','listar timers','meus timers','mostra timers'):return 'timer.list',{}
    m=match(r'(?:adiciona|adicione) (.+?) (?:ao|no) timer (?:do |chamado )?(.+)')
    if m:return 'timer.extend',{'label':m[2],'delta_seconds':duration(m[1])}
    m=match(r'(?:quanto falta|quanto tempo falta) (?:no |naquele |pro )?timer(?: (?:do |chamado |de )?(.+))?')
    if m:return 'timer.get',({'label':m[1]} if m[1] else {})
    m=match(r'(?:cancela|cancelar|cancele|repete|repetir) (?:o )?(ultimo )?(?:timer|alarme|temporizador)(?: (?:chamado |do |de )?(.+))?')
    if m:
        args={'last':True} if m[1] else {}
        if m[2]:
            try:args['duration_seconds']=duration(m[2])
            except ValueError:args['label']=m[2]
        return ('timer.repeat' if t.startswith(('repete','repetir')) else 'timer.cancel'),args
    m=match(r'(?:(?:cria|criar|coloca|inicia|iniciar|novo|nova|gera|gere|gerar|ligar|liga|ligue|bota|bote|poe|faz|faca|marca|marque|programa) (?:um |uma )?)?(?:timer|time|alarme|temporizador|cronometro)(?: chamado (.+?))? (?:de |por |pra |para )?(.+)')
    if not m and t.startswith('me avisa daqui a '):return 'timer.create',{'duration_seconds':duration(raw[len('me avisa daqui a '):])}
    if m:
        args={'duration_seconds':duration(m[2])}
        if m[1]:args['label']=m[1]
        return 'timer.create',args
    if any(s in t.split() for s in ('shared','share','shareio','cher','xer','compartilhado','compartilhada')) or 'divide experiencia' in t or 'compartilho experiencia' in t:
        nums=[int(v) for v in re.findall(r'\b\d+\b',t)]
        if re.search(r'(?:entra|pode|compartilhar|comigo)',t) and len(nums)==1:return 'shared.check',{'party_levels':nums,'include_active':True}
        if len(nums)>1:return 'shared.check',{'party_levels':nums}
        return 'shared.range',({'reference_level':nums[0]} if nums else {})
    m=match(r'(?:meu level e |se eu fosse |level )(\d+).*')
    if m:return 'shared.range',{'reference_level':int(m[1])}
    if re.search(r'\batualiza (?:meu )?(?:level|nivel)\b',t):raise ValueError('Confirme a alteração do level no formulário Shared XP; consultas não alteram o cadastro.')
    m=match(r'(?:(?:matei|matamos|derrubei|derrubamos|acabei de matar|acabamos de matar) (?:o |a )?|(?:acabei de fazer|acabamos de fazer) (?:o |a )?|(?:fiz|fizemos) (?:o |a ))(.+?)(?: (agora|ha .+|ontem .+|hoje .+|as .+))?')
    if m:return 'boss.kill',{'boss_id':m[1],'killed_at':local_datetime(m[2] or 'agora',now)}
    m=match(r'(?:atualiza|atualizar) (?:meu |minha )?(.+?) para (.+?) kills')
    if m:return 'bosstiary.set_total',{'boss_id':m[1],'total_kills':number(m[2])}
    m=match(r'(?:adiciona|adicionar) (.+?) kills (?:no |na |ao )?(.+)')
    if m:return 'bosstiary.increment',{'boss_id':m[2],'delta_kills':number(m[1])}
    m=match(r'(?:desfaz|desfazer) a ultima kill (?:do |da )?(.+)')
    if m:return 'boss.kill.undo',{'boss_id':m[1]}
    m=match(r'corrige:? matei (?:o |a )?(.+?) (ontem .+|hoje .+|ha .+|as .+)')
    if m:return 'boss.kill.correct_time',{'boss_id':m[1],'corrected_at':local_datetime(m[2],now)}
    m=match(r'(?:quanto falta (?:pro |para o |para a )|me avisa quando (?:o |a )?)(.+?)(?: liberar)?')
    if m:return ('boss.alert' if t.startswith('me avisa') else 'boss.cooldown.get'),{'boss_id':m[1]}
    m=match(r'(?:quantas kills tenho (?:no |na )|quantas faltam para completar o bosstiary (?:do |da ))(.+)')
    if m:return 'bosstiary.get',{'boss_id':m[1]}
    if t in ('quais bosses estao disponiveis','mostra os bosses do meu personagem','meus bosses'):return 'boss.cooldown.list',{}
    m=match(r'(?:define |coloca )?(?:o )?cooldown (?:do |da |de )?(.+?) (?:e |eh |para |pra )(?:de )?(.+)')
    if m:return 'boss.cooldown.set',{'boss_id':m[1],'cooldown_minutes':duration(m[2])//60}
    if re.fullmatch(r'(?:estou |to |acabei de |vou )?(?:logando|loguei|logar|entrei no jogo|entrando no jogo|registrar login)(?: agora)?',t):return 'stamina.login',{'logged_in_at':iso(now)}
    m=match(r'(?:estou deslogando agora[, ]*minha stamina esta em |desloguei (.+?) com )(.+)')
    if m:return 'stamina.logout',{'stamina_minutes':duration(m[2])//60,'logged_out_at':local_datetime(m[1] or 'agora',now)}
    m=match(r'(?:corrige minha stamina para|minha e?stamina (?:esta|ta)(?: em)?) (.+)')
    if m:return 'stamina.correct',{'stamina_minutes':duration(m[1])//60,'reference_at':iso(now)}
    m=match(r'(?:que horas minha stamina chega em|quando recupero) (\d+)(?: horas?)?')
    if m:return 'stamina.time_to',{'target_stamina_minutes':int(m[1])*60}
    if t=='quando recupero o bonus de stamina':return 'stamina.time_to',{'target_stamina_minutes':2340}
    if re.fullmatch(r'(?:qual e? ?(?:a )?minha e?stamina|quanto tenho de e?stamina|quanta e?stamina eu tenho)(?: agora)?',t):return 'stamina.get',{}
    m=re.search(r'\bquando\b.*\be?stamina\b.*\b(cheia|completa|full|verde|bonus)\b',t)
    if m:return 'stamina.time_to',{'target_stamina_minutes':2340 if m[1] in ('verde','bonus') else 2520}
    m=match(r'(amanha .+|hoje .+),? quanto terei de stamina')
    if m:return 'stamina.project',{'target_datetime':local_datetime(m[1],now)}
    m=match(r'se eu deslogar (.+?),? quanto terei (.+)')
    if m:return 'stamina.project',{'logged_out_at':local_datetime(m[1],now),'target_datetime':local_datetime(m[2],now)}
    m=match(r'qual o ultimo horario para deslogar e ficar com (\d+) horas (.+)')
    if m:return 'stamina.reverse',{'desired_stamina_minutes':int(m[1])*60,'desired_at':local_datetime(m[2],now)}
    if t in ('mostra historico','historico de acoes','historico do personagem'):return 'history',{}
    m=match(r'(?:adiciona|adicionar) (.+?) (?:a minha lista|na minha lista)')
    if m:return 'market.item.watch',{'item':m[1]}
    m=match(r'(?:corrige o ultimo registro (?:do |da )?)(.+?) para (.+)')
    if m:return 'market.price.correct',{'item':m[1],'price':m[2],'offer_type':'sell','reason':'Correção explícita por voz'}
    m=match(r'me avisa se (?:o |a )?(.+?) for registrado (abaixo|acima) de (.+)')
    if m:return 'market.alert.create',{'item':m[1],'offer_type':'sell','direction':'below' if m[2].lower()=='abaixo' else 'above','price':m[3]}
    m=match(r'(?:qual a mediana (?:do |da )?)(.+?)(?: nos ultimos (7|30|90) dias)?')
    if m:return 'market.stats',{'item':m[1],'offer_type':'sell','days':int(m[2] or 30)}
    # Fala livre de logout ("vou fazer logout agora, minha estamina está em 41 horas"); o ASR às vezes escreve "estamina".
    m=re.search(r'\b(?:logout|deslog\w*|sai\w* do jogo|offline)\b.*?\be?stamina (?:esta |ta |e |fica )?(?:em |com |de )?(.+)',t)
    if m:return 'stamina.logout',{'stamina_minutes':duration(m[1])//60,'logged_out_at':iso(now)}
    m=match(r'(?:registra |registrar )?(.+?) (?:ta |esta |a )(\d.*?)(?: (?:na |no )(compra|venda|negociado))?(?: no meu mundo)?')
    if m:
        item,price=m[1],m[2];offer={'compra':'buy','venda':'sell','negociado':'traded'}.get((m[3] or '').lower(),'sell')
        query=re.search(r'\s+(?:ta |esta )?(?:barato|caro).*$',price,re.I)
        if query:price=price[:query.start()].strip()
        if not re.fullmatch(r'\d[\d.,]*\s*(?:kk|k|gp|gold)?',price,re.I):return None  # "40 horas" não é preço: deixa a IA online tentar
        price_gp(price)
        return ('market.stats' if query else 'market.price.add'),{'item':item,'price':price,'offer_type':offer}
    return None


def span(seconds):
    """3h 12min, 45min ou 2d 4h: o mesmo formato do Boss Cooldowns do Tibia."""
    minutes=max(1,int(seconds+59)//60);days,hours,rest=minutes//1440,minutes//60%24,minutes%60
    return f'{days}d {hours}h' if days else f'{hours}h {rest}min' if hours else f'{rest}min'

def reply(result):
    if 'timer' in result:
        t=result['timer'];remaining=result['timer'].get('remaining_seconds')
        if remaining is not None:return f"Faltam {max(0,int(remaining+0.999))} segundos no timer {t['label']}."
        verb='cancelado' if t['status']=='cancelled' else 'estendido' if result.get('operation')=='timer.extend' else 'alterado' if result.get('operation')=='timer.edit' else 'iniciado'
        return f"Timer de {t['label']} {verb}."
    if 'timers' in result:return f"{sum(t['status']=='active' and t['remaining_seconds']>0 for t in result['timers'])} timers ativos. Consulte a lista na tela."
    if 'compatible' in result:return ('Compatível' if result['compatible'] else 'Incompatível')+' por level. '+result['note']
    if 'range' in result:return f"Seu shared vai do level {result['range'][0]} até {result['range'][1]}."
    if 'boss' in result:
        b=result['boss'];left=b['remaining_seconds']
        cooldown=f" Libera em {span(left)}." if left else ' Disponível.' if b['cooldown_minutes'] else ' Cooldown não informado.'
        goal=f" Faltam {b['missing']} para a próxima meta." if b['missing'] is not None else (' Bosstiary completo.' if b['complete'] else ' Meta não verificada.')
        return f"{b['name']}: {b['real_kills']} abates reais, {b['progress']} de progresso."+goal+cooldown
    if 'estimate_minutes' in result:
        m=result['estimate_minutes'];full=instant(result['full_at']).astimezone(LOCAL).strftime('%d/%m às %H:%M')
        return f"Stamina estimada: {m//60}h{m%60:02d}, se ficou offline. Cheia em {full}."
    if 'online_minutes' in result:
        m=result['stamina']['stamina_minutes'];return f"Online desde o login, que foi com {m//60}h{m%60:02d}. Registre o valor ao deslogar."
    if 'stamina_minutes' in result:return f"Stamina estimada: {result['stamina_minutes']//60}h{result['stamina_minutes']%60:02d}. Se permanecer offline."
    if 'at' in result:return 'Estimativa: '+instant(result['at']).astimezone(LOCAL).strftime('%d/%m às %H:%M')+'. Se permanecer offline.'
    if 'stamina' in result:return 'Referência de stamina registrada. '+result.get('note','')
    if 'observation' in result:return f"Preço registrado: {result['observation']['price_gp']} GP. Observação local privada."
    if 'count' in result:return f"{result['count']} observações locais. Mediana: {result['median']} GP. "+result.get('comparison',('Amostra insuficiente.' if result['insufficient'] else 'Sem preço em tempo real.'))
    if 'bosses' in result:return 'Consulte os bosses e os cooldowns verificados na tela.'
    return 'Concluído. Consulte os detalhes na tela.'

def validate_state(d):
    """Reject unknown/corrupt state before any mutation or backup replacement."""
    try:
        if not isinstance(d,dict) or d.get('version')!=1:raise ValueError()
        for key in ('timers','kills','prices','alerts','events','catalog'):
            if not isinstance(d.get(key),list):raise ValueError()
            ids=[]
            for row in d[key]:
                if not isinstance(row,dict):raise ValueError()
                if key!='catalog':ids.append(label(row['id']))
            if len(ids)!=len(set(ids)):raise ValueError()
        for key in ('totals','stamina','watchlist','requests'):
            if not isinstance(d.get(key),dict):raise ValueError()
        integer(d['catalog_version'])
        for t in d['timers']:
            label(t['label']);integer(t['duration_seconds'],1,604800);instant(t['ends_at']);instant(t['created_at'])
            if t['character_id'] is not None:label(t['character_id'])
            if t['status'] not in ('active','completed','cancelled') or type(t['alerted']) is not bool:raise ValueError()
        for k in d['kills']:
            label(k['boss_id']);label(k['character_id']);instant(k['at']);integer(k['progress'],1,3)
            if type(k['undone']) is not bool:raise ValueError()
        for char,totals in d['totals'].items():
            label(char)
            if not isinstance(totals,dict):raise ValueError()
            for bid,n in totals.items():label(bid);integer(n,0,1000000)
        for char,ref in d['stamina'].items():
            label(char);integer(ref['stamina_minutes'],0,2520);instant(ref['reference_at'])
            if type(ref['offline']) is not bool:raise ValueError()
        for world,items in d['watchlist'].items():
            label(world)
            if not isinstance(items,list):raise ValueError()
            for item in items:item_name(item)
        for p in d['prices']:
            label(p['world_id']);item_name(p['item']);price_gp(p['price_gp']);instant(p['at'])
            if p['offer_type'] not in ('buy','sell','traded') or type(p['deleted']) is not bool:raise ValueError()
        for b in d['catalog']:
            label(b['boss_id']);label(b['name']);label(b['source'])
            if not isinstance(b['aliases'],list) or len(b['aliases'])>10:raise ValueError()
            for alias in b['aliases']:label(alias)
            if b['category'] not in (*GOALS,'unknown','not_applicable') or b['cooldown_type'] not in ('fixed','unknown','server_save','event','spawn'):raise ValueError()
            if b['cooldown_type']=='fixed':
                integer(b['cooldown_minutes'],1,525600)
                if b['status'] not in ('verified','wiki','player') or b['status']!='player' and not b['source'].startswith('https://'):raise ValueError()
                datetime.strptime(b['verified_at'],'%Y-%m-%d')
            elif b['cooldown_minutes'] is not None:raise ValueError()
        for alert in d['alerts']:
            if alert['kind'] not in ('boss','stamina','market') or type(alert['fired']) is not bool:raise ValueError()
            if 'cancelled' in alert and type(alert['cancelled']) is not bool:raise ValueError()
            if alert['kind']=='market':
                label(alert['world_id']);item_name(alert['item']);price_gp(alert['threshold'])
                if alert['offer_type'] not in ('buy','sell','traded') or alert['direction'] not in ('above','below'):raise ValueError()
                if alert['matched_at'] is not None:instant(alert['matched_at'])
            else:label(alert['character_id']);instant(alert['at']);label(alert['message'])
        for event in d['events']:
            instant(event['at'])
            if event['intent'] not in (*FIELDS,'alert.fired') or not isinstance(event['arguments'],dict):raise ValueError()
            if event['character_id'] is not None and event['character_id']!='':label(event['character_id'])
            if event['world_id'] is not None and event['world_id']!='':label(event['world_id'])
        for rid,cached in d['requests'].items():
            label(rid)
            if not isinstance(cached,dict) or not re.fullmatch('[a-f0-9]{64}',cached['hash']) or not isinstance(cached['result'],dict):raise ValueError()
    except (ValueError,TypeError,KeyError,AttributeError):
        raise ValueError('Dados do Assistente inválidos ou de versão desconhecida. Arquivo preservado; restaure um backup válido.') from None
    return d
