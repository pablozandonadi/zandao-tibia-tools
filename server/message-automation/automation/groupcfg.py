"""Configuração pelo próprio grupo: administradores do grupo usam !set e !alerta.

O que se cria aqui é o mesmo registro que o app cria (aparece na lista do app, com a marca "criado pelo grupo") e conta nos mesmos limites do dono.
Só chega aqui quem a ponte confirmou como administrador do grupo; o texto recebido nunca é gravado.
"""
import re
from urllib.parse import quote
from .botcmds import KEYS, WORLD, clean, norm
from .domain import Invalid
from .watch import GUILD, tibia_json, validate_watch

COOLDOWN_MIN, COOLDOWN_MAX = 3, 86400
COMMAND = re.compile(r'!\s*(set|alerta)\b\s*(.*)', re.I | re.S)
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
    def __init__(self, store, guild_exists=None):
        self.store = store
        self.guild_exists = guild_exists or default_guild_exists

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
            return self.set(owner, key, current, parsed[1], now) if parsed[0] == 'set' else self.alert(owner, current, parsed[1], now)
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
            return self.summary(owner, current)
        if sub in ('ajuda', 'help'):
            return SET_HELP
        if sub in ('world', 'mundo'):
            if not rest:
                return f'🌍 Mundo do grupo: *{clean(current["world"])}*'
            name = ' '.join(rest)
            if not WORLD.fullmatch(name):
                raise Invalid('Informe só o nome do mundo. Ex.: !set world Jadebra')
            return self.save(owner, key, current, {'world': name.capitalize()}, now, f'🌍 Mundo do grupo agora: *{name.capitalize()}*')
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

    def summary(self, owner, current):
        lines = ['⚙️ *Configuração do grupo*', f'🌍 Mundo: *{clean(current["world"])}*', f'⏳ Espera por pessoa: *{duration_text(current["cooldown"])}*',
                 '🤖 Comandos: *' + ('pausados' if current.get('paused') else 'ligados') + '*']
        if current.get('disabled'):
            lines.append('🚫 Desligados aqui: ' + ', '.join(current['disabled']))
        lines.append(self.alert_status(self.find_watch(owner, current)))
        lines.append('_Veja: !set ajuda · !alerta ajuda_')
        return '\n'.join(lines)

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
                return self.change_watch(owner, watch, {'guild': name}, now, f'🏰 Alerta agora acompanha a guild *{clean(name)}*.')
            try:
                self.store.create(owner, 'watch', {**validate_watch({'guild': name}), 'connection': current['connection'], 'destination': current['destination'],
                                                   'source': 'group', 'createdAt': int(now.timestamp())}, 'active', limit=3)
            except Invalid:
                raise Invalid('O dono do bot já usa todos os alertas permitidos. Apague um no app para criar este.') from None
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
            return '🗑️ Alerta removido.'
        raise Invalid('Não entendi. Veja: !alerta ajuda')
