"""Leitura manual do World Board, salva apenas no perfil local do personagem."""
import copy
import json
import os
import re
import sys
import threading
import time
import unicodedata
from datetime import date, datetime, timedelta, timezone

import tibia_info

BASE = os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__))
ARQUIVO = os.path.join(BASE, 'world_board_registros.json')
FONTE = 'https://www.tibiawiki.com.br/wiki/Mini_World_Changes'
_LOCK = threading.Lock()
# Assinaturas curtas das mensagens; sem executar texto colado ou guardar chat bruto.
RULES = (
    ('poacher_caves', 'Poacher Caves', 'Orc Land / Poacher Caves', r'^(?:the wild animals|poachers).*green claw swamp', 'Norte de Green Claw Swamp'),
    ('jungle_camp', 'Jungle Camp', 'Acampamento de hunters e dworcs', r'strange sounds.*trapwood.*hunters and dworcs', 'Trapwood, Tiquanda'),
    ('nightmare_isles', 'Nightmare Isles', 'Nightmare Isles', r'sandstorm.*darama.*nightmare', 'Darama'),
    ('grimvale', 'Grimvale', 'Lua cheia em Grimvale', r'full moon.*island of grimvale.*howls', 'Grimvale'),
    ('nomads', 'Nomads', 'Acampamento de Nomads', r'nomads travel.*ankrahmun.*camp', 'Deserto de Ankrahmun'),
    ('river_runs_deep', 'River Runs Deep', 'River Runs Deep', r'river in zao steppe runs deep', 'Zao Steppe'),
    ('fire_from_earth', 'Fire from the Earth', 'Erupção de Goroma', r'volcano on goroma.*fiery message', 'Goroma'),
    ('down_drain', 'Down the Drain', 'Inundação do Outlaw Camp', r'river south of the outlaw camp is flooding', 'Sul do Outlaw Camp'),
    ('spirit_grounds', 'Spirit Grounds', 'Spirit Gate', r'adventurers.*spirit gate.*restless undead', 'Local indicado na mensagem'),
    ('oriental_trader', 'Oriental Trader', 'Yasir / Oriental Trader', r'^oriental ships sighted!.*trader.*creature products', 'Carlin, Ankrahmun ou Liberty Bay'),
    ('fury_gates', 'Fury Gates', 'Fury Gate', r'^a fiery fury gate has opened', 'Cidade não informada'),
    ('chakoya', 'Chakoya Iceberg', 'Chakoya Iceberg', r'^a big iceberg.*port hope.*furballs', 'Norte de Port Hope'),
    ('hive', 'Hive Outpost', 'Hive Outpost', r'^a hive infestation.*liberty bay', 'Sudoeste de Liberty Bay'),
    ('stampede', 'Stampede', 'Stampede', r'^stampede!.*ape god.*elephants', 'Tiquanda'),
    ('bank', 'Bank Robbery', 'Roubo de banco', r'^several banks.*being robbed.*thieves', 'Banco não informado'),
    ('thawing', 'Thawing', 'Thawing', r'^judging by.*mammoths.*svargrond.*snow', 'Svargrond'),
    ('noodles', 'Noodles is Gone', 'Noodles desapareceu', r'^not again! noodles.*left the castle', 'Thais'),
    ('lumberjack', 'Lumberjack', 'Lumberjack', r'^looks like.*royal trees.*cut down.*lumberjacks', 'Ao norte de Carlin'),
    ('kingsday', 'Kingsday', 'Kingsday', r'^hail to the king!.*kingsday in thais', 'Thais'),
    ('bored', 'Bored', 'Bruxa Wyda entediada', r'^sharpen your sword!.*witch wyda.*bored', 'Green Claw Swamp'),
    ('warpath', 'Warpath', 'Bibby Bloodbath / Warpath', r'^bibby bloodbath and her crew.*roaming', 'Local não informado'),
    ('spider', 'Spider Nest', 'Spider Nest', r'^a whole nest of spiders.*mamma longlegs', 'Oeste de Venore'),
    ('devovorga', "Devovorga's Essence", 'Devovorga’s Essence', r'^in case.*tentacle pieces.*devovorga.*boss lair', 'Vengoth'),
    ('chyllfroest', 'Chyllfroest', 'Chyllfroest', r'^an ice bridge.*svargrond.*frosty island', 'Próximo de Svargrond'),
)


