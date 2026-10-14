import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import historico
from web_api import API


class ExportarHuntsSelecionadasTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.destino = Path(self.tmp.name) / 'hunts.json'
        self.api = API.__new__(API)
        self.api._window = Mock()
        self.api._window.create_file_dialog.return_value = [str(self.destino)]
        self.hunts = [{'id': str(i), 'personagem': 'Teste', 'salvo_em': '2026-01-01'} for i in range(7)]
        mock = patch.object(historico, 'carregar', return_value=self.hunts)
        mock.start()
        self.addCleanup(mock.stop)

    def exportados(self, ids):
        result = self.api.hunt_exportar('', ids)
        self.assertTrue(result['ok'])
        data = json.loads(self.destino.read_text(encoding='utf-8'))
        self.assertEqual(data['formato'], historico.FORMATO)
        self.assertEqual(result['qtd'], len(data['hunts']))
        return {h['id'] for h in data['hunts']}

    def test_sem_marcacao_exporta_todo_historico(self):
        self.assertEqual(self.exportados([]), {str(i) for i in range(7)})

    def test_marcacao_exporta_somente_as_hunts_escolhidas(self):
        self.assertEqual(self.exportados(['1', '3', '5']), {'1', '3', '5'})

    def test_permite_exportar_mais_de_quatro_hunts(self):
        self.assertEqual(self.exportados(['0', '1', '2', '3', '4', '5']), {str(i) for i in range(6)})

    def test_ids_repetidos_ou_apagados_nao_ampliam_exportacao(self):
        self.assertEqual(self.exportados(['2', '2', 'inexistente']), {'2'})

    def test_selecao_apagada_nao_exporta_tudo_por_engano(self):
        result = self.api.hunt_exportar('', ['inexistente'])
        self.assertFalse(result['ok'])
        self.api._window.create_file_dialog.assert_not_called()
        self.assertFalse(self.destino.exists())

    def test_cancelar_nao_grava_arquivo(self):
        self.api._window.create_file_dialog.return_value = None
        result = self.api.hunt_exportar('', ['2'])
        self.assertTrue(result['cancelado'])
        self.assertFalse(self.destino.exists())


if __name__ == '__main__':
    unittest.main()
