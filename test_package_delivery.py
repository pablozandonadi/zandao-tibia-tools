import json
from pathlib import Path
import tempfile
import unittest
import package_tools as p
from recovery import prepare_snapshot
class DeliveryTests(unittest.TestCase):
    def source(self,directory):
        source=Path(directory)/'source';source.mkdir();(source/'web').mkdir();(source/'sons_padrao').mkdir()
        (source/'web/index.html').write_text('app');(source/'icon.ico').write_bytes(b'icon')
        (source/'packaging-resources.json').write_text(json.dumps({'files':['web/index.html','icon.ico']}))
        return source
    def app(self,directory):
        app=Path(directory)/'app';app.mkdir();(app/'ZandaoTibiaTools.exe').write_bytes(b'MZ executable')
        (app/'_internal/web').mkdir(parents=True);(app/'_internal/web/index.html').write_text('app')
        return app
    def test_manifest_detects_changed_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            source=self.source(directory);app=self.app(directory)
            p.create_manifest(app,source,'1-beta','beta','a'*40)
            (app/'_internal/web/index.html').write_text('bad')
            with self.assertRaises(ValueError):p.verify_manifest(app)
    def test_private_data_rejected_even_nested(self):
        with tempfile.TemporaryDirectory() as directory:
            source=self.source(directory);app=self.app(directory)
            (app/'_internal/web/historico_hunts.json').write_text('{}')
            with self.assertRaises(ValueError):p.validate_layout(app,source)
    def test_unknown_resource_and_root_files_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            source=self.source(directory);app=self.app(directory)
            (source/'web/private.txt').write_text('secret')
            with self.assertRaises(ValueError):p.validate_resources(source)
            (app/'passwords.txt').write_text('private')
            with self.assertRaises(ValueError):p.validate_layout(app,source)
    def test_rollback_preserves_old_version_without_private_data(self):
        with tempfile.TemporaryDirectory() as directory:
            app=self.app(directory);(app/'preferencias.json').write_text('private')
            storage=Path(directory)/'user'
            snapshot=Path(prepare_snapshot('1.1.0',source=app,storage=storage))
            self.assertEqual((snapshot/'ZandaoTibiaTools.exe').read_bytes(),b'MZ executable')
            self.assertTrue((app/'ZandaoTibiaTools.exe').exists())
            self.assertFalse((snapshot/'preferencias.json').exists())
            self.assertTrue((storage/'atualizacao-pendente.json').exists())

    def test_online_credentials_rejected_at_any_package_depth(self):
        for filename in ('voice-online.json','voice-online.dpapi','voice-online.tmp','voice-online.json.tmp','voice-online.dpapi.tmp','admin-online.dpapi','admin-online.dpapi.tmp','voice-device.id','voice-device.id.tmp'):
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as directory:
                source=self.source(directory);app=self.app(directory)
                target=app/'_internal'/'nested'/filename
                target.parent.mkdir(parents=True)
                target.write_bytes(b'fake-private-payload')
                with self.assertRaisesRegex(ValueError,'Dados privados'):
                    p.validate_layout(app,source)

class AssistantDeliveryTests(unittest.TestCase):
    source = DeliveryTests.source
    app = DeliveryTests.app
    def test_contract_json_is_an_explicit_resource(self):
        with tempfile.TemporaryDirectory() as directory:
            source=self.source(directory);(source/'voice').mkdir();(source/'voice/domain_actions.json').write_text('{}')
            manifest=source/'packaging-resources.json';data=json.loads(manifest.read_text());data['files'].append('voice/domain_actions.json');manifest.write_text(json.dumps(data))
            p.validate_resources(source)
    def test_all_assistant_private_variants_are_rejected_at_any_depth(self):
        for name in ('assistente-tibiano.json','assistente-tibiano.json.tmp','assistente-tibiano.json.bak','assistente-tibiano.json.antes-do-backup','market-conversao-tc.json','market-conversao-tc.tmp'):
            with self.subTest(name=name),tempfile.TemporaryDirectory() as directory:
                source=self.source(directory);app=self.app(directory);target=app/'_internal'/'nested'/name;target.parent.mkdir(parents=True);target.write_text('{}')
                with self.assertRaisesRegex(ValueError,'Dados privados'):p.validate_layout(app,source)
