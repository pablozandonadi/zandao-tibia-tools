import types
import tempfile
import io
import urllib.error
import unittest
from unittest.mock import patch
import guild_stats as gs

class GuildStatsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        paths = patch.object(gs, 'data_dir', return_value=self.temp.name)
        paths.start()
        self.addCleanup(paths.stop)
        gs._cache.clear()
        gs._failures.clear()

    def test_cache_survives_restart_and_network_failure(self):
        key = ('zandao', 'experience')
        data = {'name':'Zandao', 'tab':'experience', 'days':[{'date':'2026-10-10','gain':42}], 'fetched':'2026-10-11'}
        gs._save_cache(key, data)
        gs._cache.clear()
        with patch.object(gs.urllib.request, 'urlopen', side_effect=OSError('offline')):
            result = gs.buscar('Zandao', forcar=True)
        self.assertTrue(result['stale'])
        self.assertEqual(result['days'][0]['gain'], 42)
        self.assertEqual(result['fetched'], '2026-10-11')

    def test_blocked_query_uses_internal_session(self):
        error = urllib.error.HTTPError('url',403,'Forbidden',{},io.BytesIO(b'Just a moment'))
        html = '<table><tr><td>2026-10-10</td><td>42</td><td>1</td><td>500</td><td>1000</td></tr></table>'
        with patch.object(gs.urllib.request,'urlopen',side_effect=error), patch.object(gs,'_browser_html',return_value=html) as browser:
            result = gs.buscar('Zandao', forcar=True, interagir=True)
        self.assertEqual(result['days'][0]['gain'],42)
        browser.assert_called_once_with('https://guildstats.eu/include/character/tab.php?nick=Zandao&tab=experience','experience',True)
        self.assertIsNotNone(gs._read_cache(('zandao','experience')))

    def test_cancel_preserves_cache_and_reports_verification(self):
        gs._save_cache(('zandao','experience'), {'name':'Zandao','days':[]})
        error = urllib.error.HTTPError('url',403,'Forbidden',{},io.BytesIO())
        with patch.object(gs.urllib.request,'urlopen',side_effect=error), patch.object(gs,'_browser_html',side_effect=gs.VerificationRequired('Verificação cancelada.')):
            result = gs.buscar('Zandao',forcar=True,interagir=True)
        self.assertTrue(result['stale'])
        self.assertTrue(result['verification_required'])
        self.assertIn('cancelada',result['erro_cache'])

    def test_hover_does_not_create_window_and_backs_off(self):
        error = urllib.error.HTTPError('url',403,'Forbidden',{},io.BytesIO())
        with patch.object(gs,'_browser',None), patch.object(gs.urllib.request,'urlopen',side_effect=error) as fetch:
            self.assertTrue(gs.buscar('Zandao')['verification_required'])
            self.assertTrue(gs.buscar('Zandao')['verification_required'])
            self.assertEqual(fetch.call_count,1)

    def test_internal_window_has_no_privileged_api_and_hides_after_success(self):
        from unittest.mock import MagicMock
        html = '<table><tr><td>2026-10-10</td><td>42</td><td>1</td><td>500</td><td>1000</td></tr></table>'
        window = MagicMock()
        window.get_current_url.return_value = 'https://guildstats.eu/include/character/tab.php?nick=Zandao&tab=experience'
        window.evaluate_js.return_value = html
        create = MagicMock(return_value=window)
        with patch.object(gs,'_browser',None), patch.dict('sys.modules',{'webview':types.SimpleNamespace(create_window=create)}):
            result = gs._browser_html(window.get_current_url.return_value,'experience',True)
        self.assertEqual(result,html)
        self.assertIsNone(create.call_args.kwargs['js_api'])
        window.hide.assert_called_once()

    def test_foreign_navigation_is_not_read_and_times_out(self):
        from unittest.mock import MagicMock
        window = MagicMock()
        window.get_current_url.return_value = 'https://other.example/'
        with patch.object(gs,'_browser',window), patch.object(gs.time,'monotonic',side_effect=[0,0,13]), patch.object(gs.time,'sleep'):
            with self.assertRaises(gs.VerificationRequired):
                gs._browser_html('https://guildstats.eu/character/Zandao','character')
        window.evaluate_js.assert_not_called()

    def test_corrupt_cache_is_ignored(self):
        path = gs._cache_file(('zandao','experience'))
        path.parent.mkdir()
        path.write_text('{broken',encoding='utf-8')
        self.assertIsNone(gs._read_cache(('zandao','experience')))

    def test_daily_dates_signed_gains_and_month_coverage(self):
        html='''<h2>Update: 2026-10-11 11:21 CEST</h2><script>alert('never')</script><table><tr><th>When</th><th>Exp change</th></tr>
        <tr><td><span>2026-10-10</span><span class="md:hidden">10-10</span></td><td>+16,173,185</td><td>131</td><td>501</td><td>2,080,478,348</td><td>5h</td></tr>
        <tr><td>2026-10-09</td><td>-9,584,799</td><td>132</td><td>500</td><td>2,064,305,163</td><td>6h</td></tr>
        <tr><td>2026-10-08</td><td>—</td><td>132</td><td>500</td><td>2,064,305,163</td><td>6h</td></tr></table>'''
        r=gs.parse(html,'experience')
        self.assertEqual(r['days'][0]['date'],'2026-10-10')
        self.assertEqual(r['days'][1]['gain'],-9584799)
        self.assertIsNone(r['days'][2]['gain'])
        self.assertEqual(r['months']['2026-10'],{'gain':6588386,'days':3,'missing':1})
        self.assertEqual(r['updated'],'2026-10-11 11:21 CEST')
    def test_hidden_tooltip_and_mobile_duplicate_removed(self):
        r=gs.parse('<table><tr><th>When</th></tr><tr><td>10-10-2026<span class="md:hidden">10-10</span><div x-show="open">tip</div></td></tr></table>','deaths')
        self.assertEqual(r['tables'][0]['rows'],[['10-10-2026']])
    def test_browser_verification_reported(self):
        r=gs.parse('<div id="charHistoryTurnstile"></div>','history')
        self.assertIn('verificação',r['notice'])
    def test_invalid_tab_does_not_fetch(self):
        with patch.object(gs.urllib.request,'urlopen') as fetch:
            self.assertIn('erro',gs.buscar('Zandao','../other'))
            fetch.assert_not_called()
    def test_cached_result_on_network_failure_is_marked_stale(self):
        with patch.dict(gs._cache,{('zandao','experience'):(0,{'name':'Zandao','days':[]})},clear=True), patch.object(gs.urllib.request,'urlopen',side_effect=OSError()):
            self.assertTrue(gs.buscar('Zandao',forcar=True)['stale'])
    def test_profile_comes_from_guildstats_markup(self):
        r=gs.profile('<span>Level 502</span><!-- Tab: Character --><div>Vocation: Master Sorcerer World: Rasteibra Tibian age: 374 years Tibia Completed 6%</div><!-- Tab: History -->')
        self.assertEqual(r['Level'],'502')
        self.assertEqual(r['World'],'Rasteibra')
        self.assertEqual(r['Tibian age'],'374 years')

if __name__=='__main__': unittest.main()
