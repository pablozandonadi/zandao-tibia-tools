"""Fontes públicas injetadas: nenhum teste conecta WhatsApp ou rede externa."""
import hashlib
import io
import json
import tempfile
import unittest
from datetime import datetime,timedelta
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from cryptography.fernet import Fernet
from automation.domain import UTC,reference_day
from automation.store import Store
from automation.xp_sources import XPProvider,tibiadata,OWNER
from automation.botcmds import Bot
from automation.commands import Commander
from automation.transport import FakeTransport

NOW=datetime(2026,10,27,12,tzinfo=UTC)
ROWS=[('Alpha Knight',500,1000,'Elite Knight'),('Beta Druid',600,2000,'Elder Druid')]

def unavailable(*args):raise HTTPError('https://guildstats.eu/',403,'Forbidden',{},None)

class XPTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.store=Store(Path(self.tmp.name)/'xp.sqlite',Fernet.generate_key(),open_access=True)
  self.now=NOW;self.provider=XPProvider(self.store,lambda:self.now,unavailable,lambda *a:(_ for _ in ()).throw(OSError('offline')))
 def seed(self,day,rows=ROWS,at=None):
  at=at or datetime.fromisoformat(day+'T12:00:00+00:00');fingerprint=hashlib.sha256(json.dumps(rows).encode()).hexdigest()
  with self.store.tx() as db:db.execute('INSERT INTO xp_totals VALUES(?,?,?,?,?,?)',('Antica',day,at.timestamp(),at.timestamp(),fingerprint,self.store.pack(OWNER,'td:antica:'+day,rows)))
 def test_guildstats_primary_persistent_stale_cache_keeps_original_date_and_backoff(self):
  calls=[]
  self.provider.gs=lambda world,window:(calls.append(window) or ROWS)
  self.provider.collect('Antica');original=self.provider.cache('Antica',30)['observed']
  self.provider.gs=unavailable;self.now+=timedelta(hours=1);self.provider.collect('Antica')
  cached=self.provider.cache('Antica',30)
  self.assertEqual(cached['observed'],original);self.assertEqual(cached['status'],'blocked');self.assertEqual(cached['rows'][0][2],1000)
  self.assertGreater(cached['retry_after'],self.now.timestamp()+3600)
  report=self.provider.report('Antica','Alpha Knight');self.assertEqual(report[30],1000);self.assertFalse(report['_projection']);self.assertIn('antigo',report['_meta'][30]['source'])
  self.assertEqual(XPProvider(self.store,lambda:self.now).cache('Antica',30)['observed'],original)
  self.assertEqual(self.provider.ranking_for_extra('Antica')['rows'],None,'Bom dia não trata o cache antigo como XP atual')
 def test_blocked_source_is_not_a_character_missing_from_the_ranking(self):
  self.provider.collect('Antica')
  report=self.provider.report('Antica','Alpha Knight')
  self.assertTrue(all(report[window] is None for window in (0,7,30)))
  self.assertEqual(report['_notes'],['Histórico insuficiente para calcular os períodos sem valor.'])
  self.assertEqual(self.provider.cache('Antica',0)['status'],'blocked')
  b=Bot(sheet=lambda n:{'name':n,'world':'Antica','level':500,'vocation':'Knight'},experience=self.provider.report)
  text=b.handle('!evolucao Alpha Knight','Antica',NOW.date())
  self.assertEqual(text.count('Histórico insuficiente para calcular os períodos sem valor.'),1)
  for technical in ('acesso bloqueado','Cloudflare','HTTP','complemento sem histórico','fora do top 500','código de recuperação'):
   self.assertNotIn(technical,text)
  self.assertIn('!help',b.handle('!help'));self.assertIn('—',text)
 def test_historical_guildstats_rows_are_preserved_and_visible_without_a_month(self):
  with self.store.tx() as db:db.execute('INSERT INTO rank_history VALUES(?,?,?,?,?)',('Antica','2026-10-25','Alpha Knight',499,55))
  report=self.provider.report('Antica','Alpha Knight');self.assertIsNone(report[0]);self.assertIsNone(report[30]);self.assertEqual(report['_daily'][0],('2026-10-25',499,55,'GuildStats — histórico salvo'))
  b=Bot(sheet=lambda n:{'name':n,'world':'Antica','level':500,'vocation':'Knight'},experience=self.provider.report)
  text=b.handle('!xptop Alpha Knight','Antica',NOW.date());self.assertIn('25/10',text);self.assertIn('GS',text)
 def test_adjacent_total_samples_negative_and_zero_are_real_differences_not_missing(self):
  self.seed('2026-10-26');self.seed('2026-10-27',[('Alpha Knight',499,900,'Elite Knight'),('Beta Druid',600,2000,'Elder Druid')])
  report=self.provider.report('Antica','Alpha Knight');self.assertEqual(report[0],-100);self.assertIn('TibiaData',report['_meta'][0]['source']);self.assertIsNone(report[7]);self.assertIsNone(report[30])
  self.assertEqual(self.provider.report('Antica','Beta Druid')[0],0)
  extra=self.provider.ranking_for_extra('Antica');self.assertIn('entre coletas',extra['source']);self.assertEqual(extra['rows'][0][2],-100)
 def test_missing_days_and_missing_people_never_turn_into_zero_or_multiday_daily_gain(self):
  self.seed('2026-10-25');self.seed('2026-10-27',[ROWS[1]])
  report=self.provider.report('Antica','Alpha Knight');self.assertIsNone(report[0]);self.assertEqual(report['_daily'],[])
  self.assertIsNone(self.provider.report('Antica','Beta Druid')[0])
  self.assertIsNone(self.provider.ranking_for_extra('Antica')['rows'])
 def test_measured_interval_is_not_yesterday_and_custom_legacy_variable_is_empty(self):
  self.seed('2026-10-26',at=datetime(2026,10,26,10,tzinfo=UTC))
  self.seed('2026-10-27',[('Alpha Knight',501,1100,'Elite Knight'),ROWS[1]],at=datetime(2026,10,27,11,tzinfo=UTC))
  report=self.provider.report('Antica','Alpha Knight')
  self.assertEqual(report['_daily'][0][0],'2026-10-27');self.assertEqual(report['_rates'][0],96)
  b=Bot(sheet=lambda n:{'name':n,'world':'Antica','level':500,'vocation':'Knight'},experience=self.provider.report)
  for command in ('!evolucao Alpha Knight','!xptop Alpha Knight'):
   text=b.handle(command,'Antica',NOW.date());self.assertIn('Entre coletas',text);self.assertIn('26/10 10:00 → 27/10 11:00 UTC',text);self.assertNotIn('Ontem: *0,00kk*',text)
  b.settings=lambda:{'xptop':{'text':'Ontem: {xp_ontem}'}}
  text=b.handle('!xptop Alpha Knight','Antica',NOW.date());self.assertIn('Ontem: —',text);self.assertIn('TibiaData — variação',text)
 def test_complete_windows_require_every_baseline_and_preserve_input_times(self):
  for i in range(31):
   day=(NOW-timedelta(days=i)).date().isoformat();self.seed(day,[('Alpha Knight',500,10000-i*10,'Elite Knight')])
  report=self.provider.report('Antica','Alpha Knight');self.assertEqual(report[7],70);self.assertEqual(report[30],300);self.assertTrue(report['_projection']);self.assertEqual(report['_rates'][30],10)
  with self.store.tx() as db:db.execute("DELETE FROM xp_totals WHERE day='2026-10-12'")
  report=self.provider.report('Antica','Alpha Knight');self.assertIsNone(report[30]);self.assertEqual(report[7],70)
 def test_collector_does_not_publish_an_old_or_repeated_upstream_publication(self):
  def td(world,now):return {'rows':ROWS,'upstream':now.timestamp(),'fingerprint':'first','day':reference_day(now)}
  self.provider.td=td;summary=self.provider.collect('Antica');self.assertEqual(summary['status'],'partial')
  self.now+=timedelta(days=1);self.provider.collect('Antica')
  with self.store.tx() as db:self.assertEqual(db.execute('SELECT count(*) FROM xp_totals').fetchone()[0],1)
  self.provider.td=lambda world,now:{'rows':ROWS,'upstream':(now-timedelta(days=1)).timestamp(),'fingerprint':'different','day':reference_day(now)}
  self.now+=timedelta(minutes=16);self.provider.collect('Antica')
  with self.store.tx() as db:self.assertEqual(db.execute('SELECT count(*) FROM xp_totals').fetchone()[0],1)
 def test_fast_command_maintenance_never_fetches_rankings_or_totals(self):
  conn=self.store.create('owner','connection',{'riskAccepted':True},'active');transport=FakeTransport();transport.pair(conn)
  dest=self.store.create('owner','destination',{'connection':conn,'group':'fake-group'},'active')
  self.store.create('owner','botgroup',{'connection':conn,'destination':dest,'world':'Antica','cooldown':30},'active')
  with patch('automation.xp_sources.public_get',side_effect=AssertionError('HTTP in fast maintenance')) as network:
   commander=Commander(self.store,transport,clock=lambda:NOW);commander.maintain(NOW)
   self.assertEqual(commander.bot.handle('!help'),Bot().handle('!help'));network.assert_not_called()
 def test_collector_entrypoint_does_not_run_whatsapp_worker_or_inbox(self):
  import automation.__main__ as cli
  with self.store.tx() as db:db.execute("INSERT INTO rank_meta VALUES('Antica','')")
  with patch('sys.argv',['automation','collect-xp']),patch.object(cli,'state_store',return_value=self.store),patch.object(cli,'components',side_effect=AssertionError('WhatsApp configuration')),patch.object(cli.XPProvider,'maintain',return_value={'status':'skipped','attempted':False}) as collect,patch.object(cli.Worker,'tick',side_effect=AssertionError('worker')):
   cli.main();self.assertEqual(collect.call_args.args[0],['Antica'])
 def test_collector_works_without_whatsapp_env_and_reports_failed_sources_safely(self):
  import automation.__main__ as cli
  key=Path(self.tmp.name)/'data.key';key.write_bytes(Fernet.generate_key())
  env={'AUTOMATION_STATE_DIR':str(Path(self.tmp.name)/'collector-state'),'AUTOMATION_KEY_FILE':str(key),'AUTOMATION_TRANSPORT':'bridge','AUTOMATION_BRIDGE_TOKEN_FILE':'missing-token-file'}
  import tibia_info
  with patch.object(tibia_info,'CACHE_PATH',tibia_info.CACHE_PATH),patch.dict('os.environ',env,clear=True),patch('sys.argv',['automation','collect-xp']),patch.object(cli,'components',side_effect=AssertionError('transport')),patch('sys.stdout',new_callable=io.StringIO) as output:
   cli.main();self.assertEqual(json.loads(output.getvalue())['status'],'skipped')
  summary=self.provider.collect('Antica');self.assertEqual(summary['status'],'failed');self.assertEqual(summary['guildstats'][0]['http_status'],403)
  text=json.dumps(summary);self.assertNotIn('https:',text);self.assertNotIn('Forbidden',text);self.assertIn('HTTPError',text)
  with patch('sys.argv',['automation','collect-xp']),patch.object(cli,'state_store',return_value=self.store),patch.object(cli.XPProvider,'maintain',return_value=summary),patch('sys.stdout',new_callable=io.StringIO):
   with self.assertRaises(SystemExit) as error:cli.main()
  self.assertEqual(error.exception.code,1)
  self.now+=timedelta(minutes=16)
  self.provider.td=lambda world,now:{'rows':ROWS,'day':reference_day(now),'upstream':now.timestamp(),'fingerprint':'fresh'}
  summary=self.provider.collect('Antica');self.assertEqual(summary['status'],'ok','GuildStats em backoff não gera nova tentativa; TibiaData foi bem-sucedida')

