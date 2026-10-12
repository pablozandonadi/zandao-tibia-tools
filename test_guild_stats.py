import unittest
from unittest.mock import patch
import guild_stats as gs

class GuildStatsTests(unittest.TestCase):
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
