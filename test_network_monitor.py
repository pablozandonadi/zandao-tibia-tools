import json
from pathlib import Path
import tempfile
import unittest
import threading
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

    def test_failure_needs_two_consecutive_rounds(self):
        self.tick(results(None, None))
        self.assertEqual(self.link.state, 'checking')
        self.tick(results(None, None))
        self.assertEqual(self.link.state, 'offline')
        self.assertFalse(self.tick(results(None, None)))

    def test_first_response_confirms_connection_even_with_high_ping(self):
        self.tick(results(None, None)); self.tick(results(None, None))
        self.tick(results(200, 40))
        snapshot=self.link.snapshot(self.t,300)
        self.assertTrue(snapshot['connected'])
        self.assertEqual(snapshot['label'],'Conectado')
        self.assertEqual(snapshot['connected_for'],0)

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
        self.assertEqual(self.link.state,'healthy')
        self.assertEqual(self.link.snapshot(self.t,300)['connected_for'],0)
        self.assertIsNone(self.link.history[-2]['ms'])

    def test_buffer_is_bounded_and_timeout_not_zero(self):
        for _ in range(1600): self.tick(results(None,None))
        self.assertEqual(len(self.link.history),900)
        self.assertIsNone(self.link.snapshot(self.t,300)['current'])
        self.assertIsNone(self.link.snapshot(self.t,3600)['points'][-1]['ms'])

    def test_jitter_does_not_bridge_failures(self):
        self.tick(results(10,20)); self.tick(results(None,None)); self.tick(results(100,120))
        self.assertIsNone(self.link.snapshot(self.t,300)['jitter'])


class TrafficTests(unittest.TestCase):
    def setUp(self):
        self.link = n.Link(adapter())

    def read(self, received, sent, mono, luid=42):
        self.link.read_traffic(lambda index: (luid, received, sent), mono)

    def test_baseline_64bit_deltas_and_multiple_samples(self):
        self.assertIsNone(self.link.snapshot(1000, 300)['traffic']['received'])
        self.read(2**40, 2**41, 1)
        self.assertEqual(self.link.traffic, {'received': 0, 'sent': 0, 'available': True, 'partial': False})
        self.read(2**40 + 2**33, 2**41 + 20, 2)
        self.read(2**40 + 2**33 + 10, 2**41 + 50, 3)
        self.assertEqual(self.link.traffic['received'], 2**33 + 10)
        self.assertEqual(self.link.traffic['sent'], 50)

    def test_counter_reset_identity_change_and_suspend_rebase(self):
        self.read(100, 200, 1)
        self.read(120, 230, 2)
        self.read(0, 0, 3)
        self.read(10, 10, 4)
        self.read(5000, 6000, 5, luid=43)
        self.link.adapter['index'] = 21
        self.read(8000, 9000, 6, luid=43)
        self.read(18000, 19000, 60, luid=43)
        self.assertEqual(self.link.traffic['received'], 30)
        self.assertEqual(self.link.traffic['sent'], 40)

    def test_quality_and_ip_reset_keep_traffic_baseline(self):
        self.read(100, 200, 1)
        self.link.reset()
        self.link.adapter['ip'] = '192.0.2.11'
        self.read(110, 220, 2)
        self.assertEqual(self.link.traffic['sent'], 20)

    def test_pause_and_resume_keep_totals_without_paused_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            monitor = n.Monitor(Path(directory)/'prefs.json')
            monitor.links['a'] = self.link
            with patch.object(monitor, 'start'):
                monitor.configure({'enabled': True})
                self.read(100, 200, 1)
                self.read(110, 220, 2)
                monitor.configure({'enabled': False})
                monitor.configure({'enabled': True})
                self.read(900, 1000, 3)
                self.read(910, 1020, 4)
                self.assertEqual(self.link.traffic['received'], 20)
                self.assertEqual(self.link.traffic['sent'], 40)

    def test_failure_is_not_a_connection_failure_and_rebases(self):
        self.link.record(results(), 1000, 1000, 100)
        self.read(100, 200, 1)
        self.read(110, 220, 2)
        def fail(index):
            raise OSError('counter unavailable')
        self.link.read_traffic(fail, 3)
        self.assertEqual(self.link.state, 'healthy')
        self.assertFalse(self.link.traffic['available'])
        self.assertEqual(self.link.traffic['sent'], 20)
        self.read(1000, 2000, 4)
        self.assertEqual(self.link.traffic['sent'], 20)

    @unittest.skipUnless(n.sys.platform == 'win32', 'Windows interface API')
    def test_native_layout_and_api_reuse(self):
        self.assertEqual(n.C.sizeof(n.InterfaceRow), 1352)
        self.assertEqual(n.InterfaceRow.in_octets.offset, 1208)
        self.assertEqual(n.InterfaceRow.out_octets.offset, 1280)
        rows = n.adapters()
        if not rows:
            self.skipTest('No adapter to read')
        first = n.traffic_counters(rows[0]['index'])
        api = n._TRAFFIC_API
        with patch.object(n.C, 'POINTER', wraps=n.C.POINTER) as pointer:
            second = n.traffic_counters(rows[0]['index'])
        pointer.assert_not_called()
        self.assertIs(api, n._TRAFFIC_API)
        self.assertEqual(first[0], second[0])
        self.assertTrue(all(value >= 0 for value in second))


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
        with self.assertRaises(ValueError): self.m.configure({'enabled':'yes'})
        self.assertFalse(self.m.config['enabled'])

    def test_paused_snapshot_does_not_claim_healthy(self):
        self.m._refresh(); self.m.links['a'].state='healthy'
        s=self.m.snapshot()
        self.assertEqual(s['connected'],0)
        self.assertEqual(s['links'][0]['state'],'paused')

    def test_monitor_limit(self):
        self.m.inventory=lambda:[adapter(str(i)) for i in range(12)]
        self.m._refresh()
        self.assertEqual(self.m.snapshot()['selected'],8)