class MorningMessageTests(unittest.TestCase):
 setUp=XPTests.setUp
 seed=XPTests.seed
 def source_provider(self):
  from mensagem_automatica_report import PublicProvider
  class Sources(PublicProvider):
   def summary(self,c,now):
    base={'consulta':now.timestamp(),'dia':reference_day(now)}
    return {'calendario':{**base,'estado':'disponivel','eventos':[]},'yasir':{**base,'estado':'ausente','mudancas':['Fixture change']},'boostados':{**base,'boss':{'nome':'Boss fixture'},'criatura':{'nome':'Rat fixture'}},'dream_court':{**base,'estado':'previsto','nome':'Dream fixture'},'killstatistics':{**base,'estado':'disponivel','bosses':[{'nome':'Dream fixture','last_day_killed':1}]}}
  return Sources(self.provider)
 def fixture_response(self,key,endpoint,*args,**kwargs):
  if endpoint.startswith('/character/'):
   data={'character':{'character':{'name':'Alpha Knight','world':'Antica','level':500,'vocation':'Knight','guild':{'name':'Guild Fixture'}},'deaths':[]}}
  elif endpoint.startswith('/guild/'):
   data={'guild':{'name':'Guild Fixture','world':'Antica','members':[{'name':'Alpha Knight','status':'online','level':500,'vocation':'Knight','joined':'2026-10-01'}]}}
  elif endpoint.startswith('/news/'):
   data={'news':[{'id':1,'news':'Fixture news','date':'2026-10-27','category':'community'}]}
  else:data={'killstatistics':{'entries':[{'race':'Rat','last_day_killed':1}]}}
  return {'dados':data,'consulta':NOW.timestamp(),'velho':False}
 def config(self):
  from mensagem_automatica_core import BLOCKS
  return {'personagem':'Alpha Knight','mundo':'Antica','timezone':'UTC','blocks':dict.fromkeys(BLOCKS,True),'extras':dict.fromkeys(('noticias','kill','exp_mundo','guild','exp_guild','transfer'),True),'args':{'guild':'Guild Fixture','exp_guild':'Guild Fixture'}}
 def test_six_extras_with_three_guildstats_failures_do_not_cancel_valid_core(self):
  from mensagem_automatica_report import generate
  import zandaobot,zandaobot_sources
  self.provider.collect('Antica')
  with patch.object(zandaobot,'_consultar',side_effect=self.fixture_response),patch.object(zandaobot_sources,'get_text',side_effect=unavailable):
   output=generate(self.config(),NOW,self.source_provider())
  self.assertIn('Bom dia',output['text']);self.assertIn('Boss fixture',output['text']);self.assertIn('Fixture news',output['text']);self.assertIn('Guild Fixture',output['text']);self.assertIn('Transferências: dados indisponíveis',output['text']);self.assertIn('isso não significa ausência de eventos ou XP zero',output['text'])
  self.assertEqual(output['reference_date'],'2026-10-27');self.assertFalse(any(s['source']=='GuildStats' for s in output['sources']))
 def test_core_source_unavailable_still_fails_closed(self):
  from mensagem_automatica_report import generate
  from mensagem_automatica_core import Invalid
  provider=self.source_provider();base=provider.summary
  def broken(c,now):
   result=base(c,now);result['boostados']['dia']='2000-01-01';return result
  provider.summary=broken
  with self.assertRaises(Invalid):generate(self.config(),NOW,provider)
 def test_tibiadata_extra_has_actual_input_periods_and_does_not_claim_guildstats(self):
  from mensagem_automatica_report import generate
  import zandaobot
  self.seed('2026-10-26');self.seed('2026-10-27',[('Alpha Knight',501,1100,'Elite Knight'),ROWS[1]])
  config={'personagem':'Alpha Knight','mundo':'Antica','blocks':{'mundo':True},'extras':{'exp_mundo':True,'exp_guild':True},'args':{'exp_guild':'Guild Fixture'}}
  with patch.object(zandaobot,'_consultar',side_effect=self.fixture_response):output=generate(config,NOW,self.source_provider())
  self.assertIn('variação de XP entre coletas',output['text']);self.assertIn('26/10 12:00 UTC a 27/10 12:00 UTC',output['text'])
  self.assertNotIn('XP de ontem',output['text']);derived=[s for s in output['sources'] if s['source']=='local-xp-difference'];self.assertEqual(len(derived),2)
  self.assertEqual(derived[0]['inputs'][0]['period_start'],datetime(2026,10,26,12,tzinfo=UTC).timestamp())
 def test_tibiarise_extra_keeps_its_publication_period_and_is_not_guildstats(self):
  from mensagem_automatica_report import generate
  from test_tibiarise import rank
  import zandaobot
  self.provider.rise.get=lambda url,limit:json.dumps(rank({'daily':0,'weekly':7,'monthly':30}[url.split('/')[-1]])).encode()
  self.provider.rise.collect(['Antica'])
  config={'personagem':'Alpha Knight','mundo':'Antica','blocks':{'mundo':True},'extras':{'exp_mundo':True,'exp_guild':True},'args':{'exp_guild':'Guild Fixture'}}
  with patch.object(zandaobot,'_consultar',side_effect=self.fixture_response):output=generate(config,NOW,self.source_provider())
  self.assertIn('TibiaRise',output['text']);self.assertNotIn('XP de ontem',output['text'])
  self.assertFalse(any(s['source']=='GuildStats' for s in output['sources']))
  derived=[s for s in output['sources'] if s['source']=='local-tibiarise-ranking'];self.assertEqual(len(derived),2)
  self.assertEqual(derived[0]['inputs'][0]['published_at'],(NOW-timedelta(hours=5)).timestamp())

