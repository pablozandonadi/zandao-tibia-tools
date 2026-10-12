import io
import json
import unittest
from unittest.mock import patch
import atualizacoes as a


def release(tag, beta=True, name='ZandaoTibiaToolsBetaSetup.exe', draft=False):
    return dict(tag_name=tag, prerelease=beta, draft=draft,
                assets=[dict(name=name, browser_download_url='https://example.com/'+name)])


class TestCanais(unittest.TestCase):
    def check(self, data, channel='beta', current='1.0.19-beta.1.1'):
        installer = 'ZandaoTibiaToolsBetaSetup.exe' if channel == 'beta' else 'ZandaoTibiaToolsSetup.exe'
        with patch.object(a, 'CANAL_APP', channel), patch.object(a, 'VERSAO_APP', current), \
             patch.object(a, 'NOME_INSTALADOR', installer), \
             patch.object(a.urllib.request, 'urlopen', return_value=io.BytesIO(json.dumps(data).encode())) as request:
            result = a.verificar_atualizacao()
            endpoint = request.call_args.args[0].full_url
        return result, endpoint

    def test_beta_escolhe_nova_execucao_e_ignora_estavel_rascunho_e_asset_errado(self):
        data=[release('v99.0.0',False,'ZandaoTibiaToolsSetup.exe'),
              release('v1.0.19-beta.2.1'),release('v1.0.19-beta.10.1'),
              release('v1.0.19-beta.99.1',draft=True),
              release('v1.0.19-beta.98.1',name='ZandaoTibiaToolsSetup.exe')]
        result,url=self.check(data)
        self.assertEqual(result['versao'],'v1.0.19-beta.10.1')
        self.assertIn('releases?per_page=100',url)

    def test_tentativa_nova(self):
        result,_=self.check([release('v1.0.19-beta.1.2')])
        self.assertIsNotNone(result)

    def test_igual_ou_antiga_nao_atualiza(self):
        result,_=self.check([release('v1.0.19-beta.1.1'),release('v1.0.18-beta.999.1')])
        self.assertIsNone(result)

    def test_estavel_so_aceita_instalador_estavel(self):
        result,url=self.check(release('v1.0.20',False,'ZandaoTibiaToolsSetup.exe'),'stable','1.0.19')
        self.assertEqual(result['versao'],'v1.0.20')
        self.assertTrue(url.endswith('/releases/latest'))
        result,_=self.check(release('v1.0.20-beta.2.1'),'stable','1.0.19')
        self.assertIsNone(result)

    def test_falha_de_rede_nao_interrompe_app(self):
        with patch.object(a.urllib.request,'urlopen',side_effect=OSError('offline')):
            self.assertIsNone(a.verificar_atualizacao())

    def test_ordem_numerica_e_versao_invalida(self):
        self.assertGreater(a.versao_para_tupla('v1.0.19'),a.versao_para_tupla('1.0.19-beta.999.1'))
        with self.assertRaises(ValueError):
            a.versao_para_tupla('qualquer.exe')

if __name__ == '__main__':
    unittest.main()
