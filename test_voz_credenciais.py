import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from voz_credenciais import carregar_chave


class CredenciaisVozTests(unittest.TestCase):
    def test_missing_configuration_does_not_decrypt(self):
        with patch.dict(os.environ, {'LOCALAPPDATA': ''}), patch('voz_credenciais._desproteger') as decrypt:
            self.assertIsNone(carregar_chave())
            decrypt.assert_not_called()

    def test_fake_encrypted_file_is_read_without_changes(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'LOCALAPPDATA': folder}):
            path = Path(folder) / 'TibiaTudo' / 'credentials' / 'elevenlabs.dpapi'
            path.parent.mkdir(parents=True)
            path.write_text('0102', encoding='utf-8')
            original = path.read_bytes()
            with patch('voz_credenciais._desproteger', return_value='fake-test-value') as decrypt:
                self.assertEqual(carregar_chave(), 'fake-test-value')
                decrypt.assert_called_once_with(b'\x01\x02')
            self.assertEqual(path.read_bytes(), original)

    def test_absent_invalid_and_wrong_user_fail_quietly(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'LOCALAPPDATA': folder}):
            path = Path(folder) / 'TibiaTudo' / 'credentials' / 'elevenlabs.dpapi'
            self.assertIsNone(carregar_chave())
            path.parent.mkdir(parents=True)
            for invalid in ('', 'not-a-protected-value', '01' * 9000):
                path.write_text(invalid, encoding='utf-8')
                with patch('voz_credenciais._desproteger') as decrypt:
                    self.assertIsNone(carregar_chave())
                    decrypt.assert_not_called()
            path.write_text('0102', encoding='utf-8')
            with patch('voz_credenciais._desproteger', side_effect=ValueError('Wrong user')):
                self.assertIsNone(carregar_chave())
            with patch('voz_credenciais._desproteger', return_value='  '):
                self.assertIsNone(carregar_chave())


if __name__ == '__main__':
    unittest.main()
