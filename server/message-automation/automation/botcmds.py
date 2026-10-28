"""Respostas dos comandos do grupo (!help, !precocoin, !duelo, !evolucao): só leitura de fontes públicas, no padrão de texto do WhatsApp.

As fontes entram por funções injetáveis (testes sem rede). Nomes vindos de fora passam por `clean` antes de entrar na mensagem.
"""
import re
import threading
import modelos
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import time
import unicodedata
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import quote

NAME=re.compile(r"[A-Za-z][A-Za-z '\-.]{1,39}")
WORLD=re.compile(r'[A-Za-z]{2,40}')
RANKING='https://guildstats.eu/top-experience?world={}&time={}'  # time: 0 = ontem, 7 e 30 = dias; só o top 500 do mundo
CACHE_TTL=900
WARM_EVERY=600
PARTY_PER_VOCATION=8
VOCATION_ALIASES={'ek':'EK','knight':'EK','k':'EK','rp':'RP','paladin':'RP','p':'RP','ed':'ED','druid':'ED','d':'ED','ms':'MS','sorcerer':'MS','s':'MS','em':'EM','monk':'EM','m':'EM'}
FAIL='Não consegui consultar agora. Tente de novo em instantes.'
PACKAGE_TC=250
PACKAGE_REAIS=(Decimal(49),Decimal(52))  # mesmo padrão da calculadora do app
EMOJI={'knight':'🛡️','paladin':'🏹','druid':'❄️','sorcerer':'🔥','monk':'👊'}

HELP='''📖 *TibiaTudo IA — comandos disponíveis*

*📖 Comuns*

- `help` — Lista os comandos disponíveis

*⚔️ Tibia*

- `duelo` — Dois personagens lado a lado e quem ultrapassa quem no ritmo atual
- `evolucao` — XP dos últimos 30 dias e projeção de level
- `precocoin` — Cotação da Tibia Coin por mundo
- `pt` — Party finder: jogadores online na faixa de shared experience
- `char` — Informações completas do personagem em qualquer mundo
- `online` — Jogadores online de um mundo ou guild
- `xptop` — XP diário dos últimos 30 dias

*🛠️ Admins do grupo*

- `set` — Configurações do grupo: mundo, espera entre comandos e quais comandos ficam ligados
- `alerta` — Avisos de morte e level up da guild
- `bomdia` — Mensagem de bom dia automática, sempre completa

*📋 Como utilizar*

- `!help`
- `!duelo <char1> x <char2>`
- `!evolucao <char>`
- `!precocoin <mundo>`
- `!pt <personagem> [voc]`
- `!char <nome>`
- `!online <mundo ou guild>`
- `!xptop <personagem>`

*🔧 Como configurar (só admins do grupo)*

- `!set` — mostra a configuração do grupo
- `!set world <mundo>`
- `!set cooldown <30s, 2m ou 1h>`
- `!set comandos on/off`
- `!set cmd <comando> on/off`
- `!alerta guild <nome>`
- `!alerta level <n>`
- `!alerta mortes on/off` · `!alerta ups on/off`
- `!alerta limite hora <n>` · `!alerta limite minuto <n>`
- `!alerta on/off` · `!alerta remover`
- `!bomdia on/off` — liga ou pausa o bom dia
- `!bomdia horario <hh:mm>` — hora do envio (Brasília)
- `!bomdia guild <nome>` — guild do top XP e do resumo da guild
- `!bomdia teste` — manda um bom dia agora, só para ver

🌐 *Site:* https://tibia-tudo.web.app'''

T_COIN='🪙 *Tibia Coin — {mundo}*\n• 1 TC ≈ *{preco}* gold (média de venda, {data})\n• 1kk de gold ≈ *{tc_por_kk} TC* ≈ R$ {reais_min} a R$ {reais_max}\n• Pacote de {pacote_tc} TC: R$ {pacote_min} a R$ {pacote_max}\n{aviso}'
T_DUEL='⚔️ *{nome1} x {nome2}* — últimos 30 dias\n{tabela}\n{resultado}'
T_EVOLUTION='📈 *Evolução — {nome}*\n{ficha}\n\n{xp_ganha}\n\n{projecao}\n\n{grafico}'
T_CHAR='📜 *{nome}*\n{ficha}\n{guilda}\n{casas}\n{residencia}\n{extra}\n{login}\n\n{mortes}'
T_PARTY='🤝 *Party match — {nome}*{filtro}\n{ficha}\n🔗 Shared: {shared_min}–{shared_max} · jogadores online\n\n{lista}'
T_ONLINE='{bolinha} *{nome}* — {estado}\n👥 *{jogadores}* jogadores online agora\n{lugar}'
T_ONLINE_GUILD='🟢 *{nome}* online ({online} de {total})\n{lista}'
T_XPTOP='📈 *XP — últimos 30 dias*\n📅 até {ate}\n\n📜 *{nome}*\n{ficha}\n{guilda}\n\n{dias}\n{aviso}\n\n*Resumo (GuildStats)*\n• Ontem: {xp_ontem}\n• 7 dias: {xp_7d}\n• 30 dias: *{xp_30d}* (média {xp_media}/dia)'

