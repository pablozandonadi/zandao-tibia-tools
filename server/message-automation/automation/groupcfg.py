"""Configuração pelo próprio grupo: administradores do grupo usam !set e !alerta.

O que se cria aqui é o mesmo registro que o app cria (aparece na lista do app, com a marca "criado pelo grupo") e conta nos mesmos limites do dono.
Só chega aqui quem a ponte confirmou como administrador do grupo; o texto recebido nunca é gravado.
"""
import re
from urllib.parse import quote
from .botcmds import KEYS, WORLD, clean, norm
from datetime import datetime
from zoneinfo import ZoneInfo
from .domain import BLOCKS, Invalid, validate
from .watch import GUILD, tibia_json, validate_watch

COOLDOWN_MIN, COOLDOWN_MAX = 3, 86400
COMMAND = re.compile(r'!\s*(set|alerta|bomdia)\b\s*(.*)', re.I | re.S)
ZONE = 'America/Sao_Paulo'
DEFAULT_SEND = '06:00'
TEST_WORDS = ('teste', 'test', 'agora')
GENERATE_BEFORE = 10  # minutos: a mensagem é montada 10 min antes de ir para o grupo
SIGNATURE = 'TibiaTudo IA, acesso o site https://tibia-tudo.web.app\nby Zandão'
BOMDIA_ITEMS = 'data, saudação, mensagem do dia, mundo, eventos do Tibia, Yasir, Rashid, criatura boostada, boss boostado, Dream Court, mortes do Dream Court, outras world changes e próximo SS'
# Consultas adicionais sempre incluídas; as duas da guild só entram quando o grupo tem uma guild definida (!bomdia guild ou !alerta guild).
BOMDIA_EXTRAS = ('noticias', 'kill', 'exp_mundo', 'transfer')
BOMDIA_GUILD_EXTRAS = ('exp_guild', 'guild')
BOMDIA_EXTRAS_TEXT = 'notícias do Tibia, top 10 criaturas mortas ontem, top 10 XP do servidor e transferências de mundo'
UNITS = {'s': 1, 'm': 60, 'h': 3600}
TOGGLE = {'on': True, 'ligar': True, 'ligado': True, 'sim': True, 'off': False, 'desligar': False, 'desligado': False, 'nao': False}
COMMANDS = tuple(KEYS.values())

SET_HELP = '''⚙️ *!set — configurações do grupo (só admins)*
• *!set* — mostra tudo
• *!set world* <mundo> — mundo padrão dos comandos   ex: !set world Jadebra
• *!set cooldown* <tempo> — espera por pessoa entre comandos   ex: 30s · 2m · 1h (de 3s a 24h)
• *!set comandos* on/off — liga ou pausa o bot neste grupo
• *!set cmd* <comando> on/off — liga/desliga um comando só aqui   ex: !set cmd duelo off
_Comandos: ''' + ', '.join(COMMANDS) + '_'

ALERT_HELP = '''🚨 *!alerta — avisos de morte e level up da guild (só admins)*
• *!alerta* — mostra o alerta deste grupo
• *!alerta guild* <nome> — cria ou troca a guild   ex: !alerta guild Piratas do Rocks
• *!alerta level* <n> — avisa a cada n levels (1 = todo level)
• *!alerta mortes* on/off · *!alerta ups* on/off
• *!alerta limite hora* <n> — máximo por hora (0 = sem limite)
• *!alerta limite minuto* <n> — máximo por minuto (1 a 120)
• *!alerta on* / *off* — liga ou pausa · *!alerta remover* — apaga'''


BOMDIA_HELP = '''☀️ *!bomdia — mensagem de bom dia automática (só admins)*
• *!bomdia* — mostra como está
• *!bomdia on* / *off* — liga ou pausa (liga às ''' + DEFAULT_SEND + '''; horário de Brasília)
• *!bomdia horario* <hh:mm> — hora do envio   ex: !bomdia horario 07:30
• *!bomdia guild* <nome> — guild do top XP e do resumo (ou *auto*: usa a do !alerta)
• *!bomdia teste* — manda um bom dia agora, só para ver (não conta como o de hoje)
• *!bomdia remover* — apaga a rotina
_A mensagem sempre vem completa: ''' + BOMDIA_ITEMS + '''._'''


