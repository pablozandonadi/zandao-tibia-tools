"""Mensagem compartilhável construída apenas com dados atuais e campos manuais."""
from datetime import datetime, timezone, timedelta
import mensagens_tibianas


def gerar(r, campos=None, extras=(), mini=True):
    """extras = blocos de texto das consultas marcadas; mini = incluir a seção de Mini World Changes."""
    c = campos if isinstance(campos, dict) else {}
    def text(key, default='❓'):
        value = str(c.get(key) or '').strip().replace('\n', ' ')[:200]
        return value or default
    def day(value):
        try:
            return datetime.fromisoformat(value[:10]).strftime('%d/%m/%Y')
        except (ValueError, TypeError):
            return '❓'
    board = r.get('world_board') or {}
    current = bool(board.get('valido'))
    events = board.get('eventos', []) if current else []
    ids = {e['id'] for e in events}
    def state(ident):
        return '🟢 Ativo' if ident in ids else '🔴 Inativo' if current and board.get('completo') else '❓'
    yasir = r.get('yasir') or {}
    y = '🟢 Ativo' if yasir.get('estado') == 'presente' else '🔴 Inativo' if yasir.get('estado') == 'ausente' else '❓'
    source = 'World Board manual' if yasir.get('origem') == 'world_board_manual' else 'consulta online'
    boosted = r.get('boostados') or {}
    def boost(key):
        return (boosted.get(key) or {}).get('nome', '❓') if not boosted.get('velho') and not boosted.get('aguardando') else '❓'
    lines = [f"🗓️ *{day(r.get('dia', ''))}*", '', f"☀️ Bom dia, {text('comunidade', 'tripulação')}! Que o dia traga boas caçadas e um baú cheio. 🏴‍☠️", '',
             '💬 *Mensagem do dia:*', mensagens_tibianas.proxima(), '', f"🌍 *Mundo:* {r.get('mundo') or '❓'}"]
    calendar = r.get('calendario') or {}
    active = [e for e in calendar.get('eventos', []) if e.get('estado') == 'ativo'] if not calendar.get('velho') else []
    for event in active:
        lines.append(f"🎉 *Evento:* {event['titulo']} (até {day(event['fim'])} no SS)")
        if event.get('descricao'):
            lines.append('_' + ' '.join(event['descricao'].split())[:350] + '_')
    if not active:
        lines.append('🎉 *Eventos:* ❓' if calendar.get('velho') or calendar.get('estado') != 'disponivel' else 'Nenhum listado no calendário')
    dream = r.get('dream_court') or {}
    lines += [f"🐪 *Yasir:* {y} ({source})", f"🧳 *Rashid:* {r.get('rashid') or '❓'}", f"⭐ *Criatura boostada:* {boost('criatura')}", f"👑 *Boss boostado:* {boost('boss')}", f"🌙 *Dream Court:* {(dream.get('nome') or '❓') if not dream.get('velho') else '❓'} · rotação prevista", f"🔱 *Boss Deeplings:* {text('deeplings')}", f"🧭 *Região boostada:* {text('regiao')}", f"⚙️ *Roshamuul:* {text('roshamuul')}", f"🚪 *Fury Gate:* {state('fury_gates')}", f"🪓 *Bibby's Bloodbath:* {state('warpath')}", f"🏟️ *Tibia Drome:* {text('drome', 'Rotação termina no SS de ' + day(calendar['drome_fim']) if calendar.get('drome_fim') else '❓')}", f"🪙 *Tibia Coin ({text('coin_hora')}):* comprar {text('coin_compra')} gp · vender {text('coin_venda')} gp", '']
    kills = r.get('killstatistics') or {}
    if kills.get('estado') == 'disponivel':
        counts = '; '.join(f"{b['nome']}: {b['last_day_killed'] if b.get('last_day_killed') is not None else '❓'}" for b in kills.get('bosses', []))
        lines[-1:-1] = [f"📊 *Dream Court — mortes (Last Day):* {counts}"]
    if mini:
        lines.append('🌍 *Outras world changes:*')
        lines += [f"• {e.get('rotulo', e['nome'])} · {e.get('local', '')}" + (f" · {e['detalhe']}" if e.get('detalhe') else '') for e in events if e['id'] not in ('oriental_trader', 'fury_gates', 'warpath')]
        online = [n for n in yasir.get('mudancas') or [] if isinstance(n, str) and n != 'Oriental Trader']
        if current:
            observed = datetime.fromtimestamp(board['consulta'], timezone(timedelta(hours=-3))).strftime('%H:%M')
            lines.append(f"_World Board manual às {observed} (Brasília) · {'completo' if board.get('completo') else 'parcial'} · pode mudar após a consulta._")
        elif online:
            lines += [f'• {n}' for n in online]
            lines.append('_Consulta online' + (' anterior' if yasir.get('mudancas_velhas') else '') + ' · World Board de hoje não registrado neste perfil._')
        else:
            lines.append('❓ World Board de hoje ainda não registrado neste perfil.')
    else:
        lines.pop()  # sem a seção, sai a linha em branco que a separava
    for bloco in extras:
        lines += ['', bloco]
    try:
        save = datetime.fromtimestamp(r['server_save_ms'] / 1000, timezone(timedelta(hours=-3))).strftime('%d/%m/%Y às %H:%M')
    except (KeyError, TypeError, ValueError):
        save = '❓'
    lines += ['', f"⏰ Próximo SS: {save} (Brasília)", '', '🏴‍☠️ _' + text('assinatura', r.get('personagem') or 'ZandaoBot') + '_']
    return '\n'.join(lines)
