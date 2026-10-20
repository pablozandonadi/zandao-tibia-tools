import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import calculadora_gold as c
import chat


def preco(valor=48000, origem='padrão'):
    return lambda: (Decimal(valor), origem)


class Conversao(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pasta = Path(self.tmp.name)

    def r(self, texto, valor=48000, origem='padrão'):
        return c.responder(texto, self.pasta, preco(valor, origem))

    def test_exemplo_do_dono_42kk(self):
        r = self.r('farmei 42kk, quanto dá em reais?')
        self.assertIn('875 TC', r)
        self.assertIn('R$ 171,50', r)
        self.assertIn('R$ 182,00', r)
        self.assertIn('48k', r)
        self.assertIn('250 TC', r)
        self.assertIn('R$ 49,00 a R$ 52,00', r)

    def test_frases_parecidas_funcionam(self):
        for texto in ('quantos reais são 42kk', '42 kk em reais', 'quanto vale 42kk em R$', 'converte 42.000.000 gold pra reais',
                      '42000000 gp em reais', 'FARMEI 42KK QUANTO DA EM REAIS'):
            with self.subTest(texto=texto):
                self.assertIn('875 TC', self.r(texto))

    def test_decimais_e_milhar_no_formato_brasileiro(self):
        r = self.r('1,5kk em reais')
        self.assertIn('31,25 TC', r)
        self.assertIn('R$ 6,13', r)
        self.assertIn('R$ 6,50', r)
        grande = self.r('1.500kk em reais')
        self.assertIn('31.250 TC', grande)
        self.assertIn('R$ 6.125,00', grande)
        self.assertIn('R$ 6.500,00', grande)
        self.assertIn('R$ 6,13', self.r('1.5kk em reais'))

    def test_usa_o_preco_do_tc_informado_e_diz_a_origem(self):
        r = self.r('42kk em reais', valor=50000, origem='Market local')
        self.assertIn('840 TC', r)
        self.assertIn('50k', r)
        self.assertIn('Market local', r)

    def test_o_que_nao_e_conta_vai_para_a_ia(self):
        for texto in ('como converto gold em reais?', 'quantos reais custa um tc', '42kk', 'farmei 42kk hoje',
                      'o que é shared xp', 'farmei 42kk e 10kk, quanto dá em reais', 'receita de bolo'):
            with self.subTest(texto=texto):
                self.assertIsNone(self.r(texto))

    def test_valores_invalidos_sao_ignorados(self):
        for texto in ('0kk em reais', 'x' * 400 + ' 42kk em reais'):
            with self.subTest(texto=texto[:30]):
                self.assertIsNone(self.r(texto))

    def test_variaveis_ficam_salvas_e_aparecem(self):
        self.assertIn('pacote de 250 TC', self.r('variáveis do tc'))
        self.assertIn('R$ 49,00 a R$ 52,00', self.r('conversão tc'))
        salvo = self.r('pacote de 250 tc custa 50 a 55 reais')
        self.assertIn('R$ 50,00 a R$ 55,00', salvo)
        self.assertEqual(json.loads((self.pasta / 'conversao-tc.json').read_text(encoding='utf-8')),
                         {'pacote_tc': 250, 'reais_min': '50', 'reais_max': '55'})
        self.assertIn('R$ 175,00 a R$ 192,50', self.r('42kk em reais'))
        self.assertIn('R$ 50,00 a R$ 55,00', self.r('variaveis do tc'))

    def test_pacote_com_valor_unico(self):
        self.assertIn('R$ 50,00', self.r('pacote de 250 tc custa 50 reais'))
        r = self.r('42kk em reais')
        self.assertIn('R$ 175,00', r)
        self.assertNotIn('a R$ 175', r)

    def test_pacote_invalido_nao_grava(self):
        for texto in ('pacote de 250 tc custa 60 a 50 reais', 'pacote de 0 tc custa 50 reais', 'pacote de 250 tc custa 0 reais'):
            with self.subTest(texto=texto):
                self.assertIn('Não entendi', self.r(texto))
        self.assertFalse((self.pasta / 'conversao-tc.json').exists())

    def test_arquivo_corrompido_volta_ao_padrao(self):
        (self.pasta / 'conversao-tc.json').write_text('{lixo', encoding='utf-8')
        self.assertIn('R$ 171,50', self.r('42kk em reais'))
        (self.pasta / 'conversao-tc.json').write_text(json.dumps({'pacote_tc': 250, 'reais_min': '9999999', 'reais_max': '1'}), encoding='utf-8')
        self.assertIn('R$ 171,50', self.r('42kk em reais'))


class NoChat(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def chat(self, execute):
        store = SimpleNamespace(context=lambda: {'character_id': 'T', 'world_id': 'Antica', 'level': 1}, clock=lambda: None, execute=execute)
        return chat.Chat(store, self.tmp.name)

    def test_conta_local_sem_ia_e_com_preco_do_market(self):
        chamadas = []

        def execute(intent, args, context, request_id=None, source='manual'):
            chamadas.append((intent, args['offer_type'], request_id))
            return {'count': 3, 'median': 50000} if args['offer_type'] == 'sell' else {'count': 0, 'median': None}
        r = self.chat(execute).responder('farmei 42kk, quanto dá em reais?', permitir_ia=False)
        self.assertEqual(r['origem'], 'local')
        self.assertIn('840 TC', r['resposta'])
        self.assertIn('Market local', r['resposta'])
        self.assertTrue(chamadas and all(i == 'market.stats' and rid is None for i, _, rid in chamadas))

    def test_sem_preco_no_market_usa_o_padrao(self):
        def execute(*a, **k):
            return {'count': 0, 'median': None}
        r = self.chat(execute).responder('42kk em reais', permitir_ia=False)
        self.assertIn('875 TC', r['resposta'])
        self.assertIn('padrão', r['resposta'])

    def test_falha_ao_ler_o_market_usa_o_padrao(self):
        def execute(*a, **k):
            raise ValueError('sem dados')
        self.assertIn('875 TC', self.chat(execute).responder('42kk em reais', permitir_ia=False)['resposta'])

    def test_a_frase_normal_nem_consulta_o_market(self):
        def execute(*a, **k):
            raise AssertionError('não devia consultar o Market')
        r = self.chat(execute).responder('receita de bolo', permitir_ia=False)
        self.assertNotIn('TC', r['resposta'])


if __name__ == '__main__':
    unittest.main()
