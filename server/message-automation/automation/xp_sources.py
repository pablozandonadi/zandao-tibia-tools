"""Cache datado GuildStats e medições separadas de XP total TibiaData.

Leituras dos comandos nunca fazem HTTP. A manutenção coleta um mundo por vez,
com lease/backoff persistentes; uma coleta incompleta nunca vira um dia de XP.
"""
import hashlib
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo
from .domain import UTC, reference_day

WORLD=re.compile(r'^[A-Za-z]{2,40}$')
NAME=re.compile(r"^[A-Za-z][A-Za-z '\-.]{1,39}$")
TTL=900
RETENTION=60
UPSTREAM_MAX_AGE=1800
OWNER='xp-public'

def failure(error):
    """Somente códigos/classes controlados, nunca URL ou texto da exceção."""
    kind=type(error).__name__;kind=kind if re.fullmatch(r'[A-Za-z_]{1,60}',kind) else 'Error'
    reason='http_error' if isinstance(error,HTTPError) else 'timeout' if isinstance(error,TimeoutError) else 'invalid_response' if isinstance(error,ValueError) else 'source_unavailable'
    if isinstance(error,ValueError):
        reason={'Publicação TibiaData antiga.':'upstream_stale','Coleta upstream antiga.':'upstream_stale','A fonte ainda não publicou outra medição.':'publication_unchanged','Páginas de datas diferentes.':'publication_inconsistent'}.get(str(error),reason)
    result={'status':'blocked' if isinstance(error,HTTPError) and error.code==403 else 'unavailable','reason':reason,'error_type':kind}
    if isinstance(error,HTTPError):result['http_status']=error.code if type(error.code) is int and 100<=error.code<=599 else 0
    return result

def public_get(url,limit):
    request=Request(url,headers={'User-Agent':'TibiaTudo/1.0 (+https://tibia-tudo.web.app)'})
    deadline=time.monotonic()+6
    with urlopen(request,timeout=4) as response:
        raw=bytearray()
        while True:
            if time.monotonic()>deadline: raise TimeoutError('Consulta excedeu o prazo.')
            chunk=response.read1(min(16384,limit+1-len(raw)))
            if not chunk: break
            raw.extend(chunk)
            if len(raw)>limit: raise ValueError('Resposta excedeu o limite.')
        return bytes(raw)

def guildstats(world,window):
    import guild_stats
    parser=guild_stats.Tables()
    parser.feed(public_get('https://guildstats.eu/top-experience?world='+quote(world)+'&time='+str(window),6_000_000).decode('utf-8'))
    for table in parser.tables:
        headers=[h.casefold() for h in table['headers']]
        if 'name' not in headers or 'voc' not in headers: continue
        exp=next((i for i,h in enumerate(headers) if 'exp' in h),None)
        if exp is None: continue
        rows=[]
        for row in table['rows']:
            if len(row)<=max(2,exp,headers.index('voc')): continue
            try: rows.append((row[headers.index('name')],int(row[2].replace(',','')),int(row[exp].replace(',','').replace('+','')),row[headers.index('voc')]))
            except (ValueError,TypeError): raise ValueError('Ranking GuildStats incompleto.') from None
        if rows: return valid_rows(rows)
    raise ValueError('Ranking GuildStats indisponível.')

def valid_rows(rows):
    if not isinstance(rows,(list,tuple)) or not 1<=len(rows)<=1000: raise ValueError('Ranking inválido.')
    names=set();result=[]
    for row in rows:
        if not isinstance(row,(list,tuple)) or len(row)!=4: raise ValueError('Linha inválida.')
        name,level,value,vocation=row
        if not isinstance(name,str) or not NAME.fullmatch(name) or name.casefold() in names: raise ValueError('Personagem inválido ou duplicado.')
        if type(level) is not int or not 1<=level<=50000 or type(value) is not int or abs(value)>10**18: raise ValueError('XP inválido.')
        if not isinstance(vocation,str) or not 1<=len(vocation)<=50: raise ValueError('Vocação inválida.')
        names.add(name.casefold());result.append((name,level,value,vocation))
    return result

