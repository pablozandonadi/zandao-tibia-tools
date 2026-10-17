"""Comandos de Tibia no chat do Assistente: bomdia, kill, boss, online, char, death, guild. Só dados públicos da TibiaData."""
import re
from string import capwords
from datetime import date, datetime, timedelta, timezone
from urllib.parse import quote

import guild_stats
import tibia_info
import zandaobot
import zandaobot_report
import zandaobot_sources as sources

COMANDO = re.compile(r'\s*!?\s*(bom\s?dia|kill|boss|online|char|death|guild)\b\s*(.*?)\s*', re.I | re.S)
MUNDO = re.compile(r'[A-Za-z]{2,40}')
NOME = re.compile(r"[A-Za-z][A-Za-z '\-.]{1,39}")
FALHA = 'Não consegui consultar a TibiaData agora (ou o nome não existe). Tente de novo em instantes.'
VOCACOES = ('Knight', 'Paladin', 'Sorcerer', 'Druid', 'Monk')
BRT = timezone(timedelta(hours=-3))
RANKING = 'https://guildstats.eu/top-experience?world={}&time=0'  # time=0 é "Yesterday"; só traz o top 500 do mundo


def _get(chave, endpoint):
    r = zandaobot._consultar(chave, endpoint)
    return r['dados'], r['velho']


def _data(texto, hora=False):
    try:
        d = datetime.fromisoformat(str(texto).replace('Z', '+00:00')).astimezone(BRT)
    except ValueError:
        return '❓'
    return d.strftime('%d/%m/%Y %H:%M' if hora else '%d/%m/%Y')


def _ficha(nome):
    """(personagem, mortes) ou None."""
    d, _ = _get('char:' + nome.lower(), '/character/' + quote(nome))
    bloco = d.get('character') or {}
    char = bloco.get('character') or {}
    if not char.get('name'):
        return None
    return char, bloco.get('deaths') if isinstance(bloco.get('deaths'), list) else []


def _mortes(deaths, limite):
    return [f"• {_data(m.get('time'))} — Lv {m.get('level', '?')} — {m.get('reason', '')}" for m in deaths[:limite] if isinstance(m, dict)]


def _kk(n):
    return f'{n / 1e9:.2f}kkk' if abs(n) >= 1e9 else f'{n / 1e6:.2f}kk'


def _ranking(mundo):
    """Top 500 de XP de ontem do mundo no GuildStats: [(nome, level, xp)] ou None."""
    def buscar():
        p = guild_stats.Tables()
        p.feed(sources.get_text(RANKING.format(quote(mundo)), 6_000_000))
        linhas = [(r[1], r[2], int(r[3].replace(',', ''))) for t in p.tables for r in t['rows']
                  if len(r) >= 7 and r[0].isdigit() and re.fullmatch(r'[+-]?[\d,]+', r[3])]
        if not linhas:
            raise ValueError('Ranking vazio')
        return linhas
    return sources.cached('gs-topxp:' + mundo.lower(), buscar, ttl=1800)['dados']


def _xp_guild(nome, mundo):
    d, _ = _get('guild:' + nome.lower(), '/guild/' + quote(nome))
    membros = {str(x.get('name', '')).casefold() for x in (d.get('guild') or {}).get('members') or [] if isinstance(x, dict)}
    ranking = _ranking(mundo) if membros and MUNDO.fullmatch(mundo or '') else None
    if ranking is None:
        return '🏆 Top XP de ontem: indisponível agora (GuildStats ou TibiaData).'
    achados = sorted((x for x in ranking if x[0].casefold() in membros), key=lambda x: -x[2])
    if not achados:
        return f'🏆 Top XP de ontem — {nome}: nenhum membro ficou no top 500 do mundo no GuildStats.'
    linhas = [f'🏆 Top XP de ontem — {nome} (GuildStats)']
    linhas += [f"{i}. {n} (Lv {lv}) — {'+' if xp >= 0 else '-'}{_kk(abs(xp))}" for i, (n, lv, xp) in enumerate(achados[:10], 1)]
    linhas.append(f'_{len(achados)} de {len(membros)} membros aparecem no top 500 de XP do mundo._')
    return '\n'.join(linhas)


