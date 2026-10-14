import io
import tempfile
import unittest
import urllib.error
import urllib.parse
from unittest.mock import patch
import guild_stats as gs


def comparison_html(names=('Alpha Knight', 'Beta Mage')):
    return '<table><tr><th></th>' + ''.join('<th>'+n+'</th>' for n in names) + '</tr><tr><td>Level</td>' + ''.join('<td>500</td>' for _ in names) + '</tr><tr><td>Skills</td></tr><tr><td>Attack</td>' + ''.join('<td>120 (Magic)</td>' for _ in names) + '</tr></table>'


class GuildStatsCompareTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        mock = patch.object(gs, 'data_dir', return_value=self.temp.name)
        mock.start()
        self.addCleanup(mock.stop)
        gs._cache.clear()
        gs._failures.clear()

    def test_comparison_uses_official_endpoint_and_canonical_character_names(self):
        with patch.object(gs.urllib.request, 'urlopen', return_value=io.BytesIO(comparison_html().encode())) as fetch:
            result = gs.comparar([' alpha knight ', 'beta mage', '', '', ''])
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(fetch.call_args.args[0].full_url).query, keep_blank_values=True)
        self.assertEqual(query, {'char0':['alpha knight'], 'char1':['beta mage'], 'char2':[''], 'char3':[''], 'char4':['']})
        self.assertEqual(result['characters'], ['Alpha Knight', 'Beta Mage'])
        self.assertEqual(result['tab'], 'compare')
        self.assertEqual(result['tables'][0]['headers'], ['Indicador', 'Alpha Knight', 'Beta Mage'])
        self.assertIn(['Skills'], result['tables'][0]['rows'])
        self.assertFalse(result['stale'])

    def test_accepts_five_characters_and_encodes_query_values(self):
        names = ['Alpha&char4=Other', 'Beta Mage', 'Gamma Knight', 'Delta Druid', 'Epsilon Paladin']
        with patch.object(gs.urllib.request, 'urlopen', return_value=io.BytesIO(comparison_html(names).encode())) as fetch:
            result = gs.comparar(names)
        self.assertNotIn('erro', result)
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(fetch.call_args.args[0].full_url).query)
        self.assertEqual(query['char0'], [names[0]])
        self.assertEqual(query['char4'], [names[4]])

    def test_invalid_lists_and_duplicates_do_not_fetch(self):
        for names in [[], ['Alpha'], ['Alpha','alpha'], ['A','B','C','D','E','F'], 'Alpha, Beta', ['Alpha',None], ['Alpha','B\neta'], ['A'*61,'Beta']]:
            with self.subTest(names=names), patch.object(gs.urllib.request, 'urlopen') as fetch:
                self.assertIn('erro', gs.comparar(names))
                fetch.assert_not_called()

    def test_comparison_discards_unrelated_tables_and_scripts(self):
        html = '<table><tr><th>Menu</th></tr><tr><td>Navigation</td></tr></table><script>secret()</script>' + comparison_html()
        result = gs.parse_comparacao(html, ['Alpha Knight', 'Beta Mage'])
        self.assertEqual(len(result['tables']), 1)
        self.assertNotIn('Navigation', str(result))
        self.assertNotIn('secret', str(result))

    def test_partial_or_wrong_character_table_is_not_accepted(self):
        with patch.object(gs.urllib.request, 'urlopen', return_value=io.BytesIO(comparison_html(('Alpha Knight', 'Someone Else')).encode())):
            result = gs.comparar(['Alpha Knight', 'Beta Mage'])
        self.assertIn('erro', result)
        self.assertEqual(gs._cache, {})

    def test_cached_comparison_survives_restart_and_reports_network_failure(self):
        names = ['Alpha Knight', 'Beta Mage']
        with patch.object(gs.urllib.request, 'urlopen', return_value=io.BytesIO(comparison_html().encode())):
            original = gs.comparar(names)
        gs._cache.clear()
        with patch.object(gs.urllib.request, 'urlopen', side_effect=OSError('offline')):
            result = gs.comparar(names, forcar=True)
        self.assertEqual(result['characters'], original['characters'])
        self.assertTrue(result['stale'])
        self.assertIn('última comparação', result['erro_cache'])

    def test_different_groups_or_order_do_not_share_cache(self):
        with patch.object(gs.urllib.request, 'urlopen', return_value=io.BytesIO(comparison_html().encode())):
            gs.comparar(['Alpha Knight', 'Beta Mage'])
        with patch.object(gs.urllib.request, 'urlopen', side_effect=OSError('offline')):
            self.assertIn('erro', gs.comparar(['Beta Mage', 'Alpha Knight']))
            self.assertIn('erro', gs.comparar(['Alpha Knight', 'Gamma Knight']))

    def test_blocked_comparison_uses_isolated_internal_verification(self):
        error = urllib.error.HTTPError('url', 403, 'Forbidden', {}, io.BytesIO())
        with patch.object(gs.urllib.request, 'urlopen', side_effect=error), patch.object(gs, '_browser_html', return_value=comparison_html()) as browser:
            result = gs.comparar(['Alpha Knight', 'Beta Mage'], forcar=True, interagir=True)
        self.assertNotIn('erro', result)
        browser.assert_called_once_with(gs.url_comparacao(['Alpha Knight', 'Beta Mage']), 'compare', True)

    def test_cancelled_verification_is_reported_without_caching_bad_data(self):
        error = urllib.error.HTTPError('url', 403, 'Forbidden', {}, io.BytesIO())
        with patch.object(gs.urllib.request, 'urlopen', side_effect=error), patch.object(gs, '_browser_html', side_effect=gs.VerificationRequired('Verificação cancelada.')):
            result = gs.comparar(['Alpha Knight', 'Beta Mage'], forcar=True, interagir=True)
        self.assertTrue(result['verification_required'])
        self.assertIn('cancelada', result['erro'])
        self.assertEqual(gs._cache, {})


if __name__ == '__main__':
    unittest.main()