# Catálogo mostrado no Admin: modelo padrão (igual à resposta de hoje), variáveis e um exemplo para a prévia.
MODELS={
    'help':{'template':HELP,'vars':{},'example':''},
    'duelo':{'template':T_DUEL,'example':'Zazamyon x Papelaum Meliexp','vars':{'nome1':'primeiro personagem','nome2':'segundo personagem','tabela':'tabela lado a lado (nível e XP)','resultado':'quem passa quem e quando'}},
    'evolucao':{'template':T_EVOLUTION,'example':'Zazamyon','vars':{'nome':'personagem','ficha':'vocação, level e mundo','xp_ganha':'bloco de XP ganha (ontem, 7 e 30 dias)','projecao':'bloco da projeção de level','grafico':'gráfico dos últimos dias','level':'level','mundo':'mundo','vocacao':'vocação'}},
    'precocoin':{'template':T_COIN,'example':'Rasteibra','vars':{'mundo':'mundo','preco':'gold por 1 TC','data':'data da cotação (dd/mm)','tc_por_kk':'TC que 1kk de gold compra','reais_min':'R$ mínimo de 1kk','reais_max':'R$ máximo de 1kk','pacote_tc':'TC do pacote','pacote_min':'R$ mínimo do pacote','pacote_max':'R$ máximo do pacote','aviso':'nota sobre a fonte da cotação'}},
    'pt':{'template':T_PARTY,'example':'Zazamyon ek','vars':{'nome':'personagem','filtro':'filtro de vocação (se houver)','ficha':'vocação, level e mundo','shared_min':'menor level da faixa','shared_max':'maior level da faixa','lista':'jogadores por vocação'}},
    'char':{'template':T_CHAR,'example':'Zazamyon','vars':{'nome':'personagem','ficha':'vocação, level e mundo','guilda':'guilda e cargo','casas':'casas','residencia':'residência','extra':'achievement points e conta','login':'último login','mortes':'bloco de mortes recentes'}},
    'online':{'template':T_ONLINE,'example':'Rasteibra','vars':{'bolinha':'🟢/🔴 do mundo','nome':'mundo ou guild','estado':'Online ou Offline (mundo)','jogadores':'jogadores online (mundo)','lugar':'região e tipo de PvP (mundo)','online':'membros online (guild)','total':'membros da guild','lista':'lista de membros online (guild)'}},
    'xptop':{'template':T_XPTOP,'example':'Zazamyon','vars':{'ate':'data final (dd/mm)','nome':'personagem','ficha':'vocação, level e mundo','guilda':'guilda','dias':'XP dia a dia','aviso':'nota sobre o histórico','xp_ontem':'XP de ontem','xp_7d':'XP em 7 dias','xp_30d':'XP em 30 dias','xp_media':'média por dia (30 dias)'}}}

class Reply:
    """Resposta montada por modelo. O administrador pode trocar o modelo; `{resposta}` é o modelo padrão já preenchido."""
    def __init__(self,template,variables,notice=''): self.template=template;self.variables=variables;self.notice=notice
    def text(self,custom=''):
        default=modelos.renderizar(self.template,self.variables)
        text=modelos.renderizar(custom,{**self.variables,'resposta':default}) if custom else default
        if not self.notice:return text
        title,separator,body=text.partition('\n')
        return title+'\n\n'+self.notice+('\n\n'+body if separator else '')

def clean(value,limit=40):
    return re.sub(r'[*_~`\x00-\x1f]','',str(value))[:limit].strip()

def norm(text):
    return unicodedata.normalize('NFKD',str(text).casefold()).encode('ascii','ignore').decode()

def pt(number):
    return f'{int(number):,}'.replace(',','.')

def decimal_pt(value,places=2):
    text=f'{Decimal(value).quantize(Decimal(1).scaleb(-places),rounding=ROUND_HALF_UP):,.{places}f}'
    return text.replace(',','#').replace('.',',').replace('#','.')

def kk(number):
    sign='-' if number<0 else ''
    number=abs(number)
    return sign+(f'{number/1e9:.2f}kkk' if number>=1e9 else f'{number/1e6:.2f}kk').replace('.',',')

def vocation_code(vocation):
    text=str(vocation).casefold()
    return next((code for key,code in (('knight','EK'),('paladin','RP'),('druid','ED'),('sorcerer','MS'),('monk','EM')) if key in text),'?')

def brt(value):
    return datetime.fromisoformat(str(value).replace('Z','+00:00')).astimezone(timezone(timedelta(hours=-3)))

def emoji(vocation): return EMOJI.get(next((k for k in EMOJI if k in str(vocation).casefold()),''),'')

def short(date_value): return date_value.strftime('%d/%m/%y')

def span(days):
    return f'~{round(days)} dias' if days<60 else f'~{round(days/30)} meses'

# ---- fontes (padrão: rede; nos testes são trocadas) ----
_cache={};_lock=threading.Lock()

def cached(key,fetch,refresh=False,ttl=None):
    with _lock:
        hit=_cache.get(key)
        if hit and not refresh and time.monotonic()-hit[0]<(ttl or CACHE_TTL): return hit[1]
    value=fetch()
    with _lock: _cache[key]=(time.monotonic(),value)
    return value

