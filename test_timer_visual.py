import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

import audio_timers as at
import overlay
import timer_visual as visual
from PIL import Image


class TimerVisualTests(unittest.TestCase):
    def test_arquivo_antigo_preserva_configuracao_e_ganha_contorno(self):
        old = {"id":"po", "nome":"Potion", "personagem":"Zandao", "duracao":5.125,
               "antes":.2, "modo":"loop", "som":"usuario:meu.wav", "volume":35,
               "fonte":14, "cor":"#52EE60", "mensagem":"POTION SKILL", "fixo":True,
               "piscar":3, "alerta":True, "barra":True, "ativo":False,
               "tecla":{"vk":75,"nome":"K","ctrl":True,"shift":False,"alt":False}}
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'timers.json'
            path.write_text(json.dumps({"timers":[old]}))
            cfg = at.carregar(str(path))
            for k,v in old.items():
                self.assertEqual(cfg['timers'][0][k],v,k)
            self.assertEqual(cfg['timers'][0]['visual']['estilo'],'contorno')
            cfg['timers'][0]['visual']={'estilo':'glow','familia':'Segoe UI','intensidade':22}
            cfg['barra'].update(estilo='arredondada',cor_tempo=True,texto_estilo='sombra')
            at.salvar(cfg,str(path))
            self.assertEqual(at.carregar(str(path)),cfg)

    def test_glow_transparente_sem_contorno_preto(self):
        image=visual.texto('Potion',(70,240,100),34,{'estilo':'glow'})
        pixels=list(image.get_flattened_data())
        self.assertTrue(any(0<a<255 for r,g,b,a in pixels))
        self.assertFalse(any(a>0 and r==g==b==0 for r,g,b,a in pixels))
        self.assertEqual(image.getpixel((0,0))[3],0)
        self.assertLessEqual(visual.texto('Mensagem muito longa '*4,(255,220,0),96,largura=320).width,320)

    def test_premultiplicacao_bgra(self):
        self.assertEqual(visual.bgra_premultiplicado(Image.new('RGBA',(1,1),(200,100,50,128))),bytes((25,50,100,128)))

    def test_barras_e_cores_no_final(self):
        self.assertGreater(visual.cor_progresso(1)[1],visual.cor_progresso(1)[0])
        self.assertGreater(visual.cor_progresso(0)[0],visual.cor_progresso(0)[1])
        for style in visual.ESTILOS_BARRA:
            cfg=overlay.normalizar_barra({'estilo':style,'espessura':4,'cor_tempo':True})
            image=visual.barras([('Potion',.6,'0:03','verde'),('Utito',0,'0:00','amarelo')],cfg,overlay.cor_rgb)
            self.assertEqual(image.width,328)
            self.assertEqual(image.getpixel((0,0))[3],0)

    def test_estilo_encaminhado_no_aviso_piscando_e_no_teste(self):
        motor=at.Motor.__new__(at.Motor)
        motor.alerta=Mock(); motor.cfg={'alerta':{'x':50,'y':30}}
        motor._piscou={};motor._pisca_dono=motor._alerta_fixo=None
        t=at.normalizar({'id':'p','alerta':True,'piscar':3,'duracao':10,'visual':{'estilo':'glow'}})
        e=at.EstadoTimer(t);e.apertou(0)
        motor._talvez_piscar(e,7)
        self.assertEqual(motor.alerta.mostrar.call_args.kwargs['visual'],t['visual'])
        motor.testar_alerta(visual=t['visual'])
        self.assertEqual(motor.alerta.mostrar.call_args.kwargs['visual'],t['visual'])


if __name__=='__main__':
    unittest.main()
