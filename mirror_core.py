"""Private Mirror profiles. No Windows dependency or persisted window handles."""
import copy
import json
import math
import os
import re
import threading
import uuid
from pathlib import Path
from app_paths import data_dir

ARQUIVO = os.path.join(data_dir(), 'mirrors.json')


def numero(value, default, minimum, maximum):
    try:
        n = float(default if value is None else value)
    except (TypeError, ValueError):
        raise ValueError('Valor numérico inválido.') from None
    if not math.isfinite(n) or not minimum <= n <= maximum:
        raise ValueError('Valor fora do intervalo permitido.')
    return n


def limpar_nome(value, default=''):
    return str(value or default).strip()[:80]


def normalizar_recorte(data, base=None):
    if not isinstance(data, dict):
        raise ValueError('Recorte inválido.')
    original = copy.deepcopy(base or {})
    d = {**original, **data}
    out = {'id': original.get('id') or uuid.uuid4().hex,
           'nome': limpar_nome(d.get('nome'), 'Mirror'),
           'modo': d.get('modo', 'quadrado')}
    if out['modo'] not in ('quadrado', 'manual'):
        raise ValueError('Modo de recorte inválido.')
    rect = {**original.get('origem', {}), **(data.get('origem') or {})}
    out['origem'] = {k: int(numero(rect.get(k), default, low, high)) for k, default, low, high in
                     [('x', 0, 0, 32768), ('y', 0, 0, 32768), ('w', 32, 1, 8192), ('h', 32, 1, 8192)]}
    if out['modo'] == 'quadrado' and out['origem']['w'] != out['origem']['h']:
        raise ValueError('O recorte padrão deve ser quadrado.')
    dest = {**original.get('destino', {}), **(data.get('destino') or {})}
    out['destino'] = {k: int(numero(dest.get(k), 60, -32768, 32768)) for k in ('x', 'y')}
    out['escala'] = numero(d.get('escala'), 1, .25, 8)
    out['opacidade'] = numero(d.get('opacidade'), 1, .1, 1)
    output_w, output_h = out['origem']['w'] * out['escala'], out['origem']['h'] * out['escala']
    if max(output_w, output_h) > 4096 or output_w * output_h > 8_000_000:
        raise ValueError('Este recorte ficou grande demais. Reduza a área ou a escala de exibição.')
    for key, default in [('visivel', True), ('travado', True), ('mostrar_nome', False)]:
        value = d.get(key, default)
        if not isinstance(value, bool):
            raise ValueError('Opção de recorte inválida.')
        out[key] = value
    if re.fullmatch(r'Mirror\s*\d+', out['nome'], re.IGNORECASE):
        out['mostrar_nome'] = False
    glow = {**original.get('glow', {}), **(data.get('glow') or {})}
    color = str(glow.get('cor', '#00cc66'))
    level = glow.get('intensidade', 'med')
    if not re.fullmatch(r'#[0-9a-fA-F]{6}', color) or level not in ('off', 'min', 'med', 'max'):
        raise ValueError('Cor ou intensidade do glow inválida.')
    out['glow'] = {'cor': color.lower(), 'intensidade': level}
    ctx = {**original.get('contexto', {}), **(data.get('contexto') or {})}
    out['contexto'] = {k: int(numero(ctx.get(k), default, low, high)) for k, default, low, high in
                       [('w', 0, 0, 32768), ('h', 0, 0, 32768), ('dpi', 96, 48, 768)]}
    return out