def default_ranking(world,window,refresh=False):
    """[(nome, level, xp, voc)] do top 500 do mundo no GuildStats, ou None."""
    import guild_stats
    import zandaobot_sources as sources
    def fetch():
        parser=guild_stats.Tables();parser.feed(sources.get_text(RANKING.format(quote(world),window),6_000_000))
        for table in parser.tables:
            headers=[h.casefold() for h in table['headers']]
            exp=next((i for i,h in enumerate(headers) if 'exp' in h),None);voc=next((i for i,h in enumerate(headers) if h=='voc'),None)
            if exp is None or voc is None or 'name' not in headers: continue
            rows=[]
            for r in table['rows']:
                try: rows.append((r[1],int(r[2].replace(',','')),int(r[exp].replace(',','').replace('+','')),r[voc]))
                except (ValueError,IndexError): continue
            if rows: return rows
        raise ValueError('Ranking vazio')
    try: return cached(('rank',world.casefold(),window),fetch,refresh)
    except Exception: return None

def default_sheet(name):
    """{'name','level','vocation','world'} da ficha pública, ou None."""
    import tibia_info
    try:
        def fetch():
            info=(tibia_info._get_json(tibia_info.TIBIADATA+'/character/'+quote(name)).get('character') or {}).get('character') or {}
            return info if info.get('name') else None
        info=cached(('char',name.casefold()),fetch)
    except Exception: return None
    return {'name':info['name'],'level':info.get('level'),'vocation':info.get('vocation',''),'world':info.get('world',''),'guild':(info.get('guild') or {}).get('name')} if info and type(info.get('level')) is int else None

def default_character(name):
    """Resposta completa da TibiaData para o personagem (ficha + mortes), sem cache: o comando mostra o estado de agora."""
    import tibia_info
    try:
        data=tibia_info._get_json(tibia_info.TIBIADATA+'/character/'+quote(name))
        return data if isinstance(data,dict) else None
    except Exception: return None

def default_online(world):
    """[{'name','level','vocation'}] de quem está online no mundo (TibiaData), ou None."""
    import tibia_info
    def fetch():
        listed=(tibia_info._get_json(tibia_info.TIBIADATA+'/world/'+quote(world)).get('world') or {}).get('online_players')
        if not isinstance(listed,list) or not listed: raise ValueError('Lista vazia')
        return [{'name':p['name'],'level':p['level'],'vocation':p.get('vocation','')} for p in listed if isinstance(p,dict) and isinstance(p.get('name'),str) and type(p.get('level')) is int]
    try: return cached(('online',world.casefold()),fetch,ttl=30)
    except Exception: return None

def default_world(name):
    """Dados do mundo na TibiaData (nome, status, jogadores online, região, tipo de PvP), ou None se não for um mundo."""
    import tibia_info
    def fetch():
        info=tibia_info._get_json(tibia_info.TIBIADATA+'/world/'+quote(name)).get('world') or {}
        if not info.get('name'): raise ValueError('Mundo inexistente')
        return info
    try: return cached(('world',name.casefold()),fetch,ttl=30)
    except Exception: return None

def default_guild(name):
    import tibia_info
    def fetch():
        info=tibia_info._get_json(tibia_info.TIBIADATA+'/guild/'+quote(name)).get('guild') or {}
        if not info.get('name'): raise ValueError('Guild inexistente')
        return info
    try: return cached(('guild',name.casefold()),fetch,ttl=60)
    except Exception: return None

def default_trade(world):
    import tibiatrade_cotacao
    return tibiatrade_cotacao.consultar(world)

KEYS={'help':'help','coin':'precocoin','duel':'duelo','evolution':'evolucao','party':'pt','charinfo':'char','online_cmd':'online','xptop':'xptop'}  # método -> chave do comando no Admin