def tibiadata(world,now,get=public_get):
    """Só retorna depois de validar a paginação inteira e os tempos upstream."""
    def page(number):
        data=json.loads(get('https://api.tibiadata.com/v4/highscores/'+quote(world)+'/experience/all/'+str(number),262144))
        h=data.get('highscores',{});meta=h.get('highscore_page',{});info=data.get('information',{})
        if h.get('world','').casefold()!=world.casefold() or h.get('category')!='experience' or h.get('vocation')!='all': raise ValueError('Categoria ou mundo divergente.')
        if info.get('api',{}).get('version')!=4 or info.get('status',{}).get('http_code')!=200: raise ValueError('API indisponível.')
        stamp=datetime.fromisoformat(info['timestamp'].replace('Z','+00:00'))
        if stamp.tzinfo is None or not -120<=now.timestamp()-stamp.timestamp()<=UPSTREAM_MAX_AGE: raise ValueError('Publicação TibiaData antiga.')
        if any(type(meta.get(k)) is not int for k in ('current_page','total_pages','total_records')): raise ValueError('Paginação inválida.')
        if meta['current_page']!=number or not 1<=meta['total_pages']<=20 or not 1<=meta['total_records']<=1000: raise ValueError('Paginação fora do limite.')
        if meta['total_pages']!=(meta['total_records']+49)//50: raise ValueError('Total de páginas divergente.')
        rows=h.get('highscore_list')
        if not isinstance(rows,list) or len(rows)!=(50 if number<meta['total_pages'] else meta['total_records']-(number-1)*50): raise ValueError('Página incompleta.')
        for index,row in enumerate(rows):
            if not isinstance(row,dict) or row.get('world','').casefold()!=world.casefold() or type(row.get('rank')) is not int or row['rank']!=(number-1)*50+index+1: raise ValueError('Posição ou mundo inválido.')
            if type(row.get('value')) is not int or row['value']<0: raise ValueError('XP total inválido.')
        return meta,stamp.timestamp(),[(r.get('name'),r.get('level'),r.get('value'),r.get('vocation')) for r in rows]
    first=page(1);count=first[0]['total_pages']
    with ThreadPoolExecutor(max_workers=4) as pool: rest=list(pool.map(page,range(2,count+1)))
    pages=[first,*rest]
    if any(p[0]['total_pages']!=count or p[0]['total_records']!=first[0]['total_records'] for p in pages): raise ValueError('Publicações inconsistentes.')
    stamps=[p[1] for p in pages]
    if max(stamps)-min(stamps)>TTL or len({reference_day(datetime.fromtimestamp(t,UTC)) for t in stamps})!=1: raise ValueError('Páginas de datas diferentes.')
    rows=valid_rows([r for p in pages for r in p[2]])
    if len(rows)!=first[0]['total_records']: raise ValueError('Ranking incompleto.')
    fingerprint=hashlib.sha256(json.dumps(rows,separators=(',',':')).encode()).hexdigest()
    return {'rows':rows,'upstream':min(stamps),'fingerprint':fingerprint,'day':reference_day(datetime.fromtimestamp(min(stamps),UTC))}