class MirrorStore:
    def __init__(self, path=None):
        self.path = Path(path or ARQUIVO)
        self.lock = threading.RLock()
        self.cfg = self._load()
        self._persisted = copy.deepcopy(self.cfg)

    def _load(self):
        for path in (self.path, self.path.with_suffix(self.path.suffix + '.bak')):
            if not path.exists():
                continue
            try:
                d = json.loads(path.read_text(encoding='utf-8-sig'))
                if not isinstance(d, dict) or d.get('schema') != 1 or not isinstance(d.get('personagens'), dict):
                    raise ValueError('Formato de Mirror inválido.')
                clean = {'schema': 1, 'personagens': {}}
                for key, char in d['personagens'].items():
                    if not isinstance(char, dict) or not isinstance(char.get('perfis'), list):
                        raise ValueError('Perfis inválidos.')
                    profiles = []
                    ids = set()
                    for pf in char['perfis']:
                        if not isinstance(pf, dict) or not isinstance(pf.get('recortes'), list):
                            raise ValueError('Perfil inválido.')
                        pid = str(pf.get('id', ''))
                        if not re.fullmatch(r'[0-9a-f]{32}', pid) or pid in ids:
                            raise ValueError('Identificador de perfil inválido.')
                        ids.add(pid)
                        crops = []
                        cropids = set()
                        for crop in pf['recortes']:
                            cid = str(crop.get('id', ''))
                            if not re.fullmatch(r'[0-9a-f]{32}', cid) or cid in cropids:
                                raise ValueError('Identificador de recorte inválido.')
                            cropids.add(cid)
                            crops.append(normalizar_recorte(crop, crop))
                        profiles.append({'id': pid, 'nome': limpar_nome(pf.get('nome'), 'Perfil'), 'recortes': crops})
                    active = char.get('ativo', '')
                    if active and active not in ids:
                        raise ValueError('Perfil ativo inválido.')
                    label = limpar_nome(char.get('nome'), key)
                    if not label or label.casefold() in clean['personagens']:
                        raise ValueError('Personagem inválido.')
                    clean['personagens'][label.casefold()] = {'nome': label, 'ativo': active, 'perfis': profiles}
                return clean
            except (OSError, ValueError, TypeError, KeyError, AttributeError):
                continue
        if self.path.exists() or self.path.with_suffix(self.path.suffix + '.bak').exists():
            raise ValueError('Não consegui ler os perfis Mirror nem o backup. Os arquivos foram preservados.')
        return {'schema': 1, 'personagens': {}}

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(self.cfg, ensure_ascii=False, indent=2, allow_nan=False)
        temp = self.path.with_suffix(self.path.suffix + '.tmp')
        try:
            if self.path.exists():
                backup_temp = self.path.with_suffix(self.path.suffix + '.bak.tmp')
                backup_temp.write_text(json.dumps(self._persisted, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
                os.replace(backup_temp, self.path.with_suffix(self.path.suffix + '.bak'))
            with temp.open('w', encoding='utf-8') as f:
                f.write(text); f.flush(); os.fsync(f.fileno())
            os.replace(temp, self.path)
            self._persisted = copy.deepcopy(self.cfg)
        finally:
            if temp.exists():
                temp.unlink()

    def _character(self, character, create=False):
        label = limpar_nome(character)
        if not label:
            raise ValueError('Escolha um personagem em uso para configurar Mirror.')
        char = self.cfg['personagens'].get(label.casefold())
        if char is None and create:
            char = {'nome': label, 'ativo': '', 'perfis': []}
            self.cfg['personagens'][label.casefold()] = char
        if char is None:
            raise ValueError('Crie um perfil Mirror para este personagem.')
        return char

    def estado(self, character):
        with self.lock:
            char = self.cfg['personagens'].get(limpar_nome(character).casefold(), {'ativo': '', 'perfis': []})
            profiles = copy.deepcopy(char['perfis'])
            return {'personagem': limpar_nome(character), 'perfis': profiles, 'ativo': char['ativo'],
                    'perfil': next((p for p in profiles if p['id'] == char['ativo']), None)}

    def _profile(self, character):
        char = self._character(character)
        pf = next((p for p in char['perfis'] if p['id'] == char['ativo']), None)
        if pf is None:
            raise ValueError('Escolha um perfil Mirror.')
        return pf

    def _transaction(self, action):
        with self.lock:
            before = copy.deepcopy(self.cfg)
            try:
                result = action()
                self._save()
                return copy.deepcopy(result)
            except Exception:
                self.cfg = before
                raise

    def perfil(self, character, action, pid='', nome=''):
        def update():
            if action not in ('novo', 'duplicar', 'renomear', 'remover', 'usar'):
                raise ValueError('Ação de perfil inválida.')
            char = self._character(character, create=action == 'novo')
            pf = next((p for p in char['perfis'] if p['id'] == pid), None)
            if action != 'novo' and pf is None:
                raise ValueError('Perfil não encontrado para este personagem.')
            if action in ('novo', 'duplicar'):
                label = limpar_nome(nome, (pf['nome'] + ' (cópia)') if pf else 'Novo perfil')
                if any(p['nome'].casefold() == label.casefold() for p in char['perfis']):
                    raise ValueError('Já existe um perfil com esse nome.')
                new = {'id': uuid.uuid4().hex, 'nome': label, 'recortes': copy.deepcopy(pf['recortes']) if pf else []}
                for crop in new['recortes']:
                    crop['id'] = uuid.uuid4().hex
                char['perfis'].append(new); char['ativo'] = new['id']
                return new
            if action == 'renomear':
                label = limpar_nome(nome)
                if not label or any(p['id'] != pid and p['nome'].casefold() == label.casefold() for p in char['perfis']):
                    raise ValueError('Informe um nome de perfil único.')
                pf['nome'] = label
            elif action == 'usar':
                char['ativo'] = pid
            elif action == 'remover':
                char['perfis'].remove(pf)
                if char['ativo'] == pid:
                    char['ativo'] = char['perfis'][0]['id'] if char['perfis'] else ''
            return pf
        return self._transaction(update)

    def recorte(self, character, action, cid='', dados=None):
        def update():
            pf = self._profile(character)
            crop = next((c for c in pf['recortes'] if c['id'] == cid), None)
            if cid and crop is None:
                raise ValueError('Recorte não encontrado neste perfil.')
            if action == 'remover':
                if crop is None:
                    raise ValueError('Recorte não encontrado.')
                pf['recortes'].remove(crop)
                return crop
            if action != 'salvar':
                raise ValueError('Ação de recorte inválida.')
            new = normalizar_recorte(dados or {}, crop)
            if crop is None:
                pf['recortes'].append(new)
            else:
                pf['recortes'][pf['recortes'].index(crop)] = new
            return new
        return self._transaction(update)

    def todos(self, character, action):
        choices = {'ocultar': ('visivel', False), 'mostrar': ('visivel', True),
                   'travar': ('travado', True), 'destravar': ('travado', False)}
        if action not in choices:
            raise ValueError('Ação de Mirror inválida.')
        def update():
            pf = self._profile(character)
            key, value = choices[action]
            for crop in pf['recortes']:
                crop[key] = value
            return pf
        return self._transaction(update)
