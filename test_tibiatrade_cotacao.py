from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import threading
import unittest
from unittest.mock import patch

import tibiatrade_cotacao as c

NOW = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)


def row(world='Antica', price=46600, age=1):
    return {'world_name': world, 'sell_average_price': price, 'buy_average_price': 45000,
            'buy_highest_price': 45200, 'sell_lowest_price': 46500,
            'created_at': (NOW-timedelta(hours=age)).isoformat()}


class QuoteTests(unittest.TestCase):
    def setUp(self):
        for key, value in [('_rows', None), ('_consulta', None), ('_success', None), ('_attempt', None), ('_failed', False)]:
            target = patch.object(c, key, value)
            target.start(); self.addCleanup(target.stop)
        self.now = patch.object(c, '_now', return_value=NOW).start()
        self.clock = patch.object(c.time, 'monotonic', return_value=1000).start()
        self.trade = patch.object(c.sources, 'trade', return_value={'prices': [row(), row('Rasteibra', 46000, 96)]}).start()
        self.addCleanup(patch.stopall)

    def test_each_world_uses_its_own_base_date_and_daily_sell_average(self):
        result = c.consultar('antica')
        self.assertEqual(('ok', 46600), (result['estado'], result['gold_por_tc']))
        self.assertEqual('antiga', c.consultar('Rasteibra')['estado'])
        self.trade.assert_called_once_with('tibiaCoinPrice.list')
        self.assertEqual((NOW-timedelta(hours=1)).isoformat(), result['data_base'])

    def test_age_boundary_and_future_tolerance(self):
        for age, expected in [(36, 'ok'), (36.001, 'antiga'), (-1/12, 'ok'), (-.084, 'invalida')]:
            c._rows = [row(age=age)]; c._success = 1000
            self.assertEqual(expected, c.consultar('Antica')['estado'])

    def test_missing_duplicate_and_bad_rows_do_not_damage_other_worlds(self):
        for invalid in [row(price=True), row(price=0), row(price=-1), row(price='46600'), row(price=10**13), {**row(), 'created_at':'bad'}, {**row(), 'created_at':'2026-10-20T12:00:00'}]:
            c._rows = [invalid, row('Honbra')]; c._success = 1000
            self.assertEqual('invalida', c.consultar('Antica')['estado'])
            self.assertEqual('ok', c.consultar('Honbra')['estado'])
        c._rows = [row(), row('ANTICA'), None, {'world_name': 5}, row('Honbra')]
        self.assertEqual('invalida', c.consultar('Antica')['estado'])
        self.assertEqual('ok', c.consultar('Honbra')['estado'])
        self.assertEqual('ausente', c.consultar('Secura')['estado'])

    def test_invalid_world_or_force_never_fetches(self):
        for world in ['', 'https://bad', 'A', 'a'*41, '<script>', 1, 'Antica/']:
            self.assertEqual('invalida', c.consultar(world)['estado'])
        self.assertEqual('invalida', c.consultar('Antica', 'yes')['estado'])
        self.trade.assert_not_called()

    def test_cache_ttl_and_force_are_rate_limited(self):
        first = c.consultar('Antica')
        self.clock.return_value = 1059
        c.consultar('Antica', True)
        self.assertEqual(1, self.trade.call_count)
        self.clock.return_value = 1060
        c.consultar('Antica', True)
        self.assertEqual(2, self.trade.call_count)
        self.clock.return_value = 4659
        self.assertEqual(first['consulta'], c.consultar('Antica')['consulta'])
        self.assertEqual(2, self.trade.call_count)
        self.clock.return_value = 4660
        c.consultar('Antica')
        self.assertEqual(3, self.trade.call_count)

    def test_failure_uses_manual_and_recovers_after_cooldown(self):
        c.consultar('Antica')
        self.trade.side_effect = OSError('offline')
        self.clock.return_value = 1060
        self.assertEqual('indisponivel', c.consultar('Antica', True)['estado'])
        self.clock.return_value = 1119
        self.assertEqual('indisponivel', c.consultar('Antica')['estado'])
        self.assertEqual(2, self.trade.call_count)
        self.clock.return_value = 1120
        self.trade.side_effect = None
        self.assertEqual('ok', c.consultar('Antica')['estado'])
        self.assertEqual(3, self.trade.call_count)

    def test_bad_payload_and_simultaneous_requests(self):
        for payload in [{}, {'prices': []}, {'prices': 'bad'}]:
            c._attempt = None
            self.trade.return_value = payload
            self.assertEqual('indisponivel', c.consultar('Antica')['estado'])
        c._attempt = None
        started, release = threading.Event(), threading.Event()
        def fetch(_):
            started.set(); release.wait(2)
            return {'prices': [row()]}
        self.trade.side_effect = fetch
        calls = self.trade.call_count
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(c.consultar, 'Antica')
            self.assertTrue(started.wait(1))
            second = pool.submit(c.consultar, 'Antica')
            release.set()
            self.assertEqual('ok', first.result()['estado'])
            self.assertEqual('ok', second.result()['estado'])
        self.assertEqual(calls+1, self.trade.call_count)
