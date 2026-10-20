import re
import unittest
from pathlib import Path

from versao import porta_http


class PortaHttpPorCanal(unittest.TestCase):
    def test_cada_canal_tem_a_sua_porta(self):
        self.assertEqual(porta_http('stable'), 42001)
        self.assertEqual(porta_http('beta'), 42002)
        self.assertNotEqual(porta_http('stable'), porta_http('beta'))

    def test_canal_desconhecido_cai_na_porta_da_estavel(self):
        self.assertEqual(porta_http(''), 42001)
        self.assertEqual(porta_http('qualquer'), 42001)

    def test_a_janela_usa_a_porta_do_canal(self):
        # Sem isso o pywebview usa 42001 para todas as instâncias e a janela da Beta, com a estável aberta, carrega
        # os arquivos web da estável (sem a aba Admin).
        fonte = Path(__file__).with_name('zandao_tibia_tools.py').read_text(encoding='utf-8')
        self.assertRegex(fonte, r'webview\.start\(.*?http_port=porta_http\(CANAL_APP\)')
        self.assertIsNone(re.search(r'http_port\s*=\s*42001', fonte))


if __name__ == '__main__':
    unittest.main()
