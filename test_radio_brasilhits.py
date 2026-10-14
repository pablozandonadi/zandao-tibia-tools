import tempfile
import json
import shutil
import subprocess
from pathlib import Path
import unittest
from unittest.mock import patch
import radio_brasilhits as radio


def payload(**values):
    s = dict(id='pop', slug='brasilhits-pop', label='Pop', qualities=[], streamUrl='')
    s.update(values)
    return {'stations': [s]}


class RadioTests(unittest.TestCase):
    def test_fallback_and_qualities(self):
        stations = radio.normalize_catalog(payload(qualities=[{'id':'baixa','label':'Baixa','url':'https://live.brasilhits.com/listen/brasilhits-pop/lofi'}]))
        self.assertEqual(stations[0]['url'], 'https://live.brasilhits.com/listen/brasilhits-pop/acc')
        self.assertEqual(len(stations[0]['qualities']), 1)

    def test_reject_untrusted_urls_and_ids(self):
        for value in ['http://live.brasilhits.com/x','https://live.brasilhits.com.evil/x','https://user@live.brasilhits.com/x','https://live.brasilhits.com:999/x','https://127.0.0.1/x']:
            self.assertEqual(radio.safe_url(value), '')
        self.assertEqual(radio.normalize_catalog(payload(streamUrl='https://evil.example/x'))[0]['url'], '')
        with self.assertRaises(ValueError): radio.normalize_catalog(payload(id='../auth'))
        with self.assertRaises(ValueError): radio.SafeRedirect().redirect_request(None,None,302,'',{},'https://evil.example/x')

    def test_cache_and_failure_preserves_previous_catalog(self):
        calls = []
        clock = [0]
        def fetch(path):
            calls.append(path)
            if len(calls) > 1: raise TimeoutError()
            return payload()
        client = radio.Client(fetch, lambda: clock[0])
        a = client.catalog(); a['stations'][0]['label'] = 'changed'
        self.assertEqual(client.catalog()['stations'][0]['label'], 'Pop')
        self.assertEqual(len(calls), 1)
        clock[0] = 61
        self.assertTrue(client.catalog()['stale'])

    def test_no_catalog_and_invalid_channel_fail_without_arbitrary_fetch(self):
        client = radio.Client(lambda _: (_ for _ in ()).throw(TimeoutError()))
        self.assertFalse(client.catalog()['ok'])
        self.assertFalse(client.now_playing('../auth/me')['ok'])

    def test_metadata_missing_and_network_failure(self):
        responses = [payload(), {'current': None}, None]
        client = radio.Client(lambda _: responses.pop(0))
        client.catalog()
        self.assertEqual(client.now_playing('pop')['title'], '')
        self.assertFalse(client.now_playing('pop')['ok'])

    def test_preferences_do_not_persist_playing_or_tokens(self):
        self.assertEqual(radio.normalize_preferences({'volume':900,'channel':'../','playing':True,'token':'secret'}), {'channel':'pop','quality':'','volume':100})
        self.assertEqual(radio.normalize_preferences({'volume':'invalid'})['volume'], 50)

    def test_radio_preferences_survive_window_changes(self):
        import web_api
        with tempfile.TemporaryDirectory() as tmp, patch.object(web_api, "PREFS_PATH", str(Path(tmp) / "prefs.json")):
            api = web_api.API.__new__(web_api.API)
            self.assertEqual(api.radio_preferencias()["volume"], 50)
            api.radio_preferencias_salvar({"channel":"rock","volume":30,"quality":"","playing":True})
            web_api.salvar_prefs({"escala":75})
            self.assertEqual(api.radio_preferencias(), {"channel":"rock","quality":"","volume":30})
            saved = json.loads(Path(web_api.PREFS_PATH).read_text(encoding="utf-8"))
            self.assertEqual(saved["escala"],75)
            self.assertNotIn("playing",saved["radio"])

    def test_malformed_catalog(self):
        for data in [None, [], {'stations': []}, {'stations': 'bad'}]:
            with self.assertRaises(ValueError): radio.normalize_catalog(data)

    @unittest.skipUnless(shutil.which("node"), "Node indisponível")
    def test_player_state_machine(self):
        root = Path(__file__).resolve().parent
        subprocess.run([shutil.which("node"), str(root / "test_radio_player.cjs")], cwd=root, check=True, capture_output=True)

    def test_response_size_is_bounded(self):
        class Response:
            url = radio.BASE + '/api/stations'
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def read(self, size): return b'x' * size
        with patch.object(radio, 'build_opener') as opener:
            opener.return_value.open.return_value = Response()
            with self.assertRaises(ValueError): radio.fetch_json('/api/stations')

if __name__ == '__main__': unittest.main()
