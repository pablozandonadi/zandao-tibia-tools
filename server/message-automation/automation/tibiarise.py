"""Leitura limitada da API pública usada pelo frontend TibiaRise, sem autenticação."""
import json
import re
from datetime import datetime
from urllib.parse import quote
from .domain import UTC

NAME=re.compile(r"^[A-Za-z][A-Za-z '\-.]{1,39}$")
WORLD=re.compile(r'^[A-Za-z]{2,40}$')
OWNER='xp-public'
PERIODS={0:'daily',7:'weekly',30:'monthly'}
MAX_AGE=36*3600
REFRESH=6*3600
RETRY=900


def stamp(value):
    if not isinstance(value,str) or len(value)>40: raise ValueError('Data TibiaRise inválida.')
    d=datetime.fromisoformat(value.replace('Z','+00:00'))
    if d.tzinfo is None: raise ValueError('Data TibiaRise sem fuso.')
    return d.astimezone(UTC).timestamp()


def number(value,minimum=-10**18,maximum=10**18):
    if type(value) is not int or not minimum<=value<=maximum: raise ValueError('Número TibiaRise inválido.')
    return value


def identity(data,world,name=None):
    if not isinstance(data,dict) or str(data.get('world','')).casefold()!=world.casefold(): raise ValueError('Mundo TibiaRise divergente.')
    if name is not None and str(data.get('name','')).casefold()!=name.casefold(): raise ValueError('Personagem TibiaRise divergente.')


def character(world,name,now,get):
    rows=[];total=None
    for page in (1,2):
        data=json.loads(get('https://tibiarise.app/api/character/'+quote(name,safe='')+'?page='+str(page),262144))
        identity(data.get('character'),world,name)
        pagination=data.get('pagination',{});values=data.get('experienceTable')
        if number(pagination.get('page'),1,2)!=page or number(pagination.get('pageSize'),1,30)!=30: raise ValueError('Paginação TibiaRise inválida.')
        count=number(pagination.get('total'),0,100000)
        if total is not None and total!=count: raise ValueError('Paginação TibiaRise mudou.')
        total=count
        more=pagination.get('hasMore')
        if type(more) is not bool or more!=(page*30<total) or not isinstance(values,list) or len(values)>30 or more and len(values)!=30: raise ValueError('Página TibiaRise incompleta.')
        for row in values:
            if not isinstance(row,dict): raise ValueError('Registro TibiaRise inválido.')
            at=stamp(row.get('date'));level=number(row.get('level'),1,50000)
            if at>now.timestamp()+120 or at<now.timestamp()-60*86400: raise ValueError('Data TibiaRise fora da retenção.')
            rows.append({'at':at,'level':level,'xp':number(row.get('experience')),'total':number(row.get('totalExperience'),0)})
        if not more: break
    if not rows: raise ValueError('Histórico TibiaRise vazio.')
    days=set()
    for index,row in enumerate(rows):
        day=datetime.fromtimestamp(row['at'],UTC).date().isoformat()
        if day in days or index and row['at']>=rows[index-1]['at']: raise ValueError('Datas TibiaRise duplicadas ou desordenadas.')
        days.add(day)
        if index:
            newer=rows[index-1]
            consecutive=(datetime.fromtimestamp(newer['at'],UTC).date()-datetime.fromtimestamp(row['at'],UTC).date()).days==1
            if consecutive and newer['total']-row['total']!=newer['xp']: raise ValueError('XP TibiaRise inconsistente.')
    return {'rows':rows}


