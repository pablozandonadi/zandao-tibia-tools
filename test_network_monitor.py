import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock
import network_monitor as n


def adapter(key='a', **kw):
    return dict({'id': key, 'index': 20, 'name': 'Fibra', 'description': 'Ethernet',
                 'up': True, 'ip': '192.0.2.10', 'kind': 6, 'virtual': False}, **kw)


def results(a=30, b=40, error='timeout'):
    return [{'target': 'Cloudflare', 'ms': a, 'error': None if a is not None else error},
            {'target': 'Google', 'ms': b, 'error': None if b is not None else error}]


class LinkTests(unittest.TestCase):
    def setUp(self):
        self.link = n.Link(adapter())
        self.t = 1000

    def tick(self, values):
        self.t += 2
        return self.link.record(values, self.t, self.t, 150)

    def test_failure_needs_three_consecutive_rounds(self):
        for _ in range(2):
            self.tick(results(None, None))
            self.assertEqual(self.link.state, 'checking')
        self.tick(results(None, None))
        self.assertEqual(self.link.state, 'offline')
        self.assertFalse(self.tick(results(None, None)))

    def test_recovery_needs_five_complete_rounds(self):
        for _ in range(3): self.tick(results(None,None))
        for _ in range(4):
            self.tick(results())
            self.assertEqual(self.link.state, 'checking')
        self.tick(results())
        self.assertEqual(self.link.state, 'healthy')
        self.assertEqual(self.link.snapshot(self.t, 300)['healthy_for'], 8)

    def test_partial_success_never_means_offline(self):
        for _ in range(6): self.tick(results(None, 40))
        s = self.link.snapshot(self.t,300)
        self.assertEqual(s['state'],'degraded')
        self.assertIsNone(s['current'])  # no silent swap to the secondary destination
        self.assertEqual(s['loss'],50)

    def test_binding_failure_is_not_network_loss(self):
        for _ in range(6): self.tick(results(None,None,'binding'))
        s = self.link.snapshot(self.t,300)
        self.assertEqual(s['state'],'unavailable')
        self.assertIsNone(s['loss'])

    def test_high_latency_is_degraded(self):
        self.tick(results(200,40))
        self.assertEqual(self.link.state,'degraded')

    def test_disconnect_is_separate(self):
        self.link.adapter['up'] = False
        self.tick([])
        self.assertEqual(self.link.state,'disconnected')
        self.assertIsNone(self.link.history[-1]['loss'])

    def test_ipv6_only_is_not_offline(self):
        self.link.adapter['ip'] = None
        self.tick([])
        self.assertEqual(self.link.state,'unavailable')

    def test_sleep_does_not_extend_healthy_time(self):
        for _ in range(5): self.tick(results())
        self.t += 100
        self.tick(results())
        self.assertEqual(self.link.state,'checking')
        self.assertEqual(self.link.snapshot(self.t,300)['healthy_for'],0)
        self.assertIsNone(self.link.history[-2]['ms'])

    def test_buffer_is_bounded_and_timeout_not_zero(self):
        for _ in range(1600): self.tick(results(None,None))
        self.assertEqual(len(self.link.history),900)
        self.assertIsNone(self.link.snapshot(self.t,300)['current'])
        self.assertIsNone(self.link.snapshot(self.t,3600)['points'][-1]['ms'])

    def test_jitter_does_not_bridge_failures(self):
        self.tick(results(10,20)); self.tick(results(None,None)); self.tick(results(100,120))
        self.assertIsNone(self.link.snapshot(self.t,300)['jitter'])


class ProbeTests(unittest.TestCase):
    def fake(self):
        s=MagicMock(); s.__enter__.return_value=s
        s.getsockopt.return_value=20
        s.getsockname.return_value=('192.0.2.10',123)
        return s

    @patch('network_monitor.sys.platform','win32')
    def test_bound_socket_and_no_route_fallback(self):
        s=self.fake()
        r=n.probe(adapter(),n.TARGETS[0],socket_factory=lambda *args:s)
        self.assertIsNotNone(r['ms'])
        s.setsockopt.assert_called_once_with(n.socket.IPPROTO_IP,31,b'\x00\x00\x00\x14')
        s.bind.assert_called_once_with(('192.0.2.10',0))
        s.connect.assert_called_once_with(('1.1.1.1',443))

    @patch('network_monitor.sys.platform','win32')
    def test_binding_rejected_never_connects(self):
        s=self.fake(); s.getsockopt.return_value=6
        self.assertEqual(n.probe(adapter(),n.TARGETS[0],socket_factory=lambda *args:s)['error'],'binding')
        s.connect.assert_not_called()

    @patch('network_monitor.sys.platform','win32')
    def test_timeout_distinguished_from_internal_error(self):
        s=self.fake(); s.connect.side_effect=TimeoutError()
        self.assertEqual(n.probe(adapter(),n.TARGETS[0],socket_factory=lambda *args:s)['error'],'timeout')
        s.connect.side_effect=OSError(10022,'invalid')
        self.assertEqual(n.probe(adapter(),n.TARGETS[0],socket_factory=lambda *args:s)['error'],'measurement')


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.m=n.Monitor(Path(self.tmp.name)/'prefs.json',inventory=lambda:[adapter()])
        self.addCleanup(self.m.close)

    def test_virtual_and_unused_adapters_excluded_initially(self):
        self.m.inventory=lambda:[adapter(),adapter('b',virtual=True),adapter('c',up=False)]
        self.m._refresh()
        self.assertEqual(self.m.snapshot()['selected'],1)

    def test_missing_adapter_is_retained_as_disconnected(self):
        self.m._refresh(); self.m.inventory=lambda:[]; self.m._refresh()
        self.assertFalse(self.m.links['a'].adapter['up'])

    def test_preferences_persist_without_samples_or_ips(self):
        with patch.object(self.m,'start'):
            self.m.configure({'enabled':True,'aliases':{'a':'Vivo'},'interval':1})
        stored=json.loads(self.m.path.read_text(encoding='utf-8'))
        self.assertTrue(stored['enabled'])
        self.assertNotIn('links',stored)
        self.assertNotIn('192.0.2.10',self.m.path.read_text())

    def test_bad_configuration_does_not_mutate(self):
        with self.assertRaises(ValueError): self.m.configure({'interval':0})
        self.assertFalse(self.m.config['enabled'])

    def test_paused_snapshot_does_not_claim_healthy(self):
        self.m._refresh(); self.m.links['a'].state='healthy'
        s=self.m.snapshot()
        self.assertEqual(s['healthy'],0)
        self.assertEqual(s['links'][0]['state'],'paused')

    def test_monitor_limit(self):
        self.m.inventory=lambda:[adapter(str(i)) for i in range(12)]
        self.m._refresh()
        self.assertEqual(self.m.snapshot()['selected'],8)


if __name__=='__main__': unittest.main()
