import re
import unittest
from pathlib import Path

import baixar_imagens_bosses as bi
import boss_catalog

NOMES = {
    'Arkhothep (Criatura)': 'arkhothep.gif',
    'Zushuka (Mortal)': 'zushuka.gif',
    'Grand Master Oberon': 'grand_master_oberon.gif',
    "Ghazbaran's Heir": 'ghazbaran_s_heir.gif',
    'Time-displaced Thing': 'time_displaced_thing.gif',
    'Bakragore (Ágil)': 'bakragore.gif',
    'Árvore Mãe': 'rvore_m_e.gif',
    '  The Old Widow ': 'the_old_widow.gif',
}


def regra_js(name):
    """Regra de bossImage em web/assistente.js, lida do próprio arquivo e reaplicada em Python."""
    js = Path('web/assistente.js').read_text(encoding='utf-8')
    assert "name.split(' (')[0].toLowerCase().replace(/[^a-z0-9]+/g,'_').replace(/^_|_$/g,'')" in js
    return re.sub(r'^_|_$', '', re.sub(r'[^a-z0-9]+', '_', name.split(' (')[0].lower())) + '.gif'


class BossImagesTests(unittest.TestCase):
    def test_nome_igual_regra_js(self):
        for name, esperado in NOMES.items():
            with self.subTest(name=name):
                self.assertEqual(bi.nome_arquivo(name), regra_js(name))
        for name, esperado in list(NOMES.items())[:6]:
            self.assertEqual(bi.nome_arquivo(name), esperado)
        for entry in boss_catalog.BOSSES:
            self.assertEqual(bi.nome_arquivo(entry[0]), regra_js(entry[0]))

    def test_gif_valido(self):
        self.assertTrue(bi.gif_valido(b'GIF89a' + b'0' * 300))
        self.assertFalse(bi.gif_valido(b'GIF89a'))
        self.assertFalse(bi.gif_valido(b'\x89PNG' + b'0' * 300))
        self.assertFalse(bi.gif_valido(b'GIF89a' + b'0' * 400000))

    def test_arquivos_baixados_sao_gif(self):
        for entry in boss_catalog.BOSSES:
            path = bi.DESTINO / bi.nome_arquivo(entry[0])
            if path.exists():
                with self.subTest(path=path.name):
                    self.assertEqual(path.read_bytes()[:4], b'GIF8')

    def test_maioria_dos_bosses_tem_imagem(self):
        com = sum((bi.DESTINO / bi.nome_arquivo(e[0])).exists() for e in boss_catalog.BOSSES)
        self.assertGreaterEqual(com, 500)


if __name__ == '__main__':
    unittest.main()