def ranking(world,window,now,get):
    data=json.loads(get('https://tibiarise.app/api/experience-by-world/'+quote(world,safe='')+'/'+PERIODS[window],262144))
    identity(data,world);period=data.get('period',{})
    if period.get('type')!=PERIODS[window]: raise ValueError('Período TibiaRise divergente.')
    start=stamp(period.get('startDate'));end=stamp(period.get('endDate'));updated=stamp(data.get('updatedAt'))
    if not 0<end-start<=(window or 1)*86400+7200 or abs((end-start)-(window or 1)*86400)>7200: raise ValueError('Intervalo TibiaRise inválido.')
    if end>now.timestamp()+120 or updated>now.timestamp()+120 or end<now.timestamp()-60*86400: raise ValueError('Publicação TibiaRise inválida.')
    if updated<start or updated>end+86400: raise ValueError('Publicação TibiaRise fora do período.')
    values=data.get('topGainers')
    if not isinstance(values,list) or not 1<=len(values)<=100: raise ValueError('Ranking TibiaRise inválido.')
    rows=[];names=set();duplicates=set()
    for row in values:
        if not isinstance(row,dict): raise ValueError('Linha TibiaRise inválida.')
        identity(row,world);name=row.get('characterName');voc=row.get('vocation')
        if not isinstance(name,str) or not NAME.fullmatch(name): raise ValueError('Nome TibiaRise inválido.')
        if not isinstance(voc,str) or not 1<=len(voc)<=50: raise ValueError('Vocação TibiaRise inválida.')
        if name.casefold() in names:duplicates.add(name.casefold())
        rows.append((name,number(row.get('level'),1,50000),number(row.get('experienceGained')),voc));names.add(name.casefold())
    # A lista pública pode conter IDs antigos do mesmo nome: nenhum deles é escolhido arbitrariamente.
    rows=[r for r in rows if r[0].casefold() not in duplicates]
    if not rows:raise ValueError('Ranking TibiaRise ambíguo.')
    return {'rows':rows,'start':start,'end':end,'updated':updated,'omitted':len(duplicates)}


