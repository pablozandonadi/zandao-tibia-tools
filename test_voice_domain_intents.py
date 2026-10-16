import unittest
from voice.remote_ai_client import valid_intent
class DomainIntentTests(unittest.TestCase):
    def test_domain_nlu_validates_types_and_extra_fields(self):
        def intent(action,p):return {'action':action,'parameters':p,'needs_clarification':False,'clarification':None}
        self.assertTrue(valid_intent(intent('boss.kill',{'boss_id':'drume','killed_at':None,'boosted':False})))
        self.assertFalse(valid_intent(intent('boss.kill',{'boss_id':'drume','killed_at':None,'boosted':'yes'})))
        self.assertTrue(valid_intent(intent('market.price.add',{'item':'TC','price':'35k','offer_type':'buy','observed_at':None})))
        self.assertFalse(valid_intent(intent('market.price.add',{'item':'TC','price':'35k','offer_type':'buy','observed_at':None,'shell':'bad'})))
        self.assertFalse(valid_intent(intent('stamina.logout',{'stamina_minutes':True,'logged_out_at':None})))
        self.assertTrue(valid_intent(intent('stamina.get',{})))
        self.assertTrue(valid_intent(intent('boss.cooldown.set',{'boss_id':'drume','cooldown_minutes':1200})))
        self.assertFalse(valid_intent(intent('boss.cooldown.set',{'boss_id':'drume','cooldown_minutes':0})))
    def test_nlu_cannot_silently_create_personal_timer(self):
        base={'action':'timer.create','parameters':{'duration_seconds':30,'label':None,'personal':False},'needs_clarification':False,'clarification':None}
        self.assertTrue(valid_intent(base))
        base['parameters']['personal']=True
        self.assertFalse(valid_intent(base))
    def test_nlu_cannot_invent_observation_timestamp(self):
        base={'action':'market.price.add','parameters':{'item':'Tibia Coin','price':'36500 gp','offer_type':'sell','observed_at':'2026-10-16T00:00:00+00:00'},'needs_clarification':False,'clarification':None}
        self.assertFalse(valid_intent(base))
        base['parameters']['observed_at']=None
        self.assertTrue(valid_intent(base))
    def test_date_required_actions_and_relative_dates_request_clarification(self):
        from voice.remote_ai_client import safe_temporal_intent
        for action,parameters,text in [('stamina.project',{'target_datetime':None},'projete stamina'),('boss.kill',{'boss_id':'drume','killed_at':None,'boosted':False},'matei o Drume ontem')]:
            value=safe_temporal_intent({'action':action,'parameters':parameters,'needs_clarification':False,'clarification':None},text)
            self.assertTrue(value['needs_clarification']);self.assertEqual('unknown',value['action'])
    def test_relative_time_synonyms_cannot_default_to_now(self):
        from voice.remote_ai_client import safe_temporal_intent
        for action,p,text in [('boss.kill',{'boss_id':'drume','killed_at':None,'boosted':False},'matei Drume faz meia hora'),('stamina.correct',{'stamina_minutes':2340,'reference_at':None},'corrige minha referência de stamina meia hora atrás')]:
            value=safe_temporal_intent({'action':action,'parameters':p,'needs_clarification':False,'clarification':None},text)
            self.assertTrue(value['needs_clarification'])
