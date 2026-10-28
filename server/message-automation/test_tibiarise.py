"""Contratos sintéticos: nenhuma rede, sessão ou mensagem real."""
import json
import tempfile
import unittest
from datetime import datetime,timedelta
from pathlib import Path
from unittest.mock import patch
from cryptography.fernet import Fernet
from automation.domain import UTC
from automation.store import Store
from automation.tibiarise import RiseCache,character,ranking,REFRESH
from automation.xp_sources import XPProvider
from automation.botcmds import Bot

NOW=datetime(2026,10,27,12,tzinfo=UTC)

def pages(count=43):
 rows=[{'date':(NOW-timedelta(hours=5,days=i)).isoformat(),'level':500,'experience':10,'totalExperience':10000-i*10} for i in range(count)]
 def page(number):
  return {'character':{'name':'Alpha Knight','world':'Antica'},'experienceTable':rows[(number-1)*30:number*30],'pagination':{'page':number,'pageSize':30,'total':count,'hasMore':number*30<count}}
 return [page(1),page(2)]

def rank(window=0):
 return {'world':'Antica','period':{'type':{0:'daily',7:'weekly',30:'monthly'}[window],'startDate':(NOW-timedelta(hours=4,days=window or 1)).isoformat(),'endDate':(NOW-timedelta(hours=4)).isoformat()},'updatedAt':(NOW-timedelta(hours=5)).isoformat(),'topGainers':[{'characterName':'Alpha Knight','world':'Antica','vocation':'Knight','level':500,'experienceGained':-25}]}

class RiseTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.store=Store(Path(self.tmp.name)/'state.sqlite',Fernet.generate_key(),open_access=True)
  self.now=NOW;self.values=pages();self.calls=[]
  def get(url,limit):
   self.calls.append(url)
   return json.dumps(self.values[int(url[-1])-1] if '/character/' in url else rank({'daily':0,'weekly':7,'monthly':30}[url.split('/')[-1]])).encode()
  self.get=get;self.rise=RiseCache(self.store,lambda:self.now,self.get)
  self.provider=XPProvider(self.store,lambda:self.now,rise=self.rise)
 def seed(self):
  self.rise.request('Antica','Alpha Knight');self.rise.collect([])
 def test_two_pages_and_complete_intervals_preserve_provenance(self):
  self.seed();r=self.provider.report('Antica','Alpha Knight')
  self.assertEqual((r[0],r[7],r[30]),(10,70,300));self.assertTrue(r['_projection']);self.assertEqual(r['_rates'][30],10)
  self.assertEqual(len(self.calls),2);self.assertEqual(r['_meta'][30]['source'],'TibiaRise — variação entre registros')
  self.assertEqual(len(r['_daily']),42);self.assertEqual(r['_daily_periods'][r['_daily'][0][0]]['end'],(NOW-timedelta(hours=5)).timestamp())
  with self.store.tx() as db:
   self.assertEqual(db.execute('SELECT count(*) FROM rank_history').fetchone()[0],0)
   body=bytes(db.execute('SELECT body FROM xp_rise_cache').fetchone()[0]);self.assertNotIn(b'Alpha Knight',body)
  again=RiseCache(self.store,lambda:self.now,self.get);self.assertEqual(again.read('Antica','ALPHA KNIGHT')['observed'],NOW.timestamp())
 def test_first_read_queues_without_http_then_collector_updates(self):
  with patch.object(self.rise,'get',side_effect=AssertionError('HTTP in report')):
   r=self.provider.report('Antica','Alpha Knight');self.assertIsNone(r[0])
   self.assertEqual(self.rise.read('Antica','Alpha Knight')['status'],'waiting')
  self.rise.collect([]);self.assertEqual(self.provider.report('Antica','Alpha Knight')[0],10)
  self.rise.collect([]);self.assertEqual(len(self.calls),2,'Success backoff is persistent')
 def test_negative_and_zero_are_not_missing(self):
  self.values[0]['experienceTable'][0]['experience']=-10;self.values[0]['experienceTable'][0]['totalExperience']=9980
  self.seed();self.assertEqual(self.provider.report('Antica','Alpha Knight')[0],-10)
  self.values[0]['experienceTable'][0]['experience']=0;self.values[0]['experienceTable'][0]['totalExperience']=9990
  self.now+=timedelta(hours=7);self.rise.collect([]);self.assertEqual(self.provider.report('Antica','Alpha Knight')[0],0)
 def test_gap_does_not_become_zero_or_a_complete_window(self):
  self.values[0]['experienceTable'][10]['date']=(NOW-timedelta(hours=5,days=10,seconds=1)).isoformat()
  self.values[0]['experienceTable'].pop(10);self.values[0]['pagination'].update(hasMore=False,total=29)
  self.seed();r=self.provider.report('Antica','Alpha Knight');self.assertEqual(r[7],70);self.assertIsNone(r[30]);self.assertFalse(r['_projection'])
 def test_invalid_contract_never_replaces_good_cache(self):
  self.seed();original=self.rise.read('Antica','Alpha Knight')['observed'];self.now+=timedelta(hours=7)
  self.values[1]['character']['name']='Other Knight';summary=self.rise.collect([])
  self.assertEqual(summary[0]['status'],'unavailable');self.assertEqual(self.rise.read('Antica','Alpha Knight')['observed'],original)
  self.assertFalse(self.provider.report('Antica','Alpha Knight')['_projection'])
 def test_duplicate_bool_mismatched_total_and_world_are_rejected(self):
  for change in ('duplicate','bool','total','world','pagination'):
   self.values=pages()
   if change=='duplicate':self.values[0]['experienceTable'][1]['date']=self.values[0]['experienceTable'][0]['date']
   if change=='bool':self.values[0]['experienceTable'][0]['experience']=True
   if change=='total':self.values[0]['experienceTable'][0]['totalExperience']+=1
   if change=='world':self.values[0]['character']['world']='Bona'
   if change=='pagination':self.values[1]['pagination']['total']=44
   with self.subTest(change=change),self.assertRaises(ValueError):character('Antica','Alpha Knight',NOW,self.get)
 def test_old_history_is_dated_without_projection(self):
  self.seed();self.now+=timedelta(days=3)
  r=self.provider.report('Antica','Alpha Knight');self.assertEqual(r[30],300);self.assertFalse(r['_projection'])
  b=Bot(sheet=lambda name:{'name':name,'world':'Antica','vocation':'Knight','level':500},experience=self.provider.report)
  text=b.handle('!evolucao Alpha Knight','Antica',self.now.date());self.assertIn('registro antigo',text);self.assertIn('TibiaRise',text)
 def test_custom_template_cannot_relabel_rise_as_yesterday_guildstats(self):
  self.seed();b=Bot(sheet=lambda name:{'name':name,'world':'Antica','vocation':'Knight','level':500},experience=self.provider.report,settings=lambda:{'xptop':{'text':'Ontem: {xp_ontem}'}})
  text=b.handle('!xptop Alpha Knight','Antica',NOW.date());self.assertIn('Ontem: —',text);self.assertIn('Último intervalo',text);self.assertIn('TibiaRise',text)
 def test_ranking_contract_and_future_period_rejected(self):
  data=rank();value=ranking('Antica',0,NOW,lambda *a:json.dumps(data));self.assertEqual(value['rows'][0][2],-25)
  data['period']['endDate']=(NOW+timedelta(hours=2)).isoformat()
  with self.assertRaises(ValueError):ranking('Antica',0,NOW,lambda *a:json.dumps(data))
 def test_ambiguous_names_are_omitted_without_summing_or_choosing_a_gain(self):
  data=rank();duplicate={**data['topGainers'][0],'experienceGained':999}
  data['topGainers'].extend([duplicate,{**duplicate,'characterName':'Other Knight'}])
  value=ranking('Antica',0,NOW,lambda *a:json.dumps(data))
  self.assertEqual(value['omitted'],1);self.assertEqual(value['rows'],[('Other Knight',500,999,'Knight')])
 def test_ranking_cache_supports_extra_and_not_listed_is_not_zero(self):
  self.rise.collect(['Antica']);extra=self.provider.ranking_for_extra('Antica');self.assertIn('TibiaRise',extra['source']);self.assertIn('100',extra['note'])
  self.assertEqual(self.provider.report('Antica','Alpha Knight')[0],-25);self.assertIsNone(self.provider.report('Antica','Other Knight')[0])
  self.assertFalse(self.provider.report('Antica','Alpha Knight')['_projection'],'Ranking agregado não comprova31 medições diárias')
 def test_queue_is_bounded_and_successful_char_does_not_starve_next(self):
  for i in range(205):self.rise.request('Antica','Knight '+chr(65+i//26)+chr(65+i%26))
  with self.store.tx() as db:self.assertEqual(db.execute("SELECT count(*) FROM xp_rise_cache WHERE kind='character'").fetchone()[0],200)
 def test_maintain_success_rise_and_failed_old_sources_is_partial(self):
  self.provider.gs=lambda *a:(_ for _ in ()).throw(OSError())
  self.provider.td=lambda *a:(_ for _ in ()).throw(OSError())
  summary=self.provider.maintain(['Antica']);self.assertEqual(summary['status'],'partial');self.assertTrue(summary['attempted']);self.assertEqual(summary['tibiarise'][0]['status'],'ok')

if __name__=='__main__':unittest.main()
