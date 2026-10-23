"""Respostas dos comandos do grupo (!help, !precocoin, !duelo, !evolucao): só leitura de fontes públicas, no padrão de texto do WhatsApp.

As fontes entram por funções injetáveis (testes sem rede). Nomes vindos de fora passam por `clean` antes de entrar na mensagem.
"""
import re
import threading
import time
import unicodedata
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import quote

NAME=re.compile(r"[A-Za-z][A-Za-z '\-.]{1,39}")
WORLD=re.compile(r'[A-Za-z]{2,40}')
RANKING='https://guildstats.eu/top-experience?world={}&time={}'  # time: 0 = ontem, 7 e 30 = dias; só o top 500 do mundo
CACHE_TTL=600
FAIL='Não consegui consultar agora. Tente de novo em instantes.'
PACKAGE_TC=250
PACKAGE_REAIS=(Decimal(49),Decimal(52))  # mesmo padrão da calculadora do app
EMOJI={'knight':'🛡️','paladin':'🏹','druid':'❄️','sorcerer':'🔥','monk':'👊'}

HELP='''📖 *Comandos do bot*

• *!help* — esta lista
• *!duelo* <char1> x <char2> — dois chars lado a lado e quem passa quem no ritmo atual
• *!evolucao* <char> — XP dos últimos 30 dias e projeção de level
• *!precocoin* <mundo> — cotação do Tibia Coin no Tibia Tudo

Ex.: !duelo Fulano x Ciclano
_Um comando a cada poucos segundos por pessoa._'''

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

def emoji(vocation): return EMOJI.get(next((k for k in EMOJI if k in str(vocation).casefold()),''),'')

def short(date_value): return date_value.strftime('%d/%m/%y')

def span(days):
    return f'~{round(days)} dias' if days<60 else f'~{round(days/30)} meses'

# ---- fontes (padrão: rede; nos testes são trocadas) ----
_cache={};_lock=threading.Lock()

def cached(key,fetch):
    with _lock:
        hit=_cache.get(key)
        if hit and time.monotonic()-hit[0]<CACHE_TTL: return hit[1]
    value=fetch()
    with _lock: _cache[key]=(time.monotonic(),value)
    return value

def default_ranking(world,window):
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
    try: return cached(('rank',world.casefold(),window),fetch)
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
    return {'name':info['name'],'level':info.get('level'),'vocation':info.get('vocation',''),'world':info.get('world','')} if info and type(info.get('level')) is int else None

def default_trade(world):
    import tibiatrade_cotacao
    return tibiatrade_cotacao.consultar(world)