def _normal(text):
    return ' '.join(unicodedata.normalize('NFKC', text).replace('’', "'").lower().split())


def analisar(texto, completo=False):
    if not isinstance(texto, str) or not texto.strip():
        return {'erro': 'Cole as mensagens do Server Log obtidas ao usar o World Board.'}
    if len(texto) > 32000:
        return {'erro': 'Cole apenas o trecho do World Board (máximo de 32 mil caracteres).'}
    found, unknown = {}, []
    for raw in texto.splitlines():
        line = re.sub(r'^\s*\d{1,2}:\d{2}(?::\d{2})?\s+', '', raw).strip().rstrip('\\').strip()
        normalized = _normal(line)
        if not normalized or normalized.startswith(('you see the world board', 'this board will notify', 'you read: maintained by charos', 'maintained by charos')):
            continue
        match = next((r for r in RULES if re.search(r[3], normalized)), None)
        if not match:
            unknown.append(line)
            continue
        ident, name, label, _, location = match
        detail = ''
        if ident == 'poacher_caves':
            detail = 'Animais dominam' if 'clearly dominate' in normalized else 'Espíritos / Ghost Wolves' if 'vengeful spirits' in normalized else 'Poachers dominam'
        if ident == 'jungle_camp':
            detail = 'O texto não distingue qual lado domina o acampamento.'
        if ident == 'nightmare_isles':
            location = 'Ankrahmun · tar pits' if re.search(r'ankh?rah?mun tar pits', normalized) else 'Rio próximo de Drefia' if 'drefia' in normalized else 'Costa norte de Darama' if 'northernmost coast' in normalized else 'Darama'
        if ident == 'spirit_grounds':
            location = 'Ghostlands' if 'ghostlands' in normalized else 'Vengoth' if 'vengoth' in normalized else 'Montanhas de Darama' if 'daramian mountains' in normalized else location
        event = {'id': ident, 'nome': name, 'rotulo': label, 'local': location, 'detalhe': detail}
        if ident in found and found[ident] != event:
            unknown.append('Mensagens conflitantes para ' + label)
        else:
            found[ident] = event
    if not found:
        return {'erro': 'Nenhuma mensagem de mudança ativa foi reconhecida. Dar Look na placa não basta: use a placa e copie o Server Log.'}
    full = bool(completo) and not unknown
    yasir = 'presente' if 'oriental_trader' in found else 'ausente' if full else 'nao_confirmado'
    return {'eventos': list(found.values()), 'yasir': yasir, 'completo': full,
            'confirmou_completo': bool(completo), 'nao_reconhecidas': unknown, 'nao_reconhecidas_total': len(unknown),
            'aviso': 'Trecho completo confirmado pelo usuário.' if full else 'Registro parcial: ausência de uma mensagem não confirma ausência da mudança.', 'fonte': FONTE}


def _expiry(day):
    following = date.fromisoformat(day) + timedelta(days=1)
    noon = datetime(following.year, following.month, following.day, 12, tzinfo=timezone.utc)
    save = datetime(following.year, following.month, following.day, 10, tzinfo=timezone.utc) - tibia_info._offset_berlim(noon)
    return int(save.timestamp() * 1000)


def preparar(texto, personagem, mundo, dia='', completo=False):
    if not personagem:
        return {'erro': 'Cadastre e selecione o personagem em uso nas configurações para salvar no perfil dele.'}
    if not isinstance(mundo, str) or not re.fullmatch(r'[A-Za-z]{2,40}', mundo.strip()):
        return {'erro': 'Escolha o mundo em que o World Board foi consultado.'}
    dia = dia or tibia_info.dia_tibia().isoformat()
    try:
        chosen = date.fromisoformat(dia)
        if chosen > tibia_info.dia_tibia():
            raise ValueError()
    except (ValueError, TypeError):
        return {'erro': 'Informe um dia do Tibia válido, sem data futura.'}
    parsed = analisar(texto, completo)
    if parsed.get('erro'):
        return parsed
    return {**parsed, 'personagem': personagem, 'mundo': mundo.strip().capitalize(), 'dia': dia,
            'consulta': time.time(), 'expira_ms': _expiry(dia), 'origem': 'world_board_manual'}



