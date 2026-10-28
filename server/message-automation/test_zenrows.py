"""ZenRows desligado por padrão; contratos e orçamento testados sem rede nem chave real."""
import io
import tempfile
import traceback
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
from pathlib import Path
from threading import Lock
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs,urlsplit
from cryptography.fernet import Fernet
from automation.domain import UTC
from automation.store import Store
from automation.zenrows import ZenRowsClient,ZenRowsUnavailable,NoRedirect,LIMIT
from automation.xp_sources import guildstats_fallback,XPProvider

NOW=datetime(2026,10,28,12,tzinfo=UTC)
URL='https://guildstats.eu/top-experience?world=Rasteibra&time=0'
HTML=b'<table><tr><th>Rank</th><th>Name</th><th>Level</th><th>Voc</th><th>Exp</th></tr><tr><td>1</td><td>Alpha Knight</td><td>500</td><td>Elite Knight</td><td>123,456</td></tr></table>'


class Response(io.BytesIO):
    def getcode(self):return 200


class Opener:
    def __init__(self,value=HTML,error=None):self.value=value;self.error=error;self.calls=[];self.lock=Lock()
    def open(self,request,timeout):
        with self.lock:self.calls.append((request,timeout))
        if self.error:raise self.error
        return Response(self.value)


class ZenRowsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);folder=Path(self.tmp.name)
        self.store=Store(folder/'state.sqlite',Fernet.generate_key(),open_access=True)
        self.key=folder/'fake-key.txt';self.key.write_text('synthetic-test-key\n',encoding='ascii')
        self.env={'ZENROWS_ENABLED':'1','ZENROWS_API_KEY_FILE':str(self.key)};self.now=NOW;self.opener=Opener()
        self.client=ZenRowsClient(self.store,lambda:self.now,self.env,self.opener)
    def attempts(self):
        with self.store.tx() as db:return db.execute('SELECT coalesce(sum(attempts),0) FROM zenrows_budget').fetchone()[0]
    def url(self,index):return 'https://guildstats.eu/top-experience?world=World'+chr(65+index)+'&time=0'
    def test_valid_zenrows_table_wins_without_direct_request(self):
        direct=lambda *args:(_ for _ in ()).throw(AssertionError('Direct should not run'))
        self.assertEqual(guildstats_fallback('Rasteibra',0,self.client,direct),[('Alpha Knight',500,123456,'Elite Knight')])
        request,timeout=self.opener.calls[0];params=parse_qs(urlsplit(request.full_url).query)
        self.assertEqual(params['url'],[URL]);self.assertEqual(params['mode'],['auto']);self.assertEqual(timeout,20)
        self.assertEqual(self.attempts(),1)
    def test_valid_table_with_cloudflare_helper_script_or_character_name_is_accepted(self):
        self.opener.value=b'<script src="/cdn-cgi/challenge-platform/helper.js">cf-chl-helper</script>'+HTML.replace(b'Alpha Knight',b'Just A Moment')
        rows=guildstats_fallback('Rasteibra',0,self.client,lambda *a:(_ for _ in ()).throw(AssertionError('Direct should not run')))
        self.assertEqual(rows[0][0],'Just A Moment')
    def test_explicit_challenge_title_or_form_uses_direct(self):
        for marker in (b'<title>Just a moment...</title>',b'<form id="challenge-form"></form>'):
            self.now+=timedelta(hours=7);self.opener.value=marker+HTML.replace(b'123,456',b'999')
            rows=guildstats_fallback('Rasteibra',0,self.client,lambda *a:HTML)
            self.assertEqual(rows[0][2],123456)
    def test_remote_error_timeout_or_challenge_uses_direct_parser(self):
        for error,body in ((HTTPError('secret-url',422,'secret-message',{},None),HTML),(TimeoutError('secret-url'),HTML),(None,b'<html>Just a moment cf-chl-secret</html>'),(None,b'{"error":"invalid"}')):
            with self.subTest(error=type(error).__name__,body=body[:5]):
                client=ZenRowsClient(self.store,lambda:self.now,self.env,Opener(body,error));self.now+=timedelta(hours=7)
                calls=[]
                rows=guildstats_fallback('Rasteibra',0,client,lambda url,limit:(calls.append(url) or HTML))
                self.assertEqual(rows[0][2],123456);self.assertEqual(calls,[URL])
    def test_both_failed_still_allows_existing_tibiarise_fallback(self):
        from automation.tibiarise import RiseCache
        from test_tibiarise import pages
        import json
        values=pages();rise=RiseCache(self.store,lambda:NOW,lambda url,limit:json.dumps(values[int(url[-1])-1]).encode())
        rise.request('Antica','Alpha Knight');rise.collect([])
        self.opener.value=b'<html>challenge-platform</html>'
        p=XPProvider(self.store,lambda:NOW,zenrows=self.client,rise=rise,td=lambda *a:(_ for _ in ()).throw(OSError()))
        with patch('automation.xp_sources.public_get',side_effect=OSError('direct unavailable')):summary=p.collect('Antica')
        self.assertEqual(summary['status'],'failed');report=p.report('Antica','Alpha Knight')
        self.assertEqual(report['_source'],'TibiaRise');self.assertEqual(report[30],300)
    def test_default_off_missing_key_and_disallowed_world_do_not_spend(self):
        for env in ({},{'ZENROWS_ENABLED':'1'},{**self.env,'ZENROWS_API_KEY_FILE':str(self.key.parent/'missing')},{**self.env,'ZENROWS_WORLDS':'Antica'}):
            client=ZenRowsClient(self.store,lambda:NOW,env,self.opener)
            self.assertEqual(guildstats_fallback('Rasteibra',0,client,lambda *a:HTML)[0][2],123456)
        self.assertEqual(self.attempts(),0);self.assertEqual(self.opener.calls,[])
    def test_key_and_destination_validation_precede_budget(self):
        for raw in (b'bad\nkey',b'x'*513,b'bad\xff',b''):
            self.key.write_bytes(raw)
            with self.assertRaises(ZenRowsUnavailable):self.client.fetch(URL)
        self.key.write_text('synthetic-test-key')
        for url in ('http://guildstats.eu/top-experience?world=Antica&time=0','https://guildstats.eu.evil/top-experience?world=Antica&time=0','https://guildstats.eu/account','https://guildstats.eu/top-experience?world=Antica&time=1'):
            with self.assertRaises(ZenRowsUnavailable):self.client.fetch(url)
        self.assertEqual(self.attempts(),0)
    def test_per_url_backoff_persists_and_counts_before_request(self):
        self.opener.error=TimeoutError('secret')
        with self.assertRaises(ZenRowsUnavailable):self.client.fetch(URL)
        self.assertEqual(self.attempts(),1)
        restarted=ZenRowsClient(self.store,lambda:self.now,self.env,self.opener)
        with self.assertRaises(ZenRowsUnavailable):restarted.fetch(URL)
        self.assertEqual(len(self.opener.calls),1)
        self.now+=timedelta(hours=6,seconds=1)
        with self.assertRaises(ZenRowsUnavailable):restarted.fetch(URL)
        self.assertEqual(len(self.opener.calls),2)
    def test_day_cap_is_shared_across_restarts_and_rolls_over_in_utc(self):
        self.env['ZENROWS_DAILY_REQUEST_LIMIT']='2'
        self.client.fetch(self.url(0));self.client.fetch(self.url(1))
        restarted=ZenRowsClient(self.store,lambda:self.now,self.env,self.opener)
        with self.assertRaises(ZenRowsUnavailable):restarted.fetch(self.url(2))
        self.assertEqual(self.attempts(),2)
        self.now=datetime(2026,10,28,23,30,tzinfo=timezone(timedelta(hours=-4)))
        restarted.fetch(self.url(2));self.assertEqual(self.attempts(),3)
        with self.store.tx() as db:self.assertEqual(db.execute('SELECT attempts FROM zenrows_budget WHERE day=?',('2026-10-29',)).fetchone()[0],1)
    def test_default_daily_cap_is_six_attempts(self):
        for index in range(6):self.client.fetch(self.url(index))
        with self.assertRaises(ZenRowsUnavailable):self.client.fetch(self.url(6))
        self.assertEqual(self.attempts(),6);self.assertEqual(len(self.opener.calls),6)
    def test_concurrent_clients_cannot_exceed_global_cap(self):
        self.env['ZENROWS_DAILY_REQUEST_LIMIT']='3'
        def run(index):
            client=ZenRowsClient(self.store,lambda:NOW,self.env,self.opener)
            try:client.fetch(self.url(index));return True
            except ZenRowsUnavailable:return False
        with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(run,range(12)))
        self.assertEqual(sum(results),3);self.assertEqual(len(self.opener.calls),3);self.assertEqual(self.attempts(),3)
    def test_auth_credit_and_rate_errors_block_globally_across_midnight(self):
        for code in (401,402,429):
            self.now+=timedelta(days=2);self.now=self.now.replace(hour=23,minute=45)
            self.opener.error=HTTPError('https://api.zenrows.com/?apikey=synthetic-test-key',code,'synthetic-test-key',{},None)
            with self.assertRaises(ZenRowsUnavailable) as error:self.client.fetch(self.url(code%10))
            rendered=''.join(traceback.format_exception(error.exception));self.assertNotIn('synthetic-test-key',rendered);self.assertNotIn('https:',rendered)
            before=len(self.opener.calls);self.now+=timedelta(minutes=30)
            with self.assertRaises(ZenRowsUnavailable):self.client.fetch(self.url(20))
            self.assertEqual(len(self.opener.calls),before)
    def test_redirect_disabled_size_and_deadline_are_bounded(self):
        self.assertIsNone(NoRedirect().redirect_request(None,None,302,'',{},'https://example.com'))
        self.opener.value=b'x'*(LIMIT+1)
        with self.assertRaises(ZenRowsUnavailable):self.client.fetch(URL)
        self.now+=timedelta(hours=7);ticks=iter((0,26));self.client.monotonic=lambda:next(ticks)
        with self.assertRaises(ZenRowsUnavailable):self.client.fetch(URL)
    def test_invalid_or_zero_budget_never_permits_network(self):
        for value in ('0','-1','1001','invalid'):
            self.env['ZENROWS_DAILY_REQUEST_LIMIT']=value
            with self.assertRaises(ZenRowsUnavailable):self.client.fetch(URL)
        self.assertEqual(self.attempts(),0);self.assertEqual(self.opener.calls,[])


if __name__=='__main__':unittest.main()