def parse_clock(text):
    found = re.fullmatch(r'(\d{1,2})(?:[:h](\d{2})?)?', str(text).strip().casefold())
    if not found or int(found[1]) > 23 or int(found[2] or 0) > 59:
        raise Invalid('Use o horário assim: 06:00 (horário de Brasília).')
    return f'{int(found[1]):02d}:{int(found[2] or 0):02d}'


def generation_clock(send):
    minutes = max(0, int(send[:2]) * 60 + int(send[3:]) - GENERATE_BEFORE)
    return f'{minutes // 60:02d}:{minutes % 60:02d}'


def parse_duration(text):
    found = re.fullmatch(r'(\d{1,6})\s*([smh]?)', str(text).strip().casefold())
    if not found:
        raise Invalid('Use um número com s, m ou h. Ex.: 30s, 2m, 1h.')
    seconds = int(found[1]) * UNITS[found[2] or 's']
    if not COOLDOWN_MIN <= seconds <= COOLDOWN_MAX:
        raise Invalid('O intervalo vai de 3 segundos a 24 horas.')
    return seconds


def duration_text(seconds):
    for unit, label in ((3600, 'h'), (60, 'min')):
        if seconds >= unit and seconds % unit == 0:
            return f'{seconds // unit} {label}'
    return f'{seconds} s'


def toggle(word):
    value = TOGGLE.get(norm(word))
    if value is None:
        raise Invalid('Use on ou off.')
    return value


def number(word, low, high, label):
    if not re.fullmatch(r'\d{1,6}', str(word)) or not low <= int(word) <= high:
        raise Invalid(f'{label}: um número de {low} a {high}.')
    return int(word)


def default_guild_exists(name):
    """True/False se a TibiaData conhece a guild; None se não deu para conferir agora."""
    try:
        return bool((tibia_json('/guild/' + quote(name)).get('guild') or {}).get('name'))
    except Exception:
        return None


