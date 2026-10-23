"""Gold por TC do TibiaTrade e da conversão manual entram no histórico do Tibia Coin, sem duplicar."""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import assistente_tibiano as a

NOW = datetime(2026, 10, 23, 12, tzinfo=timezone.utc)


class HistoricoTC(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.store = a.Store(self.dir.name, clock=lambda: NOW)

    def add(self, price, at, source):
        return self.store.market_quote_add('Rasteibra', 'Tibia Coin', price, at, source)

    def test_site_um_por_data_base_e_manual_so_quando_muda(self):
        base = (NOW - timedelta(days=2)).isoformat()
        self.assertIsNotNone(self.add(45139, base, 'tibiatrade'))
        self.assertIsNone(self.add(45139, base, 'tibiatrade'), 'mesma data-base não duplica')
        self.assertIsNotNone(self.add('46600', None, 'manual'))
        self.assertIsNone(self.add('46600', None, 'manual'), 'manual igual ao último não duplica')
        self.assertIsNotNone(self.add('47000', None, 'manual'))
        item = next(i for i in self.store.market_prices('Rasteibra')['items'] if i['item'] == 'Tibia Coin')
        self.assertEqual(3, item['total'])
        self.assertEqual(47000, item['latest']['sell']['price_gp'], 'venda do card = só preços do jogador')
        self.assertEqual(45139, item['latest']['tibiatrade']['price_gp'])

    def test_apagado_do_site_nao_volta(self):
        base = (NOW - timedelta(days=1)).isoformat()
        obs = self.add(45000, base, 'tibiatrade')
        self.store.execute('market.price.delete', {'observation_id': obs['id'], 'reason': 'errado'},
                           context={'world_id': 'Rasteibra'})
        self.assertIsNone(self.add(45000, base, 'tibiatrade'))

    def test_rejeita_origem_preco_e_futuro_invalidos(self):
        for args in [(45000, NOW, 'site'), (0, NOW, 'tibiatrade'), (45000, NOW + timedelta(hours=1), 'tibiatrade')]:
            with self.assertRaises(ValueError):
                self.add(*args)

    def test_arquivo_com_origem_desconhecida_e_recusado(self):
        self.add(45000, NOW, 'tibiatrade')
        path = Path(self.dir.name) / 'assistente-tibiano.json'
        d = json.loads(path.read_text(encoding='utf-8'))
        d['prices'][0]['source'] = 'hack'
        path.write_text(json.dumps(d), encoding='utf-8')
        with self.assertRaises(ValueError):
            a.Store(self.dir.name)


class ApiTC(unittest.TestCase):
    def setUp(self):
        import web_api
        self.web_api = web_api
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.store = a.Store(self.dir.name, clock=lambda: NOW)
        self.api = web_api.API.__new__(web_api.API)
        self.api._voz_obter = lambda: type('S', (), {'store': self.store})()

    def test_cotacao_antiga_e_manual_salvas(self):
        quote = {'estado': 'antiga', 'mundo': 'Rasteibra', 'gold_por_tc': 45139, 'data_base': (NOW - timedelta(days=2)).isoformat()}
        with patch.object(self.web_api.tibiatrade_cotacao, 'consultar', return_value=dict(quote)):
            self.assertTrue(self.api.conversao_tc_cotacao('Rasteibra')['registrado'])
            self.assertFalse(self.api.conversao_tc_cotacao('Rasteibra')['registrado'])
        with patch.object(self.web_api, 'BASE_DIR', self.dir.name):
            r = self.api.conversao_tc_salvar({'gold_por_tc': '46,6k', 'tc_pacote': '250', 'reais_pacote': '50'}, False, 'Rasteibra')
        self.assertTrue(r['registrado'])
        sources = [o.get('source') for o in self.store.market_prices('Rasteibra')['observations']]
        self.assertEqual(['manual', 'tibiatrade'], sources)

    def test_indisponivel_nao_grava(self):
        with patch.object(self.web_api.tibiatrade_cotacao, 'consultar', return_value={'estado': 'indisponivel'}):
            self.assertNotIn('registrado', self.api.conversao_tc_cotacao('Rasteibra'))
        self.assertEqual(0, self.store.market_prices('Rasteibra')['total'])


if __name__ == '__main__':
    unittest.main()
