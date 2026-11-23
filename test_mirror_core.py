import json
import tempfile
import unittest
from pathlib import Path
from mirror_core import MirrorStore, normalizar_recorte

class MirrorCoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'mirrors.json';self.store=MirrorStore(self.path)
    def test_characters_and_profiles_are_isolated_and_restored(self):
        hunt=self.store.perfil('Knight','novo',nome='Hunt')
        self.store.recorte('Knight','salvar',dados={'nome':'Ring','origem':{'x':4,'y':5,'w':32,'h':32}})
        boss=self.store.perfil('Knight','duplicar',hunt['id'], 'Boss')
        self.assertNotEqual(hunt['recortes'][0]['id'] if hunt['recortes'] else '',boss['recortes'][0]['id'])
        self.store.recorte('Knight','salvar',boss['recortes'][0]['id'],{'glow':{'cor':'#00ff00','intensidade':'max'}})
        self.store.perfil('Druid','novo',nome='Geral')
        self.assertEqual(len(self.store.estado('Druid')['perfil']['recortes']),0)
        self.store.perfil('Knight','usar',hunt['id'])
        self.assertEqual(self.store.estado('Knight')['perfil']['recortes'][0]['glow']['intensidade'],'med')
        restored=MirrorStore(self.path)
        self.assertEqual(restored.estado('KNIGHT')['ativo'],hunt['id'])
        self.assertEqual(len(restored.estado('Knight')['perfis']),2)
    def test_no_character_and_unknown_ids_do_not_write(self):
        with self.assertRaises(ValueError):self.store.perfil('','novo',nome='Hunt')
        self.store.perfil('A','novo',nome='Hunt')
        before=self.path.read_bytes()
        with self.assertRaises(ValueError):self.store.recorte('A','salvar','other',{'nome':'No'})
        self.assertEqual(self.path.read_bytes(),before)
    def test_corrupt_primary_recovers_backup_without_overwriting_it(self):
        self.store.perfil('A','novo',nome='One')
        self.store.perfil('A','novo',nome='Two')
        self.path.write_text('{broken',encoding='utf-8')
        recovered=MirrorStore(self.path)
        self.assertEqual(len(recovered.estado('A')['perfis']),1)
        recovered.perfil('A','novo',nome='Three')
        self.assertEqual(len(MirrorStore(self.path).estado('A')['perfis']),2)
        json.loads(self.path.with_suffix('.json.bak').read_text())
    def test_valid_json_invalid_schema_keeps_recovered_backup_valid(self):
        self.store.perfil('A','novo',nome='One');self.store.perfil('A','novo',nome='Two')
        self.path.write_text('{"schema":2,"personagens":{}}',encoding='utf-8')
        recovered=MirrorStore(self.path);recovered.perfil('A','novo',nome='Three')
        backup=MirrorStore(self.path.with_suffix('.json.bak'))
        self.assertEqual(len(backup.estado('A')['perfis']),1)
    def test_automatic_names_never_become_overlay_labels(self):
        self.assertFalse(normalizar_recorte({})['mostrar_nome'])
        self.assertFalse(normalizar_recorte({'nome':'Mirror 1','mostrar_nome':True})['mostrar_nome'])
        self.assertFalse(normalizar_recorte({'nome':'Mirror 2'}, {'nome':'Mirror 2','mostrar_nome':True})['mostrar_nome'])
        self.assertTrue(normalizar_recorte({'nome':'BUFF','mostrar_nome':True})['mostrar_nome'])
    def test_large_output_rejected_before_allocating_native_images(self):
        with self.assertRaises(ValueError):normalizar_recorte({'modo':'manual','origem':{'w':2000,'h':1000},'escala':8})
    def test_invalid_geometry_and_nonfinite_numbers_rejected(self):
        for data in [{'origem':{'w':0,'h':32}},{'origem':{'x':-1,'w':32,'h':32}},{'escala':float('nan')},{'glow':{'cor':'red'}}]:
            with self.subTest(data=data),self.assertRaises(ValueError):normalizar_recorte(data)
    def test_duplicate_has_new_ids_and_nested_values_are_independent(self):
        first=self.store.perfil('A','novo',nome='One')
        crop=self.store.recorte('A','salvar',dados={'nome':'Ring'})
        second=self.store.perfil('A','duplicar',first['id'],'Two')
        self.assertNotEqual(crop['id'],second['recortes'][0]['id'])
        second['recortes'][0]['glow']['cor']='#ffffff'
        self.assertNotEqual(self.store.estado('A')['perfil']['recortes'][0]['glow']['cor'],'#ffffff')
    def test_copy_profile_from_another_character(self):
        # Goat Hell sem preset: copia o perfil do Zandao, com recortes independentes
        ms=self.store.perfil('Zandao','novo',nome='MS')
        self.store.recorte('Zandao','salvar',dados={'nome':'anel','origem':{'x':4,'y':5,'w':32,'h':32}})
        outros=self.store.estado('Goat Hell')['outros']
        self.assertEqual([(o['personagem'],o['nome'],o['recortes']) for o in outros],[('Zandao','MS',1)])
        copia=self.store.copiar('Goat Hell','zandao',ms['id'])
        goat=self.store.estado('Goat Hell')
        self.assertEqual((goat['ativo'],goat['perfil']['nome']),(copia['id'],'MS'))
        self.assertNotEqual(copia['recortes'][0]['id'],self.store.estado('Zandao')['perfil']['recortes'][0]['id'])
        self.store.recorte('Goat Hell','salvar',copia['recortes'][0]['id'],{'nome':'outro'})
        self.assertEqual(self.store.estado('Zandao')['perfil']['recortes'][0]['nome'],'anel')
        self.assertEqual(self.store.copiar('Goat Hell','Zandao',ms['id'])['nome'],'MS (Zandao)')  # nome repetido ganha o dono
        self.assertEqual(self.store.estado('Zandao')['outros'][0]['personagem'],'Goat Hell')
        before=self.path.read_bytes()
        for origem,pid in (('Zandao','nao-existe'),('Ninguem',ms['id']),('Goat Hell',copia['id'])):
            with self.assertRaises(ValueError):self.store.copiar('Goat Hell',origem,pid)
        self.assertEqual(self.path.read_bytes(),before)
    def test_scale_does_not_change_source_and_bulk_is_profile_local(self):
        first=self.store.perfil('A','novo',nome='One')
        crop=self.store.recorte('A','salvar',dados={})
        self.store.recorte('A','salvar',crop['id'],{'escala':3.0})
        self.assertEqual(self.store.estado('A')['perfil']['recortes'][0]['origem']['w'],32)
        self.store.perfil('A','duplicar',first['id'],'Two')
        self.store.todos('A','ocultar')
        self.assertFalse(self.store.estado('A')['perfil']['recortes'][0]['visivel'])
        self.store.perfil('A','usar',first['id'])
        self.assertTrue(self.store.estado('A')['perfil']['recortes'][0]['visivel'])

if __name__=='__main__':unittest.main()