class GroupConfig:
    def __init__(self, store, guild_exists=None, generator=None):
        self.store = store
        self.guild_exists = guild_exists or default_guild_exists
        self.generator = generator  # monta a mensagem do bom dia (nos testes, uma função falsa)

    @staticmethod
    def is_slow(text):
        """!bomdia teste consulta várias fontes: o bot mostra "digitando…" enquanto monta."""
        parsed = GroupConfig.parse(text)
        return bool(parsed and parsed[0] == 'bomdia' and parsed[1] and norm(parsed[1][0]) in TEST_WORDS)

    def make_message(self, config, now):
        if self.generator:
            return self.generator(config, now)['text']
        from mensagem_automatica_report import generate
        return generate(config, now)['text']

    @staticmethod
    def parse(text):
        """('set'|'alerta', argumentos) ou None se a linha não é um comando de configuração."""
        found = COMMAND.fullmatch(str(text).strip())
        return (norm(found[1]), found[2].split()) if found else None

    def handle(self, key, owner, item, now):
        """Executa o comando de um administrador e devolve o texto da resposta (erros viram aviso, nunca exceção)."""
        parsed = self.parse(item['text'])
        try:
            current = self.store.get(owner, key, 'botgroup')['data']
            run = {'set': lambda: self.set(owner, key, current, parsed[1], now), 'alerta': lambda: self.alert(owner, current, parsed[1], now),
                   'bomdia': lambda: self.bomdia(owner, current, parsed[1], now)}[parsed[0]]
            return run()
        except Invalid as error:
            return f'⚠️ {error}'

    # ---- !set ----
    def save(self, owner, key, current, changes, now, message):
        self.store.update(owner, key, 'botgroup', {**current, **changes, 'changedByGroup': int(now.timestamp())}, 'active')
        return message

    def set(self, owner, key, current, args, now):
        sub = norm(args[0]) if args else ''
        rest = args[1:]
        if sub in ('', 'status', 'ver'):
            return self.summary(owner, current, now)
        if sub in ('ajuda', 'help'):
            return SET_HELP
        if sub in ('world', 'mundo'):
            if not rest:
                return f'🌍 Mundo do grupo: *{clean(current["world"])}*'
            name = ' '.join(rest)
            if not WORLD.fullmatch(name):
                raise Invalid('Informe só o nome do mundo. Ex.: !set world Jadebra')
            reply = self.save(owner, key, current, {'world': name.capitalize()}, now, f'🌍 Mundo do grupo agora: *{name.capitalize()}*')
            self.follow_world(owner, current, name.capitalize(), now)  # o bom dia deste grupo acompanha o mundo
            return reply
        if sub == 'cooldown':
            if not rest:
                return f'⏳ Cada pessoa espera *{duration_text(current["cooldown"])}* entre comandos.'
            seconds = parse_duration(''.join(rest))
            return self.save(owner, key, current, {'cooldown': seconds}, now, f'⏳ Agora cada pessoa espera *{duration_text(seconds)}* entre comandos.')
        if sub in ('comandos', 'bot'):
            if not rest:
                return '🤖 Comandos: *' + ('pausados' if current.get('paused') else 'ligados') + '* neste grupo.'
            on = toggle(rest[0])
            return self.save(owner, key, current, {'paused': not on}, now, '🤖 Comandos *ligados* neste grupo.' if on else '⏸️ Comandos *pausados* neste grupo. Use !set comandos on para voltar.')
        if sub == 'cmd':
            name = norm(rest[0]).lstrip('!') if rest else ''
            if name not in COMMANDS or len(rest) != 2:
                raise Invalid('Use: !set cmd <comando> on/off. Comandos: ' + ', '.join(COMMANDS))
            on = toggle(rest[1])
            disabled = [c for c in current.get('disabled', []) if c != name] + ([] if on else [name])
            return self.save(owner, key, current, {'disabled': sorted(disabled)}, now, f'✅ *!{name}* ligado neste grupo.' if on else f'🚫 *!{name}* desligado neste grupo.')
        raise Invalid('Não entendi. Veja: !set ajuda')

    def summary(self, owner, current, now):
        lines = ['⚙️ *Configuração do grupo*', f'🌍 Mundo: *{clean(current["world"])}*', f'⏳ Espera por pessoa: *{duration_text(current["cooldown"])}*',
                 '🤖 Comandos: *' + ('pausados' if current.get('paused') else 'ligados') + '*']
        if current.get('disabled'):
            lines.append('🚫 Desligados aqui: ' + ', '.join(current['disabled']))
        lines.append(self.alert_status(self.find_watch(owner, current)))
        lines.append(self.bomdia_status(self.find_bomdia(owner, current), now))
        lines.append('_Veja: !set ajuda · !alerta ajuda · !bomdia ajuda_')
        return '\n'.join(lines)

    # ---- !bomdia ----
    def subscriptions(self, owner, current):
        return [s for s in self.store.list(owner, 'subscription') if s['state'] != 'revoked' and s['data'].get('destination') == current['destination']]

    def find_bomdia(self, owner, current):
        return next((s for s in self.subscriptions(owner, current) if s['data'].get('source') == 'group'), None)

    @staticmethod
    def bomdia_config(world, send, guild=''):
        """Sempre a mensagem inteira (os 13 itens + as consultas adicionais marcadas) com a assinatura do TibiaTudo IA; só mundo, horário e guild variam."""
        extras = {k: True for k in BOMDIA_EXTRAS + (BOMDIA_GUILD_EXTRAS if guild else ())}
        return validate({'personagem': 'TibiaTudo IA', 'mundo': world, 'blocks': {k: True for k in BLOCKS}, 'extras': extras, 'args': {k: guild for k in BOMDIA_GUILD_EXTRAS} if guild else {},
                         'fields': {'assinatura': True}, 'values': {'assinatura': SIGNATURE}, 'generateAt': generation_clock(send), 'sendAt': send, 'timezone': ZONE}, schedule=True)

    def bomdia_guild(self, owner, current, sub=None):
        """Guild das consultas da guild: a escolhida em !bomdia guild ou, se não houver, a do alerta deste grupo."""
        chosen = (sub or {}).get('data', {}).get('guild', '') if sub else ''
        if chosen:
            return chosen
        watch = self.find_watch(owner, current)
        return watch['data']['guild'] if watch else ''

    def refresh_bomdia(self, owner, current, now, **changes):
        """Reconstrói a rotina de bom dia do grupo com o mundo, o horário e a guild atuais (muda só se algo mudou)."""
        sub = self.find_bomdia(owner, current)
        if not sub:
            return None
        data = {**sub['data'], **{k: v for k, v in changes.items() if k == 'guild'}}
        config = self.bomdia_config(changes.get('world', current['world']), changes.get('send', sub['data']['config']['sendAt']), self.bomdia_guild(owner, current, {'data': data}))
        if config != sub['data']['config'] or data != sub['data']:
            self.store.update(owner, sub['id'], 'subscription', {**data, 'config': config, 'changedByGroup': int(now.timestamp())}, sub['state'])
        return self.find_bomdia(owner, current)

    def follow_world(self, owner, current, world, now):
        self.refresh_bomdia(owner, current, now, world=world)

    @staticmethod
    def bomdia_status(sub, now):
        if not sub:
            return '☀️ Bom dia automático: desligado (ligue com !bomdia on)'
        config = sub['data']['config']
        local = now.astimezone(ZoneInfo(ZONE)).strftime('%H:%M')
        when = 'hoje' if local < config['generateAt'] else 'amanhã'
        guild = config['args'].get('exp_guild', '')
        extras = BOMDIA_EXTRAS_TEXT + (f', top XP da guild e resumo da guild ({clean(guild)})' if guild else '')
        return '\n'.join([f'☀️ *Bom dia automático* — {"ligado" if sub["state"] == "active" else "pausado"}', f'🕕 Envio às *{config["sendAt"]}* (Brasília; agora são {local}) · 🌍 {clean(config["mundo"])}',
                          f'📋 Sempre completo: {BOMDIA_ITEMS}.', f'➕ Consultas: {extras}.'] + ([] if guild else ['ℹ️ Para incluir top XP e resumo da guild: !bomdia guild <nome> (ou !alerta guild <nome>).'])
                         + ([f'➡️ Próximo envio: {when} às {config["sendAt"]}.'] if sub['state'] == 'active' else []))

    def bomdia(self, owner, current, args, now):
        sub = self.find_bomdia(owner, current)
        word = norm(args[0]) if args else ''
        rest = args[1:]
        if word in ('ajuda', 'help'):
            return BOMDIA_HELP
        if word in ('', 'status', 'ver'):
            return self.bomdia_status(sub, now)
        stamp = int(now.timestamp())
        if word in ('on', 'ligar', 'off', 'desligar'):
            on = word in ('on', 'ligar')
            if sub:
                sub = self.refresh_bomdia(owner, current, now) or sub
                self.store.update(owner, sub['id'], 'subscription', {**sub['data'], 'changedByGroup': stamp}, 'active' if on else 'inactive')
                return self.bomdia_status({**sub, 'state': 'active' if on else 'inactive'}, now) if on else '⏸️ Bom dia automático *pausado*. Volte com !bomdia on.'
            if not on:
                return '☀️ O bom dia automático já está desligado.'
            if any(s['state'] == 'active' for s in self.subscriptions(owner, current)):
                raise Invalid('Este grupo já recebe uma rotina de bom dia criada no app. Pause-a lá para usar o !bomdia.')
            config = self.bomdia_config(current['world'], DEFAULT_SEND, self.bomdia_guild(owner, current))
            try:
                self.store.create(owner, 'subscription', {'config': config, 'connection': current['connection'], 'destination': current['destination'], 'source': 'group', 'createdAt': stamp}, 'active', limit=5)
            except Invalid:
                raise Invalid('O dono do bot já usa todas as rotinas permitidas. Apague uma no app para criar esta.') from None
            return self.bomdia_status(self.find_bomdia(owner, current), now)
        if word in TEST_WORDS:
            config = sub['data']['config'] if sub else self.bomdia_config(current['world'], DEFAULT_SEND, self.bomdia_guild(owner, current))
            try:
                text = self.make_message(config, now)
            except Exception:
                raise Invalid('Não consegui montar o bom dia agora (alguma fonte está fora do ar). Tente de novo em instantes.') from None
            return '🧪 *Teste do bom dia* — não conta como o envio de hoje.\n\n' + text
        if word in ('horario', 'hora'):
            if not sub:
                raise Invalid('Ligue primeiro com !bomdia on.')
            if not rest:
                return f'🕕 Envio às *{sub["data"]["config"]["sendAt"]}* (Brasília).'
            send = parse_clock(''.join(rest))
            self.refresh_bomdia(owner, current, now, send=send)
            local = now.astimezone(ZoneInfo(ZONE)).strftime('%H:%M')
            return f'🕕 Bom dia será enviado às *{send}* (Brasília). Agora são {local} em Brasília: próximo envio *{"amanhã" if local >= send else "hoje"}*. Para ver como fica agora: !bomdia teste'
        if word == 'guild':
            if not sub:
                raise Invalid('Ligue primeiro com !bomdia on.')
            if not rest:
                guild = self.bomdia_guild(owner, current, sub)
                return f'🏰 Guild das consultas do bom dia: *{clean(guild)}*' if guild else '🏰 Nenhuma guild definida. Use: !bomdia guild <nome>'
            name = ' '.join(rest)
            if norm(name) in ('auto', 'limpar'):
                self.refresh_bomdia(owner, current, now, guild='')
                return '🏰 Guild do bom dia: agora segue o !alerta guild do grupo (se houver).'
            if not GUILD.fullmatch(name):
                raise Invalid('Informe o nome da guild. Ex.: !bomdia guild Piratas do Rocks')
            found = self.guild_exists(name)
            if found is None:
                raise Invalid('Não consegui conferir a guild agora. Tente de novo em instantes.')
            if not found:
                raise Invalid(f'Não encontrei a guild *{clean(name)}*.')
            self.refresh_bomdia(owner, current, now, guild=name)
            return f'🏰 O bom dia agora inclui top XP e resumo da guild *{clean(name)}*.'
        if word in ('remover', 'apagar', 'excluir'):
            if not sub:
                return '☀️ Nenhuma rotina de bom dia neste grupo.'
            self.store.update(owner, sub['id'], 'subscription', sub['data'], 'revoked')
            return '🗑️ Bom dia automático removido.'
        raise Invalid('Não entendi. Veja: !bomdia ajuda')

    # ---- !alerta ----
    def find_watch(self, owner, current):
        return next((w for w in self.store.list(owner, 'watch') if w['state'] != 'revoked' and w['data'].get('destination') == current['destination']), None)

    @staticmethod
    def alert_status(watch):
        if not watch:
            return '🚨 Alerta da guild: nenhum (crie com !alerta guild <nome>)'
        d = watch['data']
        return '\n'.join([f'🚨 *Alerta da guild* — {"ligado" if watch["state"] == "active" else "pausado"}', f'🏰 Guild: *{clean(d["guild"])}*',
                          f'🔺 Level up: a cada *{d["milestone"]}* · ' + ('💀 mortes: sim' if d['deaths'] else '💀 mortes: não') + ' · ' + ('ups: sim' if d['ups'] else 'ups: não'),
                          '⏱️ Limite: ' + ('sem limite por hora' if d['hourlyCap'] == 0 else f'{d["hourlyCap"]} por hora') + f' · {d["perMinute"]} por minuto'])

    def change_watch(self, owner, watch, changes, now, message, state=None):
        data = {**watch['data'], **validate_watch({**watch['data'], **changes}), 'changedByGroup': int(now.timestamp())}
        self.store.update(owner, watch['id'], 'watch', data, state or watch['state'])
        return message

    def alert(self, owner, current, args, now):
        sub = norm(args[0]) if args else ''
        rest = args[1:]
        watch = self.find_watch(owner, current)
        if sub in ('ajuda', 'help'):
            return ALERT_HELP
        if sub in ('', 'status', 'ver'):
            return self.alert_status(watch)
        if sub == 'guild':
            name = ' '.join(rest)
            if not GUILD.fullmatch(name):
                raise Invalid('Informe o nome da guild. Ex.: !alerta guild Piratas do Rocks')
            found = self.guild_exists(name)
            if found is None:
                raise Invalid('Não consegui conferir a guild agora. Tente de novo em instantes.')
            if not found:
                raise Invalid(f'Não encontrei a guild *{clean(name)}*.')
            if watch:
                reply = self.change_watch(owner, watch, {'guild': name}, now, f'🏰 Alerta agora acompanha a guild *{clean(name)}*.')
                self.refresh_bomdia(owner, current, now)
                return reply
            try:
                self.store.create(owner, 'watch', {**validate_watch({'guild': name}), 'connection': current['connection'], 'destination': current['destination'],
                                                   'source': 'group', 'createdAt': int(now.timestamp())}, 'active', limit=3)
            except Invalid:
                raise Invalid('O dono do bot já usa todos os alertas permitidos. Apague um no app para criar este.') from None
            self.refresh_bomdia(owner, current, now)
            return f'🚨 Alerta criado para a guild *{clean(name)}*: mortes e todo level up. Ajuste com !alerta ajuda'
        if not watch:
            raise Invalid('Este grupo ainda não tem alerta. Crie com: !alerta guild <nome>')
        if sub == 'level':
            n = number(rest[0] if rest else '', 1, 1000, 'Level')
            return self.change_watch(owner, watch, {'milestone': n}, now, '🔺 Aviso de level up *todo level*.' if n == 1 else f'🔺 Aviso de level up a cada *{n}* levels.')
        if sub in ('mortes', 'ups'):
            on = toggle(rest[0] if rest else '')
            field = 'deaths' if sub == 'mortes' else 'ups'
            return self.change_watch(owner, watch, {field: on}, now, ('💀 Avisos de morte ' if field == 'deaths' else '🔺 Avisos de level up ') + ('*ligados*.' if on else '*desligados*.'))
        if sub == 'limite':
            what = norm(rest[0]) if rest else ''
            if what in ('hora', 'h'):
                n = 0 if len(rest) > 1 and norm(rest[1]) in ('sem', 'off') else number(rest[1] if len(rest) > 1 else '', 0, 1000, 'Limite por hora')
                return self.change_watch(owner, watch, {'hourlyCap': n}, now, '⏱️ Sem limite de avisos por hora.' if n == 0 else f'⏱️ No máximo *{n}* avisos por hora.')
            if what in ('minuto', 'min', 'm'):
                n = number(rest[1] if len(rest) > 1 else '', 1, 120, 'Limite por minuto')
                return self.change_watch(owner, watch, {'perMinute': n}, now, f'⏱️ No máximo *{n}* avisos por minuto.')
            raise Invalid('Use: !alerta limite hora <n> ou !alerta limite minuto <n>')
        if sub in ('on', 'off'):
            on = sub == 'on'
            return self.change_watch(owner, watch, {}, now, '🚨 Alerta *ligado*.' if on else '⏸️ Alerta *pausado*.', 'active' if on else 'inactive')
        if sub in ('remover', 'apagar', 'excluir'):
            self.store.update(owner, watch['id'], 'watch', watch['data'], 'revoked')
            self.refresh_bomdia(owner, current, now)
            return '🗑️ Alerta removido.'
        raise Invalid('Não entendi. Veja: !alerta ajuda')