class PaginationTests(unittest.TestCase):
 def fixture(self,records=1000,mutate=None):
  calls=[]
  def get(url,limit):
   number=int(url.rsplit('/',1)[1]);calls.append(number);pages=(records+49)//50
   rows=[{'rank':i,'name':'Player '+chr(65+(i//676)%26)+chr(65+(i//26)%26)+chr(65+i%26),'world':'Antica','vocation':'Knight','level':500+i,'value':100000+i} for i in range((number-1)*50+1,min(number*50,records)+1)]
   data={'highscores':{'world':'Antica','category':'experience','vocation':'all','highscore_page':{'current_page':number,'total_pages':pages,'total_records':records},'highscore_list':rows},'information':{'api':{'version':4},'status':{'http_code':200},'timestamp':NOW.isoformat()}}
   if mutate:mutate(data,number)
   return json.dumps(data).encode()
  return get,calls
 def test_all_twenty_pages_are_validated_before_accepting_a_world(self):
  get,calls=self.fixture();result=tibiadata('Antica',NOW,get)
  self.assertEqual(len(result['rows']),1000);self.assertEqual(sorted(calls),list(range(1,21)));self.assertEqual(result['day'],'2026-10-27')
 def test_partial_duplicate_world_category_timestamp_and_total_are_rejected(self):
  def missing(d,n):
   if n==2:d['highscores']['highscore_list'].pop()
  def duplicate(d,n):
   if n==2:d['highscores']['highscore_list'][0]['name']='Player AAB'
  def wrong_world(d,n):d['highscores']['world']='Otherworld'
  def wrong_category(d,n):d['highscores']['category']='magiclevel'
  def old(d,n):d['information']['timestamp']=(NOW-timedelta(hours=2)).isoformat()
  def bad_total(d,n):d['highscores']['highscore_page']['total_records']=1001
  def negative(d,n):d['highscores']['highscore_list'][0]['value']=-1
  for mutate in (missing,duplicate,wrong_world,wrong_category,old,bad_total,negative):
   with self.subTest(mutate=mutate.__name__):
    get,_=self.fixture(100,mutate)
    with self.assertRaises(ValueError):tibiadata('Antica',NOW,get)

if __name__=='__main__':unittest.main()
