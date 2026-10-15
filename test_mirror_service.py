import tempfile
import unittest
from pathlib import Path
from mirror_core import MirrorStore
from mirror_service import MirrorService

class FakeEngine:
    def __init__(self, on_change=None, on_move=None):
        self.on_change=on_change;self.on_move=on_move;self.callback=None;self.profile=None;self.state={'hwnd':1}
    def configure(self, char, profile):self.profile=profile;self.character=char
    def status(self):return self.state.copy()
    def select(self, mode, callback, existing=None):self.callback=callback;return {'ok':True,'pendente':True}
    def bind_window(self, hwnd):return {'ok':True}
    def cancel_selection(self):return {"ok":True,"cancelado":True}
    def close(self):self.profile=None

class MirrorServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.service=MirrorService('A',store=MirrorStore(Path(self.temp.name)/'mirrors.json'),engine_factory=FakeEngine,clients=lambda:[{'hwnd':1,'titulo':'Tibia test'}])
        self.addCleanup(self.service.close)
        self.service.perfil('novo',name='Hunt')
    def test_selection_from_old_character_never_saves_into_new_one(self):
        self.service.selecionar('quadrado');callback=self.service.engine.callback
        self.service.definir_personagem('B');self.service.perfil('novo',name='Other')
        callback({'modo':'quadrado','origem':{'x':4,'y':5,'w':32,'h':32},'contexto':{'w':800,'h':600,'dpi':96}})
        self.assertEqual(self.service.carregar()['perfil']['recortes'],[])
        self.assertEqual(self.service.store.estado('A')['perfil']['recortes'],[])
    def test_selection_from_old_profile_is_rejected(self):
        self.service.selecionar('quadrado');callback=self.service.engine.callback
        self.service.perfil('novo',name='Boss')
        callback({'origem':{'x':4,'y':5,'w':32,'h':32}})
        self.assertEqual(self.service.carregar()['perfil']['recortes'],[])
    def test_cancel_does_not_create_crop_and_completion_preserves_appearance(self):
        self.service.selecionar('quadrado');self.service.engine.callback(None)
        self.assertEqual(self.service.carregar()['perfil']['recortes'],[])
        self.service.selecionar('quadrado');self.service.engine.callback({'origem':{'x':4,'y':5,'w':32,'h':32}})
        crop=self.service.carregar()['perfil']['recortes'][0]
        self.service.recorte('salvar',crop['id'],{'glow':{'cor':'#112233','intensidade':'max'},'escala':3})
        self.service.selecionar('quadrado',crop['id']);self.service.engine.callback({'origem':{'x':44,'y':55,'w':32,'h':32}})
        edited=self.service.carregar()['perfil']['recortes'][0]
        self.assertEqual(edited['glow'],{'cor':'#112233','intensidade':'max'})
        self.assertEqual(edited['escala'],3)
        self.assertEqual(edited['origem']['x'],44)
    def test_callback_after_close_does_not_write(self):
        self.service.selecionar('quadrado');callback=self.service.engine.callback
        self.service.close();callback({'origem':{'w':32,'h':32}})
        self.assertEqual(self.service.store.estado('A')['perfil']['recortes'],[])
    def test_consecutive_confirmations_save_and_emit_each_new_crop(self):
        events=[];self.service.emit=events.append
        for index in range(2):
            self.service.selecionar('manual')
            self.service.engine.callback({'modo':'manual','origem':{'x':20+index*40,'y':30,'w':32,'h':32}})
            crops=self.service.carregar()['perfil']['recortes']
            self.assertEqual(len(crops),index+1)
            self.assertEqual(len(events[-1]['perfil']['recortes']),index+1)
            self.assertFalse(crops[-1]['mostrar_nome'])
        self.assertNotEqual(crops[0]['id'],crops[1]['id'])
    def test_no_live_bound_client_rejects_selection(self):
        self.service.clients=lambda:[]
        with self.assertRaises(ValueError):self.service.selecionar('quadrado')
        self.assertIsNone(self.service.engine.callback)
    def test_cancel_invalidates_completion_that_is_already_queued(self):
        self.service.selecionar('quadrado');callback=self.service.engine.callback
        self.assertTrue(self.service.cancelar()['cancelado'])
        callback({'origem':{'w':32,'h':32}})
        self.assertEqual(self.service.carregar()['perfil']['recortes'],[])
    def test_stale_drag_does_not_modify_another_profile(self):
        self.service.recorte('salvar',data={});cid=self.service.carregar()['perfil']['recortes'][0]['id']
        self.service.perfil('novo',name='Boss');self.service._moved(cid,{'x':500,'y':500})
        self.assertEqual(self.service.carregar()['perfil']['recortes'],[])

if __name__=='__main__':unittest.main()