class RiseCache:
    """Fila de nomes públicos e cache cifrado separado; os comandos só leem SQLite."""
    def __init__(self,store,clock,get):self.store=store;self.clock=clock;self.get=get

    def request(self,world,name=''):
        if not isinstance(world,str) or not WORLD.fullmatch(world) or name and (not isinstance(name,str) or not NAME.fullmatch(name)): return
        world=world.capitalize();name=name.casefold();kind='character' if name else 'ranking';now=self.clock().timestamp()
        with self.store.tx() as db:
            db.execute('DELETE FROM xp_rise_cache WHERE requested<?',(now-60*86400,))
            found=db.execute('SELECT 1 FROM xp_rise_cache WHERE kind=? AND world=? AND name=?',(kind,world,name)).fetchone()
            if found:db.execute('UPDATE xp_rise_cache SET requested=? WHERE kind=? AND world=? AND name=?',(now,kind,world,name))
            elif db.execute("SELECT count(*) FROM xp_rise_cache WHERE kind='character'").fetchone()[0]<200 or not name:
                db.execute('INSERT INTO xp_rise_cache(kind,world,name,requested) VALUES(?,?,?,?)',(kind,world,name,now))

    def read(self,world,name=''):
        kind='character' if name else 'ranking';name=name.casefold()
        with self.store.tx() as db:row=db.execute('SELECT * FROM xp_rise_cache WHERE kind=? AND world=? AND name=?',(kind,world.capitalize(),name)).fetchone()
        if not row:return None
        value=dict(row)
        value['data']=self.store.unpack(OWNER,'rise:'+kind+':'+world.casefold()+':'+name,row['body']) if row['body'] else None
        return value

    def collect(self,worlds):
        now=self.clock();at=now.timestamp()
        for world in worlds:self.request(world)
        results=[]
        for kind in ('character','ranking'):
            with self.store.tx() as db:
                row=db.execute('SELECT * FROM xp_rise_cache WHERE kind=? AND retry_after<=? AND lease<=? AND requested>=? ORDER BY observed,requested LIMIT 1',(kind,at,at,at-7*86400)).fetchone()
                if not row:continue
                row=dict(row);db.execute('UPDATE xp_rise_cache SET lease=? WHERE kind=? AND world=? AND name=?',(at+120,kind,row['world'],row['name']))
            key='rise:'+kind+':'+row['world'].casefold()+':'+row['name']
            try:
                value=character(row['world'],row['name'],now,self.get) if kind=='character' else {str(w):ranking(row['world'],w,now,self.get) for w in PERIODS}
                body=self.store.pack(OWNER,key,value)
                with self.store.tx() as db:db.execute("UPDATE xp_rise_cache SET body=?,observed=?,retry_after=?,lease=0,status='ok' WHERE kind=? AND world=? AND name=?",(body,at,at+REFRESH,kind,row['world'],row['name']))
                results.append({'kind':kind,'status':'ok'})
            except Exception as error:
                from .xp_sources import failure
                with self.store.tx() as db:db.execute("UPDATE xp_rise_cache SET retry_after=?,lease=0,status='unavailable' WHERE kind=? AND world=? AND name=?",(at+RETRY,kind,row['world'],row['name']))
                results.append({'kind':kind,**failure(error)})
        return results

    def report(self,world,name):
        self.request(world,name);now=self.clock().timestamp();cached=self.read(world,name)
        rows=(cached or {}).get('data',{}).get('rows',[]) if cached and cached.get('data') else []
        daily=[];periods={};windows={}
        for newer,older in zip(rows,rows[1:]):
            end=datetime.fromtimestamp(newer['at'],UTC).date();start=datetime.fromtimestamp(older['at'],UTC).date()
            if (end-start).days!=1 or not 20*3600<=newer['at']-older['at']<=28*3600:continue
            day=end.isoformat();daily.append((day,newer['level'],newer['xp'],'TibiaRise — variação entre registros'))
            periods[day]={'start':older['at'],'end':newer['at']}
        for window in (0,7,30):
            count=window or 1
            if len(rows)>count:
                selected=rows[:count+1]
                if all((datetime.fromtimestamp(a['at'],UTC).date()-datetime.fromtimestamp(b['at'],UTC).date()).days==1 and 20*3600<=a['at']-b['at']<=28*3600 for a,b in zip(selected,selected[1:])):
                    end=selected[0]['at'];start=selected[-1]['at']
                    windows[window]=(sum(r['xp'] for r in selected[:-1]),{'source':'TibiaRise — variação entre registros','date':end,'start':start,'end':end,'complete':True,'fresh':now-end<=MAX_AGE and now-cached['observed']<=REFRESH+RETRY})
        ranks=self.read(world)
        if ranks and ranks.get('data'):
            for window in (0,7,30):
                rank=ranks['data'].get(str(window));match=next((r for r in (rank or {}).get('rows',[]) if r[0].casefold()==name.casefold()),None)
                if match and window not in windows:
                    windows[window]=(match[2],{'source':'TibiaRise — ranking','date':rank['updated'],'start':rank['start'],'end':rank['end'],'complete':False,'fresh':now-rank['end']<=MAX_AGE and now-ranks['observed']<=REFRESH+RETRY})
        return windows,daily,periods,bool(cached and cached['status']=='waiting')

    def ranking(self,world):
        self.request(world);cached=self.read(world);rank=(cached or {}).get('data',{}).get('0') if cached and cached.get('data') else None
        now=self.clock().timestamp()
        if not rank or now-rank['end']>MAX_AGE or now-cached['observed']>REFRESH+RETRY:return None
        label=lambda at:datetime.fromtimestamp(at,UTC).strftime('%d/%m/%Y %H:%M UTC')
        note='TibiaRise — ranking de '+label(rank['start'])+' a '+label(rank['end'])+'; lista pública limitada aos 100 maiores ganhos.'
        if rank.get('omitted'):note+=' Nomes duplicados na fonte foram omitidos.'
        return {**rank,'observed':cached['observed'],'source':'TibiaRise — ranking','note':note}