class Bot:
    def __init__(self,ranking=None,sheet=None,trade=None,history=None,track=None):
        self.ranking=ranking or default_ranking;self.sheet=sheet or default_sheet;self.trade=trade or default_trade
        self.history=history or (lambda world,name:[]);self.track=track or (lambda world:None)

    def handle(self,text,world='',today=None):
        """Resposta ao comando, ou None se não for um comando conhecido (comandos de outros bots no grupo passam em silêncio)."""
        found=re.fullmatch(r'!\s*(\S+)\s*(.*)',str(text).strip(),re.S)
        if not found: return None
        handler={'help':self.help,'ajuda':self.help,'comandos':self.help,'precocoin':self.coin,'tc':self.coin,
                 'duelo':self.duel,'evolucao':self.evolution,'evo':self.evolution}.get(norm(found[1]))
        if not handler: return None
        try: return handler(' '.join(found[2].split()),world,today or date.today())
        except Exception: return FAIL

    def help(self,arg,world,today): return HELP

    def coin(self,arg,world,today):
        mundo=arg or world
        if not WORLD.fullmatch(mundo or ''): return 'Use: *!precocoin* <mundo>   Ex.: !precocoin Rasteibra'
        r=self.trade(mundo);price=r.get('gold_por_tc');title=f'🪙 *Tibia Coin — {clean(mundo.capitalize())}*'
        if r.get('estado') not in ('ok','antiga') or type(price) is not int or price<=0:
            return f"{title}\nCotação indisponível agora. {clean(r.get('motivo',''),120)}".strip()
        when=str(r.get('data_base',''))[:10];when=f'{when[8:10]}/{when[5:7]}' if re.fullmatch(r'\d{4}-\d{2}-\d{2}',when) else '❓'
        per_kk=Decimal(1_000_000)/price;low,high=(per_kk*value/PACKAGE_TC for value in PACKAGE_REAIS)
        old='⚠️ _Cotação antiga: o TibiaTrade ainda não atualizou este mundo._' if r.get('estado')=='antiga' else '_Média diária de venda do TibiaTrade; não é o Market em tempo real._'
        return '\n'.join([title,f'• 1 TC ≈ *{pt(price)}* gold (média de venda, {when})',
                          f'• 1kk de gold ≈ *{decimal_pt(per_kk)} TC* ≈ R$ {decimal_pt(low)} a R$ {decimal_pt(high)}',
                          f'• Pacote de {PACKAGE_TC} TC: R$ {decimal_pt(PACKAGE_REAIS[0])} a R$ {decimal_pt(PACKAGE_REAIS[1])}',old])

    def xp(self,info):
        """XP de ontem, 7 e 30 dias de um personagem (None onde está fora do top 500 do mundo)."""
        world=info['world'];self.track(world);values={}
        for window in (0,7,30):
            rows=self.ranking(world,window)
            row=next((r for r in rows or () if r[0].casefold()==info['name'].casefold()),None)
            values[window]=row[2] if row else None
        return values

    def duel(self,arg,world,today):
        usage='Use: *!duelo* <char1> x <char2>   Ex.: !duelo Fulano x Ciclano'
        found=re.fullmatch(r'(.+?)\s+x\s+(.+)',arg,re.I)
        if not found or not all(NAME.fullmatch(n.strip()) for n in found.groups()): return usage
        pair=[]
        for typed in found.groups():
            info=self.sheet(typed.strip())
            if not info or not WORLD.fullmatch(info.get('world') or ''): return f'Não encontrei o personagem *{clean(typed)}*.'
            pair.append({**info,'xp':self.xp(info)})
        a,b=pair;label=lambda p:(clean(p['name'],40) if len(clean(p['name'],40))<=11 else clean(p['name'],10)+'…')
        rows=[('Level',*(pt(p['level']) for p in pair)),
              ('XP no mês',*(kk(p['xp'][30]) if p['xp'][30] is not None else '—' for p in pair)),
              ('XP/dia',*(kk(p['xp'][30]/30) if p['xp'][30] is not None else '—' for p in pair)),
              ('XP 7 dias',*(kk(p['xp'][7]) if p['xp'][7] is not None else '—' for p in pair)),
              ('XP ontem',*(kk(p['xp'][0]) if p['xp'][0] is not None else '—' for p in pair))]
        widths=[max(len(r[i]) for r in [('',label(a),label(b)),*rows]) for i in range(3)]
        line=lambda r:'  '.join(r[i].ljust(widths[i]) if i==0 else r[i].rjust(widths[i]) for i in range(3))
        lines=[f'⚔️ *{clean(a["name"])} x {clean(b["name"])}* — últimos 30 dias','```',line(('',label(a),label(b))),*(line(r) for r in rows),'```']
        missing=[clean(p['name']) for p in pair if p['xp'][30] is None]
        if missing: lines.append(f'_Sem dados de XP de {", ".join(missing)}: fora do top 500 do mundo no GuildStats._')
        else: lines.append(self.verdict(a,b,today))
        return '\n'.join(lines)

    def verdict(self,a,b,today):
        import tibia_info
        front,behind=(a,b) if a['level']>=b['level'] else (b,a)
        if front['level']==behind['level']: return '🤝 Os dois estão no mesmo level.'
        rate_front,rate_behind=front['xp'][30]/30,behind['xp'][30]/30
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
        lines=[f'📈 *Evolução — {name}*',f'{emoji(info["vocation"])} {clean(info["vocation"])} · 🏆 Lv *{pt(info["level"])}* · 🌍 {clean(info["world"])}'.replace('  ',' ').strip(),'']
        if xp[30] is None:
            return '\n'.join([*lines,'Sem dados de XP: o personagem está fora do top 500 do mundo no GuildStats.'])
        rate=xp[30]/30
        lines+=['*XP ganha*',f'• Ontem: *{kk(xp[0])}*' if xp[0] is not None else '• Ontem: — (fora do top 500 de ontem)',
                f'• 7 dias: *{kk(xp[7])}* (média {kk(xp[7]/7)}/dia)' if xp[7] is not None else '• 7 dias: —',
                f'• 30 dias: *{kk(xp[30])}* (média {kk(rate)}/dia)','']
        need=tibia_info.xp_total(info['level']+1)-tibia_info.xp_total(info['level'])
        lines.append('🔮 *Projeção no ritmo atual (média de 30 dias)*')
        if rate>0:
            per_level=need/rate;lines.append(f'• Cada level custa ~{kk(need)} ≈ *{decimal_pt(per_level,1)} dias*')
            days_left=max(1,round(per_level));lines.append(f'• Lv {pt(info["level"]+1)} em até ~{days_left} {"dia" if days_left==1 else "dias"} ({short(today+timedelta(days=per_level))})')
        else: lines.append('• Sem ganho de XP nos últimos 30 dias: sem projeção.')
        days=[(d,x) for d,x in self.history(info['world'],info['name']) if x is not None][-14:]
        if len(days)>=3:
            top=max(abs(x) for _,x in days) or 1
            lines+=['',f'📊 *XP por dia (últimos {len(days)} dias)*','```',*(f'{d[8:10]}/{d[5:7]} '+('█'*max(1,round(10*abs(x)/top))).ljust(10)+f' {kk(x)}'+(' 💀' if x<0 else '') for d,x in days),'```']
        else: lines+=['','_A curva diária começa a ser gravada agora e aparece em poucos dias._']
        return '\n'.join(lines)