def _ou(texto, rotulo):
    return f'{rotulo}: indisponível agora.' if texto == FALHA else texto


def _bomdia(rest, mundo, personagem, hoje):
    m = rest or mundo
    r = zandaobot.buscar(m)
    if r.get('erro'):
        return r['erro']
    msg = zandaobot_report.gerar(r, {'comunidade': 'tibianos', 'assinatura': personagem})
    extras = [_ou(_kill('', m), '⚔️ Criaturas mortas ontem')] if m and MUNDO.fullmatch(m) else []
    ficha = _ficha(personagem) if personagem and NOME.fullmatch(personagem) else None
    if ficha:
        char = ficha[0]
        guild = (char.get('guild') or {}).get('name')
        # a guild é do personagem em uso: com outro mundo explícito no comando, não se aplica
        if guild and (not rest or rest.casefold() == str(char.get('world', '')).casefold()):
            extras += [_ou(_guild(guild, hoje), '🏰 Guild'), _xp_guild(guild, char.get('world') or m)]
    if not extras:
        return msg
    corte = msg.rfind('⏰ Próximo SS')
    bloco = '\n\n'.join(extras)
    return msg + '\n\n' + bloco if corte < 0 else msg[:corte] + bloco + '\n\n' + msg[corte:]


def _kill(rest, mundo):
    m = rest or mundo
    if not m:
        return 'Informe o mundo, ex.: kill Antica.'
    if not MUNDO.fullmatch(m):
        return 'Nome de mundo inválido. Use só letras, ex.: kill Antica.'
    d, velho = _get('kills-todas:' + m.lower(), '/killstatistics/' + m)
    entradas = (d.get('killstatistics') or {}).get('entries')
    if not isinstance(entradas, list):
        return FALHA
    vivos = [(e['race'], e['last_day_killed']) for e in entradas if isinstance(e, dict) and isinstance(e.get('race'), str)
             and type(e.get('last_day_killed')) is int and e['last_day_killed'] > 0 and not e['race'].startswith('(')]
    if not vivos:
        return f'Sem abates registrados ontem em {m}.'
    top = sorted(vivos, key=lambda x: (-x[1], x[0]))[:10]
    linhas = [f'⚔️ Top 10 criaturas mortas ontem — 🌍 {m.capitalize()}' + (' (dados antigos)' if velho else '')]
    linhas += [f'{i}. {capwords(nome)} — {n:,} mortes'.replace(',', '.') for i, (nome, n) in enumerate(top, 1)]
    return '\n'.join(linhas)


def _boss(rest, mundo):
    m = rest or mundo
    b = tibia_info.boostados()
    linhas = ['👑 Bosses' + (f' — 🌍 {m.capitalize()}' if m else '')]
    linhas.append('⭐ Boss boosted: ' + ((b.get('boss') or {}).get('nome') or 'indisponível'))
    linhas.append('🧬 Criatura boosted: ' + ((b.get('criatura') or {}).get('nome') or 'indisponível'))
    if m:
        ks = zandaobot.killstatistics(m)
        mortos = [x['nome'] for x in ks.get('bosses', []) if (x.get('last_day_killed') or 0) > 0]
        if mortos:
            linhas.append('💀 Morreram ontem: ' + ', '.join(mortos))
        elif ks.get('consulta') is None:
            linhas.append('💀 Mortes de ontem indisponíveis agora.')
        else:
            linhas.append('💀 Nenhum boss monitorado morreu ontem.')
    else:
        linhas.append('Informe o mundo para ver quem morreu ontem, ex.: boss Antica.')
    return '\n'.join(linhas)