class XPProvider:
    def __init__(self,store,clock=None,gs=guildstats,td=tibiadata):
        self.store=store;self.clock=clock or (lambda:datetime.now(UTC));self.gs=gs;self.td=td

    def cache(self,world,window):
        with self.store.tx() as db: row=db.execute('SELECT * FROM xp_rank_cache WHERE world=? AND window=?',(world.capitalize(),window)).fetchone()
        if not row: return {'status':'waiting','rows':None,'observed':0}
        result=dict(row);result['rows']=self.store.unpack(OWNER,'gs:'+world.casefold()+':'+str(window),row['body']) if row['body'] else None
        return result

    def maintain(self,worlds,now=None):
        """Uma coleta por chamada do serviço dedicado, nunca do laço de comandos."""
        now=now or self.clock();stamp=now.timestamp();day=reference_day(now)
        worlds=list(dict.fromkeys(w.capitalize() for w in worlds if WORLD.fullmatch(w)))[:20]
        selected=None
        with self.store.tx() as db:
            options=[]
            for world in worlds:
                db.execute('INSERT OR IGNORE INTO xp_refresh(world) VALUES(?)',(world,))
                state=db.execute('SELECT * FROM xp_refresh WHERE world=?',(world,)).fetchone()
                if state['lease']>stamp or state['last_attempt']>stamp-TTL: continue
                gs_due=any(not (r:=db.execute('SELECT retry_after FROM xp_rank_cache WHERE world=? AND window=?',(world,w)).fetchone()) or r['retry_after']<=stamp for w in (0,7,30))
                td_due=state['td_retry']<=stamp and not db.execute('SELECT 1 FROM xp_totals WHERE world=? AND day=?',(world,day)).fetchone()
                if gs_due or td_due: options.append((state['last_attempt'],world))
            if options:
                selected=min(options)[1];db.execute('UPDATE xp_refresh SET lease=?,last_attempt=? WHERE world=?',(stamp+120,stamp,selected))
        if selected:return self.collect(selected,now)
        return {'attempted':False,'status':'skipped','reason':'backoff_or_no_due_world','guildstats':[],'tibiadata':{'status':'skipped'}}

    def collect(self,world,now=None):
        now=now or self.clock();stamp=now.timestamp();world=world.capitalize()
        with self.store.tx() as db:db.execute('INSERT OR IGNORE INTO xp_refresh(world) VALUES(?)',(world,))
        summary={'attempted':False,'status':'skipped','guildstats':[],'tibiadata':{'status':'skipped'}}
        try:
            for window in (0,7,30):
                cache=self.cache(world,window)
                if cache.get('retry_after',0)>stamp: continue
                try:
                    rows=valid_rows(self.gs(world,window));body=self.store.pack(OWNER,'gs:'+world.casefold()+':'+str(window),rows)
                    with self.store.tx() as db: db.execute('INSERT INTO xp_rank_cache VALUES(?,?,?,?,?,?) ON CONFLICT(world,window) DO UPDATE SET observed=excluded.observed,retry_after=excluded.retry_after,status=excluded.status,body=excluded.body',(world,window,stamp,stamp+TTL,'ok',body))
                    summary['guildstats'].append({'window':window,'status':'ok'})
                except Exception as error:
                    status='blocked' if isinstance(error,HTTPError) and error.code==403 else 'unavailable';retry=stamp+(21600 if status=='blocked' else TTL)
                    with self.store.tx() as db: db.execute('INSERT INTO xp_rank_cache VALUES(?,?,0,?,?,NULL) ON CONFLICT(world,window) DO UPDATE SET retry_after=excluded.retry_after,status=excluded.status',(world,window,retry,status))
                    summary['guildstats'].append({'window':window,**failure(error)})
            # Publication day comes from upstream, not from the time our server read it.
            with self.store.tx() as db:
                exists=db.execute('SELECT 1 FROM xp_totals WHERE world=? AND day=?',(world,reference_day(now))).fetchone()
                state=db.execute('SELECT td_retry FROM xp_refresh WHERE world=?',(world,)).fetchone()
            if not (exists or state and state['td_retry']>stamp):
                try:
                    value=self.td(world,now);rows=valid_rows(value['rows']);day=value['day'];upstream=value['upstream']
                    if day!=reference_day(now) or not -120<=stamp-upstream<=UPSTREAM_MAX_AGE: raise ValueError('Coleta upstream antiga.')
                    with self.store.tx() as db:
                        previous=db.execute('SELECT upstream,fingerprint FROM xp_totals WHERE world=? ORDER BY day DESC LIMIT 1',(world,)).fetchone()
                        if previous and (upstream<=previous['upstream'] or value['fingerprint']==previous['fingerprint']): raise ValueError('A fonte ainda não publicou outra medição.')
                        db.execute('INSERT OR IGNORE INTO xp_totals VALUES(?,?,?,?,?,?)',(world,day,stamp,upstream,value['fingerprint'],self.store.pack(OWNER,'td:'+world.casefold()+':'+day,rows)))
                        db.execute('DELETE FROM xp_totals WHERE day<?',((datetime.fromisoformat(day).date()-timedelta(days=RETENTION)).isoformat(),))
                        db.execute('UPDATE xp_refresh SET status=?,td_retry=? WHERE world=?',('ok',stamp+TTL,world))
                    summary['tibiadata']={'status':'ok'}
                except Exception as error:
                    with self.store.tx() as db: db.execute('UPDATE xp_refresh SET status=?,td_retry=? WHERE world=?',('unavailable',stamp+TTL,world))
                    summary['tibiadata']=failure(error)
        finally:
            with self.store.tx() as db: db.execute('UPDATE xp_refresh SET lease=0 WHERE world=?',(world,))
        attempted=[*summary['guildstats'],*([summary['tibiadata']] if summary['tibiadata']['status']!='skipped' else [])]
        summary['attempted']=bool(attempted)
        if attempted:
            successes=sum(r['status']=='ok' for r in attempted)
            summary['status']='ok' if successes==len(attempted) else 'partial' if successes else 'failed'
        return summary

    def totals(self,world):
        with self.store.tx() as db: values=db.execute('SELECT * FROM xp_totals WHERE world=? ORDER BY day DESC LIMIT 32',(world.capitalize(),)).fetchall()
        return {r['day']:{**dict(r),'rows':self.store.unpack(OWNER,'td:'+world.casefold()+':'+r['day'],r['body'])} for r in values}

    def report(self,world,name,today=None):
        now=self.clock();day=reference_day(now);last=(datetime.fromisoformat(day).date()-timedelta(days=1)).isoformat()
        totals=self.totals(world);key=name.casefold();measures={d:next((r for r in v['rows'] if r[0].casefold()==key),None) for d,v in totals.items()}
        with self.store.tx() as db: historical=[tuple(r) for r in db.execute('SELECT day,level,xp FROM rank_history WHERE world=? AND name=? COLLATE NOCASE ORDER BY day DESC LIMIT 60',(world.capitalize(),name))]
        history={r[0]:r for r in historical};result={0:None,7:None,30:None};notes=[];meta={};daily=[];periods={}
        for window in (0,7,30):
            c=self.cache(world,window);match=next((r for r in c['rows'] or () if r[0].casefold()==key),None);fresh=bool(match and c['observed']>=now.timestamp()-TTL and reference_day(datetime.fromtimestamp(c['observed'],UTC))==day)
            days=window or 1;required=[(datetime.fromisoformat(last).date()-timedelta(days=i)).isoformat() for i in range(days)]
            if fresh:
                result[window]=match[2];meta[window]={'source':'GuildStats','date':datetime.fromtimestamp(c['observed'],UTC).isoformat(),'fresh':True}
            elif all(d in history for d in required):
                result[window]=sum(history[d][2] for d in required);meta[window]={'source':'GuildStats — histórico salvo','date':last,'fresh':True}
            else:
                wanted=[(datetime.fromisoformat(day).date()-timedelta(days=i)).isoformat() for i in range(days+1)]
                if all(measures.get(d) for d in wanted):
                    result[window]=measures[wanted[0]][2]-measures[wanted[-1]][2]
                    meta[window]={'source':'TibiaData — variação entre coletas','date':totals[wanted[0]]['observed'],'start':totals[wanted[-1]]['upstream'],'end':totals[wanted[0]]['upstream'],'fresh':True}
                elif match and c['observed']>=now.timestamp()-RETENTION*86400:
                    result[window]=match[2];meta[window]={'source':'GuildStats — dado antigo','date':datetime.fromtimestamp(c['observed'],UTC).isoformat(),'fresh':False}
        if any(value is None for value in result.values()):
            notes.append('Histórico insuficiente para calcular os períodos sem valor.')
        for d in sorted(set(history)|set(measures),reverse=True):
            if d in history: daily.append((*history[d],'GuildStats — histórico salvo'))
            else:
                older=(datetime.fromisoformat(d).date()-timedelta(days=1)).isoformat()
                if measures.get(d) and measures.get(older):
                    daily.append((d,measures[d][1],measures[d][2]-measures[older][2],'TibiaData — variação entre coletas'))
                    periods[d]={'start':totals[older]['upstream'],'end':totals[d]['upstream']}
        rates={}
        for window,value in result.items():
            if value is None:continue
            m=meta[window];days=(m['end']-m['start'])/86400 if 'start' in m else (window or 1)
            if days>0:rates[window]=value/days
        result.update(_meta=meta,_notes=notes,_daily=sorted(daily,reverse=True),_daily_periods=periods,_projection=bool(meta.get(30,{}).get('fresh')),_rates=rates)
        if totals: result['_latest_total']=next(({'day':d,'value':measures[d][2]} for d in sorted(totals,reverse=True) if measures.get(d)),None)
        return result

    def ranking_for_extra(self,world):
        now=self.clock();c=self.cache(world,0)
        if c['rows'] and c['observed']>=now.timestamp()-TTL and reference_day(datetime.fromtimestamp(c['observed'],UTC))==reference_day(now):
            return {'rows':c['rows'],'source':'GuildStats','observed':c['observed'],'note':'GuildStats — consulta '+datetime.fromtimestamp(c['observed'],UTC).strftime('%d/%m/%Y %H:%M UTC')}
        totals=self.totals(world);day=reference_day(now);older=(datetime.fromisoformat(day).date()-timedelta(days=1)).isoformat()
        if day in totals and older in totals:
            before={r[0].casefold():r for r in totals[older]['rows']}
            rows=[(n,lv,x-before[n.casefold()][2],voc) for n,lv,x,voc in totals[day]['rows'] if n.casefold() in before]
            if rows:return {'rows':rows,'source':'TibiaData — variação entre coletas','observed':totals[day]['observed'],'start':totals[older]['upstream'],'end':totals[day]['upstream'],'note':'TibiaData — variação entre coletas de '+datetime.fromtimestamp(totals[older]['upstream'],UTC).strftime('%d/%m %H:%M UTC')+' a '+datetime.fromtimestamp(totals[day]['upstream'],UTC).strftime('%d/%m %H:%M UTC')+'; somente personagens presentes nas duas listas.'}
        if c['observed']:note='Última consulta válida ao GuildStats: '+datetime.fromtimestamp(c['observed'],UTC).strftime('%d/%m/%Y %H:%M UTC')+'. Dados antigos não são apresentados como XP atual.'
        else:
            with self.store.tx() as db: row=db.execute('SELECT max(day) FROM rank_history WHERE world=?',(world.capitalize(),)).fetchone()
            note='Histórico GuildStats preservado até '+row[0]+'.' if row and row[0] else 'Aguardando uma consulta válida ao GuildStats ou duas coletas completas da TibiaData.'
        return {'rows':None,'source':'status-local','observed':now.timestamp(),'note':note}
