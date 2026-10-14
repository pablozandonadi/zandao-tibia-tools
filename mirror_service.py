"""Bridge between private profile storage and the asynchronous native Mirror engine."""
import copy
import threading
from mirror_core import MirrorStore


class MirrorService:
    def __init__(self, character='', emit=None, store=None, engine_factory=None, clients=None):
        self.store = store or MirrorStore()
        self.character = character or ''
        self.emit = emit or (lambda state: None)
        self.lock = threading.RLock()
        self.engine = None
        self.engine_factory = engine_factory
        self.clients = clients
        self.generation = 0
        self.closed = False

    def _native(self):
        if self.closed:
            raise ValueError('Mirror foi encerrado.')
        if self.engine is None:
            from mirror_native import MirrorEngine, list_clients
            self.engine = (self.engine_factory or MirrorEngine)(on_change=self._changed, on_move=self._moved)
            self.clients = self.clients or list_clients
            data = self.store.estado(self.character)
            self.engine.configure(self.character, data['perfil'])
            choices = self.clients()
            if len(choices) == 1:
                self.engine.bind_window(choices[0]['hwnd'])
        return self.engine

    def _state(self):
        d = self.store.estado(self.character)
        d['estado'] = self.engine.status() if self.engine else {'estado': 'sem_cliente', 'selecionando': False}
        d['clientes'] = self.clients() if self.clients else []
        return d

    def _changed(self, _state=None):
        with self.lock:
            if self.closed:
                return
            data = self._state()
        self.emit(data)

    def _refresh(self):
        self.generation += 1
        if self.engine:
            self.engine.configure(self.character, self.store.estado(self.character)['perfil'])
        return self._state()

    def carregar(self):
        with self.lock:
            self._native()
            return self._state()

    def definir_personagem(self, character):
        with self.lock:
            if self.closed or self.character == (character or ''):
                return
            self.character = character or ''
            data = self._refresh()
        self.emit(data)

    def perfil(self, action, pid='', name=''):
        with self.lock:
            self._native()
            self.store.perfil(self.character, action, pid, name)
            data = self._refresh()
        self.emit(data)
        return data

    def recorte(self, action, cid='', data=None):
        with self.lock:
            self._native()
            self.store.recorte(self.character, action, cid, data)
            result = self._refresh()
        self.emit(result)
        return result

    def todos(self, action):
        with self.lock:
            self._native()
            self.store.todos(self.character, action)
            data = self._refresh()
        self.emit(data)
        return data

    def vincular(self, hwnd):
        with self.lock:
            response = self._native().bind_window(int(hwnd))
            if response.get('erro'):
                return response
            self.generation += 1
            return self._state()

    def selecionar(self, mode, cid=''):
        with self.lock:
            engine = self._native()
            state = self.store.estado(self.character)
            if not self.character or state['perfil'] is None:
                raise ValueError('Escolha um personagem e crie um perfil Mirror.')
            existing = next((r for r in state['perfil']['recortes'] if r['id'] == cid), None)
            if cid and existing is None:
                raise ValueError('Recorte não encontrado neste perfil.')
            bound = engine.status().get('hwnd', 0)
            if self.clients and not any(c['hwnd'] == bound for c in self.clients()):
                raise ValueError('Abra e vincule o cliente Tibia antes de selecionar um recorte.')
            if engine.status().get('selecionando'):
                raise ValueError('Conclua ou cancele a seleção atual.')
            self.generation += 1
            generation, character, pid = self.generation, self.character, state['ativo']
            def complete(result):
                with self.lock:
                    current = self.store.estado(self.character)
                    if self.closed or generation != self.generation or character != self.character or pid != current['ativo']:
                        return
                    if result is not None:
                        data = {**copy.deepcopy(existing or {}), **result}
                        if not existing:
                            count = len(current['perfil']['recortes'])
                            data.update(nome=f'Mirror {count + 1}', destino={'x': 60 + 48 * (count % 8), 'y': 80})
                        try:
                            self.store.recorte(character, 'salvar', cid, data)
                        except (ValueError, OSError) as error:
                            self.emit({**self._state(), 'erro': str(error)})
                            return
                        data = self._refresh()
                    else:
                        data = self._state()
                self.emit(data)
            return engine.select(mode, complete, existing)

    def cancelar(self):
        with self.lock:
            self.generation += 1
            if self.engine:
                result = self.engine.cancel_selection()
                return {**result, "cancelado": bool(result.get("ok"))}
            return {"ok": True, "cancelado": True}

    def _moved(self, cid, destination):
        with self.lock:
            if self.closed:
                return
            current = self.store.estado(self.character)
            if not current['perfil'] or not any(r['id'] == cid for r in current['perfil']['recortes']):
                return
            try:
                self.store.recorte(self.character, 'salvar', cid, {'destino': destination})
                data = self._state()
            except (ValueError, OSError) as error:
                data = {**self._state(), 'erro': str(error)}
        self.emit(data)

    def reload(self):
        with self.lock:
            self.store = MirrorStore(self.store.path)
            data = self._refresh()
        self.emit(data)

    def close(self):
        with self.lock:
            self.closed = True
            self.generation += 1
            engine = self.engine
        if engine:
            engine.close()