class Bot:
    def __init__(self,ranking=None,sheet=None,trade=None,history=None,track=None,character=None,online=None,world=None,guild=None,daily=None,settings=None,experience=None):
        self.settings=settings or (lambda:{})  # ajustes do administrador: {comando: {'enabled': bool, 'text': str}}
        self.ranking=ranking or default_ranking;self.sheet=sheet or default_sheet;self.trade=trade or default_trade
        self.character=character or default_character;self.online=online or default_online;self.world=world or default_world;self.guild=guild or default_guild
        self.daily=daily or (lambda world,name:[])
        self.history=history or (lambda world,name:[]);self.track=track or (lambda world:None)
        self.experience=experience

    def pick(self,text):
        """(função, argumento) do comando, ou None se não for um comando conhecido (comandos de outros bots no grupo passam em silêncio)."""
        found=re.fullmatch(r'!\s*(\S+)\s*(.*)',str(text).strip(),re.S)
        if not found: return None
        handler={'help':self.help,'ajuda':self.help,'comandos':self.help,'precocoin':self.coin,'tc':self.coin,
                 'duelo':self.duel,'evolucao':self.evolution,'evo':self.evolution,'pt':self.party,'party':self.party,'char':self.charinfo,'personagem':self.charinfo,'online':self.online_cmd,'xptop':self.xptop}.get(norm(found[1]))
        if not handler or self.settings().get(KEYS[handler.__name__],{}).get('enabled') is False: return None  # comando desligado pelo administrador: silêncio
        return handler,' '.join(found[2].split())

    def known(self,text): return self.pick(text) is not None

    def key(self,text):
        """Nome do comando (help, duelo, precocoin…) ou None; é o nome usado em !set cmd e no Admin."""
        picked=self.pick(text)
        return KEYS[picked[0].__name__] if picked else None

    def handle(self,text,world='',today=None):
        """Resposta ao comando, ou None se não for um comando conhecido (ou estiver desligado)."""
        picked=self.pick(text)
        if not picked: return None
        custom=str(self.settings().get(KEYS[picked[0].__name__],{}).get('text') or '')
        if custom and not modelos.usa_variaveis(custom): return custom  # texto fixo: nem consulta as fontes
        try: out=picked[0](picked[1],world,today or date.today())
        except Exception: return FAIL
        return out if isinstance(out,str) else out.text(custom)  # aviso de uso/erro vai sempre como está

    def warm(self,world):
        """Mantém o ranking do mundo no cache para o comando responder sem esperar a fonte."""
        if self.ranking is default_ranking:
            for window in (0,7,30): default_ranking(world,window,True)

    def help(self,arg,world,today): return Reply(HELP,{})

    def coin(self,arg,world,today):
        mundo=arg or world
        if not WORLD.fullmatch(mundo or ''): return 'Use: *!precocoin* <mundo>   Ex.: !precocoin Rasteibra'
        r=self.trade(mundo);price=r.get('gold_por_tc');title=f'🪙 *Tibia Coin — {clean(mundo.capitalize())}*'
        if r.get('estado') not in ('ok','antiga') or type(price) is not int or price<=0:
            return f"{title}\nCotação indisponível agora. {clean(r.get('motivo',''),120)}".strip()
        when=str(r.get('data_base',''))[:10];when=f'{when[8:10]}/{when[5:7]}' if re.fullmatch(r'\d{4}-\d{2}-\d{2}',when) else '❓'
        per_kk=Decimal(1_000_000)/price;low,high=(per_kk*value/PACKAGE_TC for value in PACKAGE_REAIS)
        old='⚠️ _Cotação antiga: o TibiaTrade ainda não atualizou este mundo._' if r.get('estado')=='antiga' else '_Média diária de venda do TibiaTrade; não é o Market em tempo real._'
        return Reply(T_COIN,{'mundo':clean(mundo.capitalize()),'preco':pt(price),'data':when,'tc_por_kk':decimal_pt(per_kk),'reais_min':decimal_pt(low),'reais_max':decimal_pt(high),
                             'pacote_tc':PACKAGE_TC,'pacote_min':decimal_pt(PACKAGE_REAIS[0]),'pacote_max':decimal_pt(PACKAGE_REAIS[1]),'aviso':old})

    def xp(self,info):
        """XP de ontem, 7 e 30 dias de um personagem (None onde está fora do top 500 do mundo)."""
        world=info['world'];self.track(world)
        if self.experience:return self.experience(world,info['name'])
        with ThreadPoolExecutor(max_workers=3) as pool: tables=dict(zip((0,7,30),pool.map(lambda window:self.ranking(world,window),(0,7,30))))
        return {window:next((r[2] for r in rows or () if r[0].casefold()==info['name'].casefold()),None) for window,rows in tables.items()}

    def duel(self,arg,world,today):
        usage='Use: *!duelo* <char1> x <char2>   Ex.: !duelo Fulano x Ciclano'
        found=re.fullmatch(r'(.+?)\s+x\s+(.+)',arg,re.I)
        if not found or not all(NAME.fullmatch(n.strip()) for n in found.groups()): return usage
        typed_names=[n.strip() for n in found.groups()]
        with ThreadPoolExecutor(max_workers=2) as pool: infos=list(pool.map(self.sheet,typed_names))
        for typed,info in zip(typed_names,infos):
            if not info or not WORLD.fullmatch(info.get('world') or ''): return f'Não encontrei o personagem *{clean(typed)}*.'
        with ThreadPoolExecutor(max_workers=2) as pool: pair=[{**info,'xp':xp} for info,xp in zip(infos,pool.map(self.xp,infos))]
        a,b=pair;label=lambda p:(clean(p['name'],40) if len(clean(p['name'],40))<=11 else clean(p['name'],10)+'…')
        rows=[('Level',*(pt(p['level']) for p in pair)),
              ('XP no mês',*(kk(p['xp'][30]) if p['xp'][30] is not None else '—' for p in pair)),
              ('XP/dia',*(kk(p['xp'].get('_rates',{}).get(30,p['xp'][30]/30)) if p['xp'][30] is not None else '—' for p in pair)),
              ('XP 7 dias',*(kk(p['xp'][7]) if p['xp'][7] is not None else '—' for p in pair)),
              ('XP ontem',*(kk(p['xp'][0]) if p['xp'][0] is not None else '—' for p in pair))]
        if self.experience:
            for index,window in ((1,30),(3,7),(4,0)):
                if any(p['xp'].get('_meta',{}).get(window,{}).get('source','').startswith(('TibiaData','TibiaRise')) for p in pair):
                    rows[index]=(('XP entre coletas' if window==0 else 'XP '+str(window)+' intervalos'),*rows[index][1:])
        widths=[max(len(r[i]) for r in [('',label(a),label(b)),*rows]) for i in range(3)]
        line=lambda r:'  '.join(r[i].ljust(widths[i]) if i==0 else r[i].rjust(widths[i]) for i in range(3))
        table='\n'.join(['```',line(('',label(a),label(b))),*(line(r) for r in rows),'```'])
        missing=[clean(p['name']) for p in pair if p['xp'][30] is None]
        if self.experience:
            same=all(p['xp'].get('_projection') for p in pair) and len({p['xp']['_meta'][30]['source'] for p in pair})==1
            if same and 'start' in a['xp']['_meta'][30]:same=all(abs(a['xp']['_meta'][30][k]-b['xp']['_meta'][30][k])<=900 for k in ('start','end'))
            result=self.verdict(a,b,today) if same else '_Sem projeção: faltam períodos completos, atuais e comparáveis para os dois personagens._'
            notice='\n\n'.join('*'+clean(p['name'])+'*\n'+self.xp_notice(p['xp']) for p in pair)
        else:
            result=f'_Sem dados de XP de {", ".join(missing)}: fora do top 500 do mundo no GuildStats._' if missing else self.verdict(a,b,today);notice=''
        return Reply(T_DUEL.replace('últimos 30 dias','dados disponíveis') if self.experience else T_DUEL,{'nome1':clean(a['name']),'nome2':clean(b['name']),'tabela':table,'resultado':result},notice)

    def verdict(self,a,b,today):
        import tibia_info
        front,behind=(a,b) if a['level']>=b['level'] else (b,a)
        if front['level']==behind['level']: return '🤝 Os dois estão no mesmo level.'
        rate_front,rate_behind=(p['xp'].get('_rates',{}).get(30,p['xp'][30]/30) for p in (front,behind))
        gap=tibia_info.xp_total(front['level'])-tibia_info.xp_total(behind['level'])
        fname,bname=clean(front['name']),clean(behind['name'])
        if rate_behind>rate_front:
            days=gap/(rate_behind-rate_front)
            if days>3650: return f'🏁 No ritmo atual, *{bname}* só passa *{fname}* daqui a muitos anos.'
            return f'🚀 No ritmo atual, *{bname}* passa *{fname}* em {span(days)} ({short(today+timedelta(days=days))}).\n_{fname} precisa de {kk(rate_behind)}/dia pra não ser passado._'
        return f'🏁 No ritmo atual, *{fname}* segue na frente de *{bname}*.\n_{bname} precisaria de mais de {kk(rate_front)}/dia pra alcançar._'

    def evolution(self,arg,world,today):
        import tibia_info
        if not NAME.fullmatch(arg): return 'Use: *!evolucao* <char>   Ex.: !evolucao Fulano'
        info=self.sheet(arg)
        if not info or not WORLD.fullmatch(info.get('world') or ''): return f'Não encontrei o personagem *{clean(arg)}*.'
        xp=self.xp(info);name=clean(info['name'])
        sheet=f'{emoji(info["vocation"])} {clean(info["vocation"])} · 🏆 Lv *{pt(info["level"])}* · 🌍 {clean(info["world"])}'.replace('  ',' ').strip()
        if self.experience:return self.measured_evolution(info,xp,today,sheet)
        if xp[30] is None:
            return '\n'.join([f'📈 *Evolução — {name}*',sheet,'','Sem dados de XP: o personagem está fora do top 500 do mundo no GuildStats.'])
        rate=xp[30]/30
        gained='\n'.join(['*XP ganha*',f'• Ontem: *{kk(xp[0])}*' if xp[0] is not None else '• Ontem: — (fora do top 500 de ontem)',
                f'• 7 dias: *{kk(xp[7])}* (média {kk(xp[7]/7)}/dia)' if xp[7] is not None else '• 7 dias: —',
                f'• 30 dias: *{kk(xp[30])}* (média {kk(rate)}/dia)'])
        need=tibia_info.xp_total(info['level']+1)-tibia_info.xp_total(info['level'])
        projection=['🔮 *Projeção no ritmo atual (média de 30 dias)*']
        if rate>0:
            per_level=need/rate;projection.append(f'• Cada level custa ~{kk(need)} ≈ *{decimal_pt(per_level,1)} dias*')
            days_left=max(1,round(per_level));projection.append(f'• Lv {pt(info["level"]+1)} em até ~{days_left} {"dia" if days_left==1 else "dias"} ({short(today+timedelta(days=per_level))})')
        else: projection.append('• Sem ganho de XP nos últimos 30 dias: sem projeção.')
        days=[(d,x) for d,x in self.history(info['world'],info['name']) if x is not None][-14:]
        if len(days)>=3:
            top=max(abs(x) for _,x in days) or 1
            chart='\n'.join([f'📊 *XP por dia (últimos {len(days)} dias)*','```',*(f'{d[8:10]}/{d[5:7]} '+('█'*max(1,round(10*abs(x)/top))).ljust(10)+f' {kk(x)}'+(' 💀' if x<0 else '') for d,x in days),'```'])
        else: chart='_A curva diária começa a ser gravada agora e aparece em poucos dias._'
        return Reply(T_EVOLUTION,{'nome':name,'ficha':sheet,'xp_ganha':gained,'projecao':'\n'.join(projection),'grafico':chart,'level':pt(info['level']),'mundo':clean(info['world']),'vocacao':clean(info['vocation'])})

    def xp_notice(self,xp):
        lines=[]
        for window,m in xp.get('_meta',{}).items():
            period=self.xp_period(xp,window)
            if 'start' in m:
                when=lambda k:datetime.fromtimestamp(m[k],timezone.utc).strftime('%d/%m/%Y %H:%M UTC')
                lines.append(period+': '+kk(xp[window])+' · '+m['source']+' — '+when('start')+' a '+when('end')+(' (registro antigo).' if not m.get('fresh') else '.'))
            else:lines.append(period+': '+m['source']+' — '+str(m['date']).replace('T',' ')[:19]+(' (consulta UTC).' if 'T' in str(m['date']) else '.'))
        lines.extend(xp.get('_notes',[]))
        if not xp.get('_meta') and xp.get('_latest_total'):
            value=xp['_latest_total'];lines.append('TibiaData: XP total '+pt(value['value'])+' na coleta '+value['day']+'. Ganho exige duas coletas válidas em dias adjacentes.')
        return '\n'.join(lines) or 'GuildStats indisponível; acompanhamento complementar ainda sem histórico suficiente.'

    def xp_period(self,xp,window):
        if xp.get('_meta',{}).get(window,{}).get('source','').startswith('TibiaRise — ranking'):return 'Período publicado' if window==0 else str(window)+' dias (período publicado)'
        if xp.get('_meta',{}).get(window,{}).get('source','').startswith('TibiaRise'):return 'Último intervalo' if window==0 else str(window)+' intervalos diários'
        if xp.get('_meta',{}).get(window,{}).get('source','').startswith('TibiaData'):return 'Entre coletas' if window==0 else str(window)+' intervalos diários'
        return 'Ontem' if window==0 else str(window)+' dias'

    def xp_daily_line(self,row,xp,level=False):
        d,lv,x,source=row
        if source.startswith('GuildStats'):period=d[8:10]+'/'+d[5:7]
        else:
            m=xp['_daily_periods'][d];stamp=lambda k:datetime.fromtimestamp(m[k],timezone.utc).strftime('%d/%m %H:%M')
            period=stamp('start')+' → '+stamp('end')+' UTC'
        return period+' — '+('Lv *'+pt(lv)+'* — ' if level else '')+kk(x)+(' 💀' if x<0 else '')

    def measured_evolution(self,info,xp,today,sheet):
        import tibia_info
        gained='\n'.join(['*XP ganha*',*('• '+self.xp_period(xp,w)+': '+('*'+kk(xp[w])+'*' if xp[w] is not None else '—') for w in (0,7,30))])
        projection='🔮 Sem projeção: faltam 30 dias completos e atuais.'
        rate=xp.get('_rates',{}).get(30)
        if xp.get('_projection') and rate is not None:
            need=tibia_info.xp_total(info['level']+1)-tibia_info.xp_total(info['level'])
            projection='🔮 Sem ganho positivo no período: sem projeção.' if rate<=0 else '🔮 No ritmo observado: Lv '+pt(info['level']+1)+' em ~'+decimal_pt(need/rate,1)+' dias.'
        rows=xp.get('_daily',[])[:14]
        if rows:
            top=max(abs(row[2]) for row in rows) or 1
            lines=[]
            for day,level,value,source in rows:
                if day in xp.get('_daily_periods',{}):
                    period=xp['_daily_periods'][day];start=datetime.fromtimestamp(period['start'],timezone.utc);end=datetime.fromtimestamp(period['end'],timezone.utc)
                    label=start.strftime('%d/%m')+'→'+end.strftime('%d/%m')
                else:label=day[8:10]+'/'+day[5:7]
                bar='█'*max(1,round(10*abs(value)/top)) if value else ''
                lines.append(label.ljust(11)+' '+bar.ljust(10)+' '+kk(value)+(' 💀' if value<0 else ''))
            chart='\n'.join(['📊 *XP por dia*','```',*lines,'```'])
        else:chart='_Ainda sem histórico diário válido; dias ausentes não são zero._'
        source=xp.get('_source') or next((m['source'].split(' — ')[0] for m in xp.get('_meta',{}).values()),None)
        if source:
            old=not any(m.get('fresh') for m in xp.get('_meta',{}).values())
            chart+='\n_Fonte: '+source+(' · registro antigo' if old else '')+(' · até '+rows[0][0][8:10]+'/'+rows[0][0][5:7] if rows else '')+'._'
        if xp.get('_notes'):gained+='\n_'+ ' '.join(xp['_notes'])+'_'
        return Reply(T_EVOLUTION,{'nome':clean(info['name']),'ficha':sheet,'xp_ganha':gained,'projecao':projection,'grafico':chart,'level':pt(info['level']),'mundo':clean(info['world']),'vocacao':clean(info['vocation'])})

    def charinfo(self,arg,world,today):
        """Ficha completa de qualquer personagem (mesmo conteúdo do comando `char` do Tibia Tudo), no padrão do WhatsApp."""
        if not NAME.fullmatch(arg): return 'Use: *!char* <nome>   Ex.: !char Zazamyon'
        data=self.character(arg)
        info=((data or {}).get('character') or {}).get('character') or {}
        if not info.get('name'): return f'Não encontrei o personagem *{clean(arg)}*.'
        voc=clean(info.get('vocation','')) or '?'
        sheet=f'{emoji(voc) or "🛡️"} {voc} · 🏆 Level *{pt(info.get("level") or 0)}* · 🌍 {clean(info.get("world","?"))}'
        guild=info.get('guild') or {}
        guild_line=f'⚔️ *Guilda:* {clean(guild["name"])}'+(f' ({clean(guild["rank"])})' if guild.get('rank') else '') if guild.get('name') else ''
        houses=[f'{clean(h.get("name","?"),50)} ({clean(h.get("town","?"))})' for h in info.get('houses') or [] if isinstance(h,dict)]
        houses_line='🏠 *Casa(s):* '+', '.join(houses) if houses else ''
        residence=f'📍 *Residência:* {clean(info["residence"])}' if info.get('residence') else ''
        extra=[x for x in (f'🎖️ {pt(info["achievement_points"])} achievement points' if type(info.get('achievement_points')) is int else '',clean(info.get('account_status',''))) if x]
        login=''
        if info.get('last_login'):
            try: login=f'⏰ *Último login:* {brt(info["last_login"]).strftime("%d/%m/%y - %H:%M")}'
            except ValueError: pass
        deaths=[d for d in (data.get('character') or {}).get('deaths') or [] if isinstance(d,dict)][:8]
        if deaths:
            rows=[]
            for d in deaths:
                try: when=brt(d['time']).strftime('%d/%m/%Y')
                except (KeyError,ValueError): when='?'
                rows.append(f'· {when} — Lv {clean(d.get("level","?"),6)} — {clean(d.get("reason",""),120)}')
            death_block='\n'.join([f'{emoji(voc) or "💀"} *Mortes (últimos 30 dias)*',*rows])
        else: death_block='💀 Sem mortes nos últimos 30 dias.'
        return Reply(T_CHAR,{'nome':clean(info['name']),'ficha':sheet,'guilda':guild_line,'casas':houses_line,'residencia':residence,'extra':' · '.join(extra),'login':login,'mortes':death_block})

    def party(self,arg,world,today):
        """Party finder: jogadores online do mesmo mundo dentro da faixa de shared XP (mesma conta do Tibia Tudo: de 2/3 a 3/2 do level)."""
        import tibia_info
        words=arg.split();usage='Use: *!pt* <personagem> [voc]   Ex.: !pt Zazamyon ek'
        if not words or len(words)>4: return usage
        wanted=None
        if len(words)>1 and norm(words[-1]) in VOCATION_ALIASES: wanted=VOCATION_ALIASES[norm(words[-1])];words=words[:-1]
        typed=' '.join(words)
        if not NAME.fullmatch(typed): return usage
        info=self.sheet(typed)
        if not info or not WORLD.fullmatch(info.get('world') or ''): return f'Não encontrei o personagem *{clean(typed)}*.'
        low,high=tibia_info.faixa_shared(info['level'])
        online=self.online(info['world'])
        if online is None: return FAIL
        me=info['name'].casefold()
        found=[p for p in online if p['name'].casefold()!=me and low<=p['level']<=high and (wanted is None or vocation_code(p['vocation'])==wanted)]
        by_code={}
        for p in sorted(found,key=lambda p:p['name'].casefold()): by_code.setdefault(vocation_code(p['vocation']),[]).append(p)
        shown=[p for rows in by_code.values() for p in rows[:PARTY_PER_VOCATION]]
        with ThreadPoolExecutor(max_workers=8) as pool: guilds={p['name']:(g or {}).get('guild') for p,g in zip(shown,pool.map(lambda p:self.sheet(p['name']),shown))}
        groups=[]
        for code in ('EK','RP','ED','MS','EM'):
            rows=by_code.get(code,[])[:PARTY_PER_VOCATION]
            if not rows: continue
            block=[f'{emoji(rows[0]["vocation"])} *{clean(rows[0]["vocation"])}*']
            block+=[f'· 🟢 {emoji(p["vocation"])} [{code}] *{clean(p["name"])}* — Lv *{pt(p["level"])}* ({clean(guilds.get(p["name"]) or "Sem Guild")})' for p in rows]
            if len(by_code[code])>len(rows): block.append(f'…e mais {len(by_code[code])-len(rows)}')
            groups.append('\n'.join(block))
        return Reply(T_PARTY,{'nome':clean(info['name']),'filtro':f' — filtro {wanted}' if wanted else '','ficha':f'{emoji(info["vocation"])} [{vocation_code(info["vocation"])}] · 🏆 Lv *{pt(info["level"])}* · 🌍 {clean(info["world"])}',
                              'shared_min':pt(low),'shared_max':pt(high),'lista':'\n\n'.join(groups) if found else 'Ninguém online na faixa agora.'})

    def online_cmd(self,arg,world,today):
        """Quantos estão online no mundo (ou quem está online numa guild), como o comando `online` do Tibia Tudo."""
        target=arg or world
        if not target or not NAME.fullmatch(target): return 'Use: *!online* <mundo>   Ex.: !online Jadebra'
        info=self.world(target) if WORLD.fullmatch(target) else None
        if info:
            up=str(info.get('status','')).casefold()=='online'
            pvp=clean(info.get('pvp_type',''));mark='⚔️' if 'open' in pvp.casefold() else '🕊️' if 'optional' in pvp.casefold() else '💀' if 'hardcore' in pvp.casefold() else '⚔️'
            place=' · '.join(x for x in (f'📍 {clean(info.get("location",""))}' if info.get('location') else '',f'{mark} {pvp}' if pvp else '') if x)
            return Reply(T_ONLINE,{'bolinha':'🟢' if up else '🔴','nome':clean(info.get('name',target)),'estado':'Online' if up else 'Offline','jogadores':pt(info.get('players_online') or 0),'lugar':place})
        guild=self.guild(target)
        if not guild: return f'Não encontrei o mundo ou a guild *{clean(target)}*.'
        members=[m for m in guild.get('members') or [] if isinstance(m,dict) and m.get('status')=='online']
        members.sort(key=lambda m:-(m.get('level') or 0))
        rows=[f'{emoji(m.get("vocation"))} *{clean(m.get("name","?"))}* — Lv {pt(m.get("level") or 0)} ({clean(m.get("vocation","?"))})' for m in members[:15]]
        if len(members)>15: rows.append(f'…e mais {len(members)-15}')
        return Reply(T_ONLINE_GUILD,{'nome':clean(guild.get('name',target)),'online':len(members),'total':len(guild.get('members') or []),'lista':'\n'.join(rows)})

    def xptop(self,arg,world,today):
        """XP dia a dia do personagem. O histórico diário é gravado pelo próprio servidor (o GuildStats protege a aba diária), então só existe a partir de quando o bot começou a gravar."""
        import tibia_info
        if not NAME.fullmatch(arg): return 'Use: *!xptop* <personagem>   Ex.: !xptop Zazamyon'
        info=self.sheet(arg)
        if not info or not WORLD.fullmatch(info.get('world') or ''): return f'Não encontrei o personagem *{clean(arg)}*.'
        xp=self.xp(info);last=today-timedelta(days=1)
        sheet=f'{emoji(info["vocation"])} {clean(info["vocation"])} · 🏆 Level *{pt(info["level"])}* · 🌍 {clean(info["world"])}'
        guild_line=f'⚔️ *Guilda:* {clean(info["guild"])}' if info.get('guild') else ''
        if self.experience:
            rows=xp.get('_daily',[])[:30]
            daily='\n'.join(self.xp_daily_line(row,xp,True) for row in rows)
            template=T_XPTOP.replace('📅 até {ate}','📅 Datas e intervalos indicados abaixo').replace('*Resumo (GuildStats)*','*Resumo de XP*').replace('• Ontem: {xp_ontem}','• '+self.xp_period(xp,0)+': {xp_observado_0}').replace('• 7 dias: {xp_7d}','• '+self.xp_period(xp,7)+': {xp_observado_7}').replace('• 30 dias: *{xp_30d}*','• '+self.xp_period(xp,30)+': *{xp_observado_30}*')
            displayed={w:kk(xp[w]) if xp[w] is not None else '—' for w in (0,7,30)}
            legacy={w:displayed[w] if not xp.get('_meta',{}).get(w,{}).get('source','').startswith(('TibiaData','TibiaRise')) else '—' for w in (0,7,30)}
            end_day=max((r[0] for r in rows),default=last.isoformat())
            return Reply(template,{'ate':end_day[8:10]+'/'+end_day[5:7],'nome':clean(info['name']),'ficha':sheet,'guilda':guild_line,'dias':daily,
                'aviso':'_Fonte: '+str(xp.get('_source') or 'não disponível')+'. Dias ausentes não são zero._' if rows else '_Ainda sem histórico diário válido._',
                'xp_ontem':legacy[0],'xp_7d':legacy[7],'xp_30d':legacy[30],'xp_observado_0':displayed[0],'xp_observado_7':displayed[7],'xp_observado_30':displayed[30],'xp_media':kk(xp['_rates'][30]) if 30 in xp.get('_rates',{}) else '—'},self.xp_notice(xp))
        if xp[30] is None:
            lines=['📈 *XP — últimos 30 dias*',f'📅 até {last.strftime("%d/%m")}','',f'📜 *{clean(info["name"])}*',sheet,*([guild_line] if guild_line else []),'']
            return '\n'.join([*lines,'Sem dados de XP: o personagem está fora do top 500 do mundo no GuildStats.'])
        rows={d:(lv,x) for d,lv,x in self.daily(info['world'],info['name'])}
        days=[(last-timedelta(days=i)).isoformat() for i in range(30)]
        have=[d for d in days if d in rows]
        day_lines=[]
        for index,day in enumerate(have):
            lv,x=rows[day];older=rows.get(have[index+1][:10]) if index+1<len(have) and (date.fromisoformat(day)-date.fromisoformat(have[index+1])).days==1 else None
            trend='' if older is None else (' 📈' if x>older[1] else ' 📉')
            day_lines.append(f'{day[8:10]}/{day[5:7]} — Lv *{pt(lv)}* — {kk(x)}{trend}'+(' 💀' if x<0 else ''))
        if not have: note='_Ainda sem dados diários: o bot começou a gravar o XP por dia agora e a lista cresce a cada dia._'
        else: note=f'_Sem dados antes de {min(have)[8:10]}/{min(have)[5:7]}: o bot só grava o XP diário desde essa data._'
        return Reply(T_XPTOP,{'ate':last.strftime('%d/%m'),'nome':clean(info['name']),'ficha':sheet,'guilda':guild_line,'dias':'\n'.join(day_lines),'aviso':note,
                              'xp_ontem':kk(xp[0]) if xp[0] is not None else '—','xp_7d':kk(xp[7]) if xp[7] is not None else '—','xp_30d':kk(xp[30]),'xp_media':kk(xp[30]/30)})