def contexto(dados, mundo=''):
    personagem = dados.get('atual') or ''
    active = next((p for p in dados.get('lista', []) if p.get('nome') == personagem), {})
    return personagem, (mundo or '').strip() or active.get('mundo') or ''

def _load(path):
    try:
        with open(path, encoding='utf-8') as file:
            records = json.load(file).get('registros', [])
            return [r for r in records if isinstance(r, dict) and isinstance(r.get('eventos'), list) and all(isinstance(e, dict) and e.get('id') in {rule[0] for rule in RULES} and isinstance(e.get('nome'), str) for e in r['eventos']) and isinstance(r.get('personagem'), str) and isinstance(r.get('mundo'), str) and isinstance(r.get('dia'), str) and isinstance(r.get('consulta'), (int, float)) and isinstance(r.get('expira_ms'), (int, float)) and isinstance(r.get('completo'), bool) and r.get('yasir') in ('presente', 'ausente', 'nao_confirmado')]
    except (OSError, ValueError, AttributeError, TypeError):
        return []


def salvar(texto, personagem, mundo, dia='', completo=False, caminho=None):
    record = preparar(texto, personagem, mundo, dia, completo)
    if record.get('erro'):
        return record
    record.pop('nao_reconhecidas', None)  # Nunca persiste chat bruto ou linhas desconhecidas.
    path = caminho or ARQUIVO
    key = (personagem.casefold(), record['mundo'].casefold(), record['dia'])
    try:
        with _LOCK:
            records = [r for r in _load(path) if (str(r.get('personagem', '')).casefold(), str(r.get('mundo', '')).casefold(), r.get('dia')) != key]
            records.append(record)
            records = sorted(records, key=lambda r: r.get('consulta', 0))[-1000:]
            with open(path + '.tmp', 'w', encoding='utf-8') as file:
                json.dump({'registros': records}, file, ensure_ascii=False, indent=1)
            os.replace(path + '.tmp', path)
    except OSError:
        return {'erro': 'Não foi possível salvar o registro no perfil. Confira acesso à pasta dos dados.'}
    return {'ok': True, 'registro': record}


def ultimo(personagem, mundo, caminho=None):
    if not personagem or not mundo:
        return None
    with _LOCK:
        records = [r for r in _load(caminho or ARQUIVO) if str(r.get('personagem', '')).casefold() == personagem.casefold() and str(r.get('mundo', '')).casefold() == mundo.casefold()]
    if not records:
        return None
    record = copy.deepcopy(max(records, key=lambda r: (r.get('dia', ''), r.get('consulta', 0))))
    record['valido'] = record.get('dia') == tibia_info.dia_tibia().isoformat() and record.get('expira_ms', 0) > time.time() * 1000
    return record


def remover(personagem, mundo, dia, caminho=None):
    path = caminho or ARQUIVO
    with _LOCK:
        records = [r for r in _load(path) if (str(r.get('personagem', '')).casefold(), str(r.get('mundo', '')).casefold(), r.get('dia')) != (personagem.casefold(), mundo.casefold(), dia)]
        with open(path + '.tmp', 'w', encoding='utf-8') as file:
            json.dump({'registros': records}, file, ensure_ascii=False, indent=1)
        os.replace(path + '.tmp', path)
    return {'ok': True}


def aplicar(resumo, personagem, caminho=None):
    if not isinstance(resumo, dict) or resumo.get('erro'):
        return resumo
    resumo['personagem'] = personagem
    record = ultimo(personagem, resumo.get('mundo', ''), caminho)
    resumo['world_board'] = record
    if not record or not record.get('valido'):
        return resumo
    yasir = dict(resumo.get('yasir') or {})
    yasir.update({'mudancas': [e['nome'] for e in record['eventos']], 'mudancas_velhas': False, 'mudancas_parciais': not record['completo']})
    if record['yasir'] in ('presente', 'ausente'):
        online = yasir.get('presente')
        present = record['yasir'] == 'presente'
        yasir.update({'estado': record['yasir'], 'presente': present, 'origem': 'world_board_manual', 'conferido': False,
                      'consulta': record['consulta'], 'dia': record['dia'], 'cidade': None, 'velho': False,
                      'motivo': 'Informado manualmente pelo World Board no perfil de ' + personagem + '.',
                      'divergencia_online': online is not None and online != present})
    resumo['yasir'] = yasir
    return resumo
