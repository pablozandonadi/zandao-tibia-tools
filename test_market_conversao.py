import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import market_conversao as c
import web_api


class ConversionTests(unittest.TestCase):
    def test_defaults_and_brazilian_gold_formats(self):
        for gold in ['11.650.000', '11.650.000 GP', '11.650.000 gold', '11,65kk', '11650k', 11650000]:
            with self.subTest(gold=gold):
                self.assertEqual({'tc': '250.00', 'reais': '50.00'}, c.calcular(gold, c.DEFAULTS))
        self.assertEqual('4.29', c.calcular('1kk', c.DEFAULTS)['reais'])
        self.assertEqual('0.00', c.calcular(0, c.DEFAULTS)['reais'])

    def test_custom_rate_and_money_rounding(self):
        values = {'gold_por_tc': '50k', 'tc_pacote': '100', 'reais_pacote': '25,50'}
        self.assertEqual({'tc': '20.00', 'reais': '5.10'}, c.calcular('1kk', values))
        self.assertEqual('0.01', c.calcular(1, {'gold_por_tc': 1, 'tc_pacote': 2, 'reais_pacote': '0.01'})['reais'])

    def test_invalid_inputs_are_rejected_and_magnitude_is_bounded(self):
        for gold in ['', 'NaN', 'Infinity', float('inf'), float('nan'), -1, '1e100', '1.2.3', '1,234,567', '0.1 GP', '1kk;alert(1)', 10**13, '9'*49, None, True]:
            with self.subTest(gold=gold), self.assertRaises(ValueError):
                c.calcular(gold, c.DEFAULTS)
        for key in c.DEFAULTS:
            for invalid in ['0', '-1', 'nan', 'inf', '', '0.0000001']:
                with self.subTest(key=key, invalid=invalid), self.assertRaises(ValueError):
                    c.calcular('1kk', {**c.DEFAULTS, key: invalid})
        self.assertTrue(c.calcular(10**12, {'gold_por_tc': '1', 'tc_pacote': '0.000001', 'reais_pacote': str(10**12)})['reais'].endswith('.00'))

    def test_only_rates_are_saved_and_chat_file_is_untouched(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path/'conversao-tc.json').write_text('chat settings')
            self.assertEqual({'valores': c.DEFAULTS}, c.carregar(directory))
            c.calcular('1kk', c.DEFAULTS)
            self.assertEqual(['conversao-tc.json'], [p.name for p in path.iterdir()])
            c.salvar(directory, c.DEFAULTS)
            self.assertEqual(c.DEFAULTS, c.carregar(directory)['valores'])
            self.assertEqual(set(c.DEFAULTS), set(json.loads((path/'market-conversao-tc.json').read_text())))
            self.assertEqual('chat settings', (path/'conversao-tc.json').read_text())
            with self.assertRaises(ValueError): c.salvar(directory, {**c.DEFAULTS, 'gold': '100'})

    def test_invalid_saved_settings_are_preserved_and_defaults_are_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'market-conversao-tc.json'
            for invalid in ['{bad', '{}', json.dumps({**c.DEFAULTS, 'tc_pacote': 0})]:
                path.write_text(invalid)
                result = c.carregar(directory)
                self.assertEqual(c.DEFAULTS, result['valores'])
                self.assertIn('preservado', result['aviso'])
                self.assertEqual(invalid, path.read_text())

    def test_api_uses_private_directory_and_returns_validation_errors(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(web_api, 'BASE_DIR', directory):
            api = web_api.API()
            self.assertEqual('50.00', api.conversao_tc_calcular('11650k', c.DEFAULTS)['reais'])
            self.assertIn('erro', api.conversao_tc_calcular('NaN', c.DEFAULTS))
            self.assertIn('erro', api.conversao_tc_salvar({}))
            api.conversao_tc_salvar(c.DEFAULTS)
            self.assertEqual(c.DEFAULTS, api.conversao_tc_carregar()['valores'])

    def test_price_api_reads_only_the_requested_world(self):
        from types import SimpleNamespace
        store = unittest.mock.Mock()
        store.market_prices.return_value = {'total': 0, 'observations': [], 'world_id': 'Antica'}
        api = web_api.API()
        with patch.object(api, '_voz_obter', return_value=SimpleNamespace(store=store)):
            self.assertEqual(0, api.assistente_precos('Antica')['total'])
            store.market_prices.assert_called_once_with('Antica')
            store.market_prices.side_effect = ValueError('invalid')
            self.assertIn('erro', api.assistente_precos(''))