class ConnectionRegressionTests(unittest.TestCase):
    setUp = MonitorTests.setUp
    @unittest.skipUnless(n.sys.platform == 'win32', 'Windows adapter API')
    def test_frequent_inventory_reuses_native_types_and_function(self):
        n.adapters()  # warm any ctypes/runtime caches once
        api=n._ADAPTER_API
        with patch.object(n.C, 'POINTER', wraps=n.C.POINTER) as pointer:
            for _ in range(20): n.adapters()
        self.assertIs(n._ADAPTER_API,api)
        # A bounded set of type identities, without depending on ctypes private caches.
        targets={call.args[0] for call in pointer.call_args_list}
        self.assertLessEqual(len(targets),2)
        self.assertTrue(targets.issubset({n.Adapter,n.U32}))

    def test_old_preferences_cannot_change_interval_or_ping_limit(self):
        self.m.path.write_text(json.dumps({'interval':5,'threshold':900}))
        loaded=n.Monitor(self.m.path)
        self.assertEqual(loaded.config['interval'],1)
        self.assertEqual(loaded.config['threshold'],100)
        self.assertEqual(n.Monitor.validate({'interval':5,'threshold':300}),{'interval':1,'threshold':100})

    def test_quality_events_never_notify_and_do_not_repeat_connection(self):
        self.m.config.update(enabled=True,sound=False)
        self.m._refresh(); link=self.m.links['a']
        calls=[]; self.m.notifier=calls.append
        for i, sample in enumerate((results(),results(120,130),results(250,80),results(),results(101,50))):
            link.record(sample,1000+i,1000+i,100)
            self.m._quality_event(link,sample,1000+i)
            event=self.m._event(link)
            if event:self.m._notify(event,self.m.config)
        self.assertEqual(calls,['Fibra: Conectado'])
        high=[x for x in self.m.events if x['kind']=='quality']
        self.assertEqual(len(high),2)
        self.assertEqual(high[-1]['samples'],2)
        self.assertEqual(high[-1]['peak'],250)
        # Defensive guard even if a caller attempts to send a quality event.
        self.m._notify(high[0],self.m.config)
        self.assertEqual(calls,['Fibra: Conectado'])

    def test_timeouts_are_in_history_without_popup_when_connection_remains(self):
        self.m.config.update(enabled=True,sound=False)
        self.m._refresh();link=self.m.links['a']
        calls=[];self.m.notifier=calls.append
        for i,sample in enumerate((results(),results(None,40),results(None,40),results())):
            link.record(sample,1000+i,1000+i,100)
            self.m._quality_event(link,sample,1000+i)
            event=self.m._event(link)
            if event:self.m._notify(event,self.m.config)
        self.assertEqual(calls,['Fibra: Conectado'])
        failures=[e for e in self.m.events if e['kind']=='probe_failure']
        self.assertEqual(len(failures),1)
        self.assertEqual(failures[0]['timeouts'],2)
        self.assertEqual(failures[0]['samples'],2)
        self.assertFalse(failures[0]['active'])

    def test_exactly_100_ms_is_not_a_high_ping(self):
        self.m.config.update(enabled=True,sound=False)
        self.m._refresh();link=self.m.links['a']
        sample=results(100,100);link.record(sample,1000,1000,100)
        self.m._quality_event(link,sample,1000)
        self.assertFalse(any(e['kind']=='quality' for e in self.m.events))
        self.assertEqual(link.totals['high_readings'],0)
        self.assertTrue(link.snapshot(1000,300)['connected'])

    def test_removal_alert_is_independent_of_blocked_probes(self):
        rows=[adapter()]
        entered=threading.Event();release=threading.Event();notice=threading.Event()
        def inventory():return [dict(x) for x in rows]
        def prober(a,t,timeout):
            entered.set();release.wait(3)
            return {'target':t[0],'ms':30,'error':None}
        calls=[]
        def notifier(msg):
            calls.append(msg)
            if msg.endswith('Desconectado'):notice.set()
        self.m.inventory=inventory;self.m.prober=prober;self.m.notifier=notifier
        self.m.config.update(enabled=True,sound=False)
        try:
            self.m.start()
            self.assertTrue(entered.wait(2))
            rows.clear()  # removed USB adapter; old probe is still blocked
            self.assertTrue(notice.wait(1.5),'physical detection waited for the probe')
            self.assertEqual(self.m.snapshot()['links'][0]['label'],'Desconectado')
            self.assertEqual(self.m.snapshot()['connected'],0)
        finally:
            release.set();self.m.close()
        self.assertEqual(calls,['Fibra: Desconectado'])  # stale success must not resurrect it

    def test_physical_changes_are_not_lost_when_ip_disappears(self):
        self.m.config.update(enabled=True,sound=False)
        self.m._refresh();link=self.m.links['a'];link.record(results(),1000,1000,100)
        link.announced=True
        notices=[];self.m.notifier=notices.append
        self.m.inventory=lambda:[adapter(up=False,ip=None)]
        self.m._refresh();self.m._refresh()
        self.assertEqual(notices,['Fibra: Desconectado'])
        self.assertEqual(link.totals['outages'],1)
        self.assertFalse(link.snapshot(1001,300)['connected'])

    def test_full_afternoon_totals_survive_chart_eviction(self):
        link=n.Link(adapter())
        for i in range(14400):  # four hours, without real waiting or network traffic
            values=results(120,80) if i < 7200 else results(30,40)
            link.record(values,1000+i,1000+i,100)
        s=link.snapshot(15400,300);t=s['totals']
        self.assertEqual(len(link.history),900)
        self.assertEqual(t['readings'],14400)
        self.assertEqual(t['high_readings'],7200)
        self.assertEqual(t['high_episodes'],1)
        self.assertEqual(t['high_seconds'],7200)
        self.assertEqual(t['maximum'],120)
        self.assertEqual(t['average'],75)
        self.assertEqual(t['high_percent'],50)
        self.assertEqual(s['maximum'],30)  # recent chart and all-session summary are distinct

    def test_timeout_failure_and_measurement_error_are_separate_totals(self):
        link=n.Link(adapter())
        for i, values in enumerate((results(None,None),results(None,40),results(None,None,'binding'))):
            link.record(values,1000+i,1000+i,100)
        t=link.snapshot(1003,300)['totals']
        self.assertEqual(t['attempts'],4)
        self.assertEqual(t['failures'],3)
        self.assertEqual(t['timeouts'],3)
        self.assertEqual(t['measurement_errors'],2)
        self.assertEqual(t['failure_percent'],75)

    def test_pauses_and_sleep_not_counted_as_monitored_hours(self):
        link=n.Link(adapter())
        link.record(results(),1000,1000,100)
        link.record(results(),1001,1001,100)
        link.reset()
        link.record(results(),5000,5000,100)
        link.record(results(),5001,5001,100)
        link.record(results(),9000,9000,100)
        self.assertEqual(link.totals['observed_seconds'],2)


if __name__=='__main__': unittest.main()
