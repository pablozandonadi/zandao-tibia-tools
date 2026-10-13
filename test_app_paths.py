from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import app_paths as a
from single_instance import InstanceGuard
class PathsTests(unittest.TestCase):
    def test_channels_never_share_data_and_source_unchanged(self):
        with patch.object(a.sys,'frozen',True,create=True),patch.dict(a.os.environ,{'LOCALAPPDATA':'C:/fake'}):
            with patch.object(a,'CANAL_APP','beta'):beta=a.data_dir()
            with patch.object(a,'CANAL_APP','stable'):stable=a.data_dir()
            self.assertNotEqual(beta,stable)
            self.assertTrue(beta.endswith('beta'))
    def test_migration_preserves_source_and_existing_data(self):
        with tempfile.TemporaryDirectory() as directory:
            old,new=Path(directory)/'old',Path(directory)/'new';old.mkdir();new.mkdir()
            (old/'historico_hunts.json').write_text('legacy');(old/'sets.json').write_text('old')
            (new/'sets.json').write_text('current');(old/'cache_monstros.json').write_text('cache')
            a.migrate_legacy(old,new)
            self.assertEqual((new/'historico_hunts.json').read_text(),'legacy')
            self.assertEqual((old/'historico_hunts.json').read_text(),'legacy')
            self.assertEqual((new/'sets.json').read_text(),'current')
            self.assertFalse((new/'cache_monstros.json').exists())
            self.assertEqual(a.migrate_legacy(old,new),[])
    def test_migration_copies_custom_sounds(self):
        with tempfile.TemporaryDirectory() as directory:
            old,new=Path(directory)/'old',Path(directory)/'new';(old/'sons_usuario').mkdir(parents=True)
            (old/'sons_usuario'/'alert.wav').write_bytes(b'wave')
            a.migrate_legacy(old,new)
            self.assertEqual((new/'sons_usuario'/'alert.wav').read_bytes(),b'wave')
    def test_second_instance_rejected_and_lock_released(self):
        with tempfile.TemporaryDirectory() as directory:
            first,second=InstanceGuard(directory),InstanceGuard(directory)
            self.assertTrue(first.acquire());self.assertFalse(second.acquire())
            second.request_activation();self.assertTrue((Path(directory)/'activate.request').exists())
            first.close();self.assertTrue(second.acquire());second.close()
