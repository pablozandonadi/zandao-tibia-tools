import concurrent.futures
import unittest
from unittest.mock import patch

import comandos_tibia
import mensagens_tibianas as mensagens
import zandaobot_report


class MensagensTibianas(unittest.TestCase):
    def setUp(self):
        with mensagens._lock:
            mensagens._fila.clear()
            mensagens._ultima = None

    def test_catalogo_original_com_60_mensagens_distintas_em_texto(self):
        self.assertEqual(len(mensagens.MENSAGENS), 60)
        self.assertEqual(len(set(mensagens.MENSAGENS)), 60)
        for texto in mensagens.MENSAGENS:
            self.assertIsInstance(texto, str)
            self.assertTrue(texto.strip())
            self.assertNotIn('<', texto)
            self.assertNotIn('>', texto)

    def test_ciclo_completo_sem_repeticao(self):
        sorteadas = [mensagens.proxima() for _ in range(60)]
        self.assertEqual(set(sorteadas), set(mensagens.MENSAGENS))
        self.assertEqual(len(set(sorteadas)), 60)

    def test_virada_nao_repete_a_ultima_mesmo_quando_embaralhamento_iguala(self):
        with patch.object(mensagens.random, 'shuffle', side_effect=lambda fila: fila.sort()):
            primeiro = [mensagens.proxima() for _ in range(60)]
            # Força a próxima fila a terminar justamente na última mensagem anterior.
            with patch.object(mensagens.random, 'shuffle', side_effect=lambda fila: fila.sort(reverse=True)):
                segundo = [mensagens.proxima() for _ in range(60)]
        self.assertNotEqual(primeiro[-1], segundo[0])
        self.assertEqual(set(segundo), set(mensagens.MENSAGENS))

    def test_60_chamadas_concorrentes_nao_duplicam(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
            sorteadas = list(pool.map(lambda _: mensagens.proxima(), range(60)))
        self.assertEqual(len(set(sorteadas)), 60)

    def test_report_sorteia_uma_vez_e_preserva_campos_e_extras(self):
        with patch.object(mensagens, 'proxima', return_value='Piada tibiana de teste.') as escolher:
            texto = zandaobot_report.gerar({'mundo': 'Antica'}, {'comunidade': 'Tibianos', 'assinatura': 'Aventureiro'}, extras=['EXTRA'])
        escolher.assert_called_once_with()
        self.assertEqual(texto.count('💬 *Mensagem do dia:*'), 1)
        self.assertEqual(texto.count('Piada tibiana de teste.'), 1)
        self.assertLess(texto.index('Bom dia'), texto.index('Mensagem do dia'))
        self.assertLess(texto.index('Mensagem do dia'), texto.index('*Mundo:*'))
        self.assertIn('EXTRA', texto)
        self.assertIn('_Aventureiro_', texto)

    def test_bomdia_inclui_a_mesma_secao_sem_novo_sorteio(self):
        with patch.object(comandos_tibia.zandaobot, 'buscar', return_value={'mundo': 'Antica'}), \
                patch.object(comandos_tibia, '_kill', return_value='KILL'), \
                patch.object(mensagens, 'proxima', return_value='Piada tibiana de teste.') as escolher:
            texto = comandos_tibia.responder('bomdia', 'Antica')
        escolher.assert_called_once_with()
        self.assertEqual(texto.count('💬 *Mensagem do dia:*'), 1)
        self.assertIn('KILL', texto)


if __name__ == '__main__':
    unittest.main()
