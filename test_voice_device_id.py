import tempfile
import unittest
import uuid
from pathlib import Path

from voice import device_id


class DeviceIdTests(unittest.TestCase):
    def test_cria_uma_vez_e_reaproveita(self):
        with tempfile.TemporaryDirectory() as pasta:
            a, b = device_id.carregar(pasta), device_id.carregar(Path(pasta))
            self.assertEqual(a, b)
            self.assertEqual(uuid.UUID(a).version, 4)
            self.assertEqual((Path(pasta) / 'voice-device.id').read_text(), a)

    def test_arquivo_corrompido_e_refeito(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / 'voice-device.id'
            for lixo in ('lixo', '', str(uuid.uuid1())):
                arquivo.write_text(lixo)
                novo = device_id.carregar(pasta)
                self.assertEqual(uuid.UUID(novo).version, 4)
                self.assertEqual(arquivo.read_text(), novo)


if __name__ == '__main__':
    unittest.main()
