import unittest
from unittest.mock import patch
import web_api


class TestHistoricoCriaturas(unittest.TestCase):
    def test_importacao_le_apenas_os_logs_da_mesma_hunt(self):
        api=web_api.API.__new__(web_api.API)
        solo='XP Gain: 1\nKilled Monsters:\n  86x draken spellweavers'
        dano='Received Damage\nTotal: 100\nDamage Types:\nPhysical 100 (100%)'
        hunt={'id':'x','nome':'Drakens','entrada':{'solo':solo,'dano':dano}}
        with patch.object(web_api.historico,'obter',return_value=hunt), patch.object(web_api.historico,'salvar') as salvar, patch.object(web_api.planejador,'catalogo_visual',return_value={'lista':[{'name':'Draken Spellweaver'}]}):
            r=api.criaturas_importar_hunt('x')
            salvar.assert_not_called()
        self.assertEqual(r['selecao'],[{'nome':'Draken Spellweaver','peso':86}])
        self.assertEqual(r['dano_texto'],dano)
        self.assertEqual(r['log_texto'],solo)
        self.assertEqual(hunt['entrada']['solo'],solo)

    def test_hunt_sem_dano_nao_reutiliza_dano_de_outra_sessao(self):
        api=web_api.API.__new__(web_api.API)
        with patch.object(web_api.historico,'obter',return_value={'entrada':{'solo':'XP Gain: 1\nKilled Monsters:\n  86x draken spellweavers'}}),patch.object(web_api.planejador,'catalogo_visual',return_value={'lista':[{'name':'Draken Spellweaver'}]}):
            r=api.criaturas_importar_hunt('x')
        self.assertEqual(r['dano_texto'],'')
        self.assertFalse(r['real'])


if __name__=='__main__': unittest.main()