def _online(rest, mundo):
    alvo = rest or mundo
    if not alvo:
        return 'Informe o mundo ou a guild, ex.: online Antica.'
    if MUNDO.fullmatch(alvo):
        d, _ = _get('mundo:' + alvo.lower(), '/world/' + quote(alvo))
        w = d.get('world') or {}
        if w.get('name'):
            return f"🟢 {w['name']}: {w.get('players_online', '?')} players online."
    d, _ = _get('guild:' + alvo.lower(), '/guild/' + quote(alvo))
    g = d.get('guild') or {}
    membros = g.get('members')
    if not isinstance(membros, list):
        return FALHA
    on = sorted((x for x in membros if isinstance(x, dict) and x.get('status') == 'online'), key=lambda x: -(x.get('level') or 0))
    linhas = [f"🟢 {g.get('name', alvo)} online ({len(on)} de {len(membros)})"]
    linhas += [f"• Lv {x.get('level', '?')} {x.get('name', '?')} ({x.get('vocation', '?')})" for x in on[:15]]
    if len(on) > 15:
        linhas.append(f'… e mais {len(on) - 15}')
    return '\n'.join(linhas)


def _char(rest, mundo):
    if not NOME.fullmatch(rest):
        return 'Use: char <personagem>.'
    f = _ficha(rest)
    if not f:
        return FALHA
    c, deaths = f
    linhas = [f"📜 {c['name']}", f"🛡️ {c.get('vocation', '?')} · 🏆 Level {c.get('level', '?')} · 🌍 {c.get('world', '?')}"]
    if (c.get('guild') or {}).get('name'):
        linhas.append(f"⚔️ Guilda: {c['guild']['name']}")
    if c.get('last_login'):
        linhas.append(f"⏰ Último login: {_data(c['last_login'], True)} (BRT)")
    m = _mortes(deaths, 3)
    linhas += ['💀 Mortes recentes:', *m] if m else ['💀 Sem mortes nos últimos 30 dias.']
    return '\n'.join(linhas)


def _death(rest, mundo):
    if not NOME.fullmatch(rest):
        return 'Use: death <personagem>. O ranking de mortes do mundo vem numa próxima fase.'
    f = _ficha(rest)
    if not f:
        return FALHA
    c, deaths = f
    m = _mortes(deaths, 10)
    return '\n'.join([f"☠️ Mortes — {c['name']} (30 dias)", *m]) if m else f"☠️ {c['name']} não morreu nos últimos 30 dias."


def _guild(rest, hoje):
    if not NOME.fullmatch(rest):
        return 'Use: guild <nome>.'
    d, _ = _get('guild:' + rest.lower(), '/guild/' + quote(rest))
    g = d.get('guild') or {}
    membros = [x for x in g.get('members') or [] if isinstance(x, dict)]
    if not membros:
        return FALHA
    on = sum(1 for x in membros if x.get('status') == 'online')
    voc = ' · '.join(f"{v}: {sum(1 for x in membros if v in str(x.get('vocation')))}" for v in VOCACOES)
    corte = hoje - timedelta(days=7)
    novos = []
    for x in membros:
        try:
            if date.fromisoformat(str(x.get('joined'))[:10]) >= corte:
                novos.append(x)
        except ValueError:
            pass
    novos.sort(key=lambda x: x['joined'], reverse=True)
    linhas = [f"🏰 {g.get('name', rest)}", f"📅 Fundada em {g.get('founded', '❓')} · 🌍 {g.get('world', '❓')}",
              f'🟢 {on} de {len(membros)} online', f'🧙 {voc}']
    linhas += ['➕ Entraram (7 dias):', *[f"• {x.get('name', '?')} — Lv {x.get('level', '?')} ({_data(x['joined'])})" for x in novos]] if novos else ['➕ Entraram (7 dias): ninguém.']
    return '\n'.join(linhas)


def responder(texto, mundo='', hoje=None, personagem=''):
    """Resposta em texto, ou None quando a mensagem não é um destes comandos."""
    m = COMANDO.fullmatch(texto or '')
    if not m:
        return None
    cmd, rest = re.sub(r'\s', '', m[1].lower()), m[2]
    hoje = hoje or date.today()
    try:
        if cmd == 'bomdia':
            return _bomdia(rest, mundo, personagem, hoje)
        if cmd == 'guild':
            return _guild(rest, hoje)
        return {'kill': _kill, 'boss': _boss, 'online': _online, 'char': _char, 'death': _death}[cmd](rest, mundo)
    except Exception:
        return FALHA
