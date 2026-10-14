import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

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
            cfg['timers'][0]['visual']=visual.aparencia({'estilo':'glow','familia':'Segoe UI','intensidade':22})
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

    def test_barra_sem_escrita_e_opcoes_independentes(self):
        self.assertFalse(overlay.normalizar_barra({'nome':False})['tempo'])
        for nome,tempo in ((False,False),(True,False),(False,True),(True,True)):
            cfg=overlay.normalizar_barra({'nome':nome,'tempo':tempo})
            image=visual.barras([('Potion',.6,'0:03','verde')],cfg,overlay.cor_rgb)
            expected=cfg['espessura']+6+(18 if nome or tempo else 0)+4
            self.assertEqual(image.height,expected)
            self.assertEqual(overlay.layout_barras(1,cfg,(0,0,1000,800))[3],expected)

    def test_estilo_encaminhado_no_aviso_piscando_e_no_teste(self):
        motor=at.Motor.__new__(at.Motor)
        motor.alerta=Mock(); motor._avisos={'p':motor.alerta}; motor.cfg={'alerta':{'x':50,'y':30}}
        motor._piscou={};motor._pisca_dono=motor._alerta_fixo=None
        t=at.normalizar({'id':'p','alerta':True,'piscar':3,'duracao':10,'visual':{'estilo':'glow'}})
        e=at.EstadoTimer(t);e.apertou(0)
        motor._talvez_piscar(e,7)
        self.assertEqual(motor.alerta.mostrar.call_args.kwargs['visual'],t['visual'])
        motor.testar_alerta(visual=t['visual'])
        self.assertEqual(motor.alerta.mostrar.call_args.kwargs['visual'],t['visual'])

    def test_cores_independentes_e_opcoes_sobrevivem_a_reabertura(self):
        antigo=at.normalizar({'cor':'#345678'})
        self.assertEqual((antigo['cor_texto'],antigo['cor_barra']),('#345678','#345678'))
        self.assertFalse(antigo['sem_som'])
        t=at.normalizar({**antigo,'cor_texto':'#FF0000','cor_barra':'#0000FF',
                        'texto_cor_tempo':True,'barra_cor_tempo':False,'sem_som':True,
                        'visual':{'estilo':'simples','glow':True,'sombra':True,'borda':True,
                                  'cor_glow':'#00FF00','cor_sombra':'#888888','cor_borda':'#FFFF00'}})
        cfg={**at.PADRAO,'timers':[t],'barra':overlay.normalizar_barra({'orientacao':'vertical'})}
        with tempfile.TemporaryDirectory() as d:
            path=str(Path(d)/'timers.json')
            at.salvar(cfg,path)
            self.assertEqual(at.carregar(path),cfg)
        self.assertEqual(at.cor_alerta(t,1),'#00E63C')
        self.assertEqual(at.cor_alerta(t,0),'#FF003C')
        self.assertEqual(at.cor_alerta({**t,'texto_cor_tempo':False},.5),'#FF0000')

    def test_efeitos_combinados_preservam_cor_da_face(self):
        image=visual.texto('TEXTO',(255,0,0),34,{'estilo':'simples','glow':True,'sombra':True,'borda':True,
                           'cor_glow':'#00FF00','cor_sombra':'#0000FF','cor_borda':'#FFFF00'})
        pixels=list(image.get_flattened_data())
        self.assertIn((255,0,0,255),pixels)
        self.assertIn((255,255,0,255),pixels)
        self.assertTrue(any(g>r and g>b and a>0 for r,g,b,a in pixels))
        self.assertTrue(any(b>r and b>g and a>0 for r,g,b,a in pixels))
        simples=visual.texto('TEXTO',(255,0,0),34,{'estilo':'simples'})
        self.assertFalse(any(a and (g or b) for r,g,b,a in simples.get_flattened_data()))
        self.assertEqual(visual.aparencia({'estilo':'glow','glow':False,'sombra':False,'borda':False})['glow'],False)

    def test_barras_verticais_preenchem_de_baixo_e_rotulos_nao_giram(self):
        for nome,tempo in ((False,False),(True,False),(False,True),(True,True)):
            cfg=overlay.normalizar_barra({'orientacao':'vertical','largura':100,'espessura':8,'nome':nome,'tempo':tempo,'estilo':'minimalista'})
            itens=[('A',.5,'0:05','#0000FF',False),('B',1,'0:10','#FF0000',False)]
            image=visual.barras(itens,cfg,overlay.cor_rgb)
            self.assertEqual(image.size,overlay.layout_barras(2,cfg,(0,0,800,800))[2:4])
            _,_,coluna=visual.dimensoes_barras(2,cfg)
            x=2+(coluna-8)//2
            y=4+(18 if nome else 0)
            self.assertEqual(image.getpixel((x+3,y+75)),(0,0,255,255))
            self.assertNotEqual(image.getpixel((x+3,y+25)),(0,0,255,255))

    def test_barra_cor_por_tempo_independe_da_opcao_global(self):
        cfg=overlay.normalizar_barra({'largura':100,'espessura':8,'nome':False,'tempo':False,'estilo':'minimalista','cor_tempo':True})
        image=visual.barras([('A',.5,'','#0000FF',False)],cfg,overlay.cor_rgb)
        self.assertEqual(image.getpixel((10,5)),(0,0,255,255))
        cfg['cor_tempo']=False
        image=visual.barras([('A',.5,'','#0000FF',True)],cfg,overlay.cor_rgb)
        self.assertEqual(image.getpixel((10,5)),(*visual.cor_progresso(.5),255))

    def _motor_falso(self, sem_som=True):
        t=at.normalizar({'id':'p','personagem':'Teste','duracao':10,'antes':3,'alerta':True,'barra':True,'fixo':True,
                        'sem_som':sem_som,'cor_texto':'#FF0000','cor_barra':'#0000FF',
                        'tecla':{'vk':75,'nome':'K','ctrl':True}})
        e=at.EstadoTimer(t);e.apertou(0)
        m=at.Motor.__new__(at.Motor)
        m.cfg={**at.PADRAO,'timers':[t]};m.estados={'p':e}
        m._trava=threading.Lock();m._apertadas=set();m._ao_mudar=None;m._ultimo_envio=0
        m._alerta_fixo=m._pisca_dono=None;m._piscou={}
        m._barras_ate=m._ultima_barra=0;m._barras_visiveis=False
        m.tocador=Mock();m.alerta=Mock();m.barras=Mock()
        m._avisos={'p':m.alerta};m._barras_individuais={'timer:p':m.barras}
        m._previas_ate=0;m._previas=[];m._ultima_individual=0
        return m,e

    def test_sem_som_mantem_contagem_texto_e_barra(self):
        for mute in (True,False):
            m,e=self._motor_falso(mute)
            with patch.object(at.time,'monotonic',return_value=7),patch.object(at,'tecla_apertada',return_value=False):
                m._passo()
            self.assertEqual(m.tocador.tocar.call_count,0 if mute else 1)
            self.assertTrue(e.rodando)
            self.assertEqual(m.alerta.mostrar.call_args.args[1],'#FF0000')
            self.assertEqual(m.barras.atualizar.call_args.args[0][0][3],'#0000FF')
            self.assertEqual(m.alerta.mostrar.call_args.args[2],0)

    def test_aviso_fixo_so_some_com_o_atalho_completo_do_timer(self):
        m,e=self._motor_falso()
        with patch.object(at.time,'monotonic',return_value=7),patch.object(at,'tecla_apertada',return_value=False):
            m._passo()
        with patch.object(at.time,'monotonic',return_value=8),patch.object(at,'tecla_apertada',side_effect=lambda vk:vk==77):
            m._passo()
        m.alerta.esconder.assert_not_called()
        with patch.object(at.time,'monotonic',return_value=8),patch.object(at,'tecla_apertada',side_effect=lambda vk:vk==75):
            m._passo()
        m.alerta.esconder.assert_not_called()
        with patch.object(at.time,'monotonic',return_value=8),patch.object(at,'tecla_apertada',return_value=False):
            m._passo()
        with patch.object(at.time,'monotonic',return_value=8),patch.object(at,'tibia_em_foco',return_value=True),patch.object(at,'tecla_apertada',side_effect=lambda vk:vk in (75,at.VK_CONTROL)):
            m._passo()
        m.alerta.esconder.assert_called_once()
        self.assertEqual(e.fim,18)

    def test_desligado_nao_dispara_nem_reaproveita_tecla_segurada(self):
        m,e=self._motor_falso();m.cfg['ligado']=False
        m._ao_mudar=Mock()
        with patch.object(at.time,'monotonic',return_value=8),patch.object(at,'tecla_apertada',side_effect=lambda vk:vk in (75,at.VK_CONTROL)),patch.object(at,'tibia_em_foco',return_value=True):
            m._passo()
            self.assertFalse(e.rodando)
            m.tocador.tocar.assert_not_called()
            m.cfg['ligado']=True;m._passo()
            self.assertFalse(e.rodando)
        with patch.object(at.time,'monotonic',return_value=9),patch.object(at,'tecla_apertada',return_value=False):
            m._passo()
        with patch.object(at.time,'monotonic',return_value=10),patch.object(at,'tecla_apertada',side_effect=lambda vk:vk in (75,at.VK_CONTROL)),patch.object(at,'tibia_em_foco',return_value=True):
            m._passo()
        self.assertEqual(e.fim,20)
        self.assertIsNone(m._ao_mudar.call_args_list[0].args[0]['timers']['p']['restante'])

    def test_posicoes_individuais_migradas_e_persistidas_sem_arredondar(self):
        cfg={**at.PADRAO,'alerta':{'x':12.345,'y':67.89},
             'barra':overlay.normalizar_barra({'x':23.456,'y':7.89,'orientacao':'vertical'}),
             'timers':[{'id':'a'}, {'id':'b','pos_alerta':{'x':80.123,'y':32.987},
                         'cfg_barra':{'x':90.876,'y':10.234,'orientacao':'horizontal'}}]}
        with tempfile.TemporaryDirectory() as d:
            path=str(Path(d)/'timers.json');at.salvar(cfg,path);loaded=at.carregar(path)
            self.assertEqual(loaded['timers'][0]['pos_alerta'],cfg['alerta'])
            self.assertEqual(loaded['timers'][0]['cfg_barra'],cfg['barra'])
            at.salvar(loaded,path);self.assertEqual(at.carregar(path),loaded)
        a,b=loaded['timers']
        self.assertNotEqual(a['pos_alerta'],b['pos_alerta'])
        self.assertEqual(b['cfg_barra']['x'],90.876)
        before=overlay.layout_barras(1,b['cfg_barra'],(0,0,1920,1080))
        self.assertEqual(before,overlay.layout_barras(1,loaded['timers'][1]['cfg_barra'],(0,0,1920,1080)))

    def test_previa_simultanea_nao_altera_configuracao_salva(self):
        m,e=self._motor_falso()
        t=at.normalizar({**e.cfg,'id':'q','pos_alerta':{'x':80,'y':90},'cfg_barra':{'x':70,'y':60}})
        original=json.loads(json.dumps(m.cfg))
        with patch.object(at.overlay,'Overlay',return_value=Mock()),patch.object(at.overlay,'Barras',return_value=Mock()),patch.object(at.time,'monotonic',return_value=10):
            m.testar_timers([e.cfg,t]);m._desenhar_individuais([(e.cfg,.5,5,True),(t,.5,5,True)])
        self.assertEqual(m.cfg,original)
        self.assertIn('previa:p',m._avisos);self.assertIn('previa:q',m._avisos)
        self.assertIn('previa:p',m._barras_individuais);self.assertIn('previa:q',m._barras_individuais)
        self.assertEqual(m._avisos['previa:q'].mostrar.call_args.kwargs['pos'],t['pos_alerta'])

    def test_texto_muda_cor_sem_reiniciar_pisca_ou_tempo_de_exibicao(self):
        instance=overlay.Overlay.__new__(overlay.Overlay)
        instance._visivel=True
        instance._progresso={'fracao':1,'duracao':10}
        instance._progresso_ini=0;instance._cor=(0,230,60)
        instance._texto='Aviso';instance._tamanho=34
        instance._visual=visual.aparencia({'estilo':'simples'})
        instance._largura_texto=800;instance._alpha=80
        with patch.object(overlay,'_u32') as native,patch.object(overlay.time,'monotonic',return_value=5),patch.object(overlay.layered_image,'mostrar') as display:
            instance._wndproc(1,overlay.WM_TIMER,3,0)
            self.assertEqual(instance._cor,visual.cor_progresso(.5))
            display.assert_called_once()
            self.assertEqual(display.call_args.args[2],80)
            native.SetTimer.assert_not_called()
            native.KillTimer.assert_not_called()


class TimerAlertLifecycleTests(unittest.TestCase):
    def motor_expirado(self):
        m, e = TimerVisualTests()._motor_falso()
        m.personagem = 'Teste'
        with patch.object(at.time, 'monotonic', return_value=11), patch.object(at, 'tecla_apertada', return_value=False):
            m._passo()
        self.assertFalse(e.rodando)
        self.assertEqual(m._alerta_fixo, 'p')
        m.alerta.reset_mock()
        return m, e

    def test_desativar_timer_expirado_remove_aviso_fixo_e_previa(self):
        m, e = self.motor_expirado()
        other = Mock()
        m._avisos['outro'] = other
        preview = m._avisos['previa:p'] = Mock()
        m._previas = [dict(e.cfg)]
        cfg = {**m.cfg, 'timers': [{**e.cfg, 'ativo': False}]}
        with patch.object(at, 'salvar'):
            m.atualizar_cfg(cfg)
        m.alerta.esconder.assert_called_once()
        preview.esconder.assert_called_once()
        other.esconder.assert_not_called()
        self.assertIsNone(m._alerta_fixo)
        self.assertIsNone(m._pisca_dono)
        self.assertEqual(m._previas, [])
        self.assertFalse(m.estados['p'].rodando)

    def test_desligar_global_encerra_tambem_teste_persistente(self):
        m, e = self.motor_expirado()
        m.alerta = Mock()  # janela de teste independente do aviso do timer
        preview = m._avisos['previa:p'] = Mock()
        m._previas_ate = m._barras_ate = 999
        with patch.object(at, 'salvar'):
            m.atualizar_cfg({**m.cfg, 'ligado': False})
        m.alerta.esconder.assert_called_once()
        self.assertTrue(preview.esconder.called)
        self.assertEqual((m._previas_ate, m._barras_ate), (0, 0))
        self.assertIsNone(m._alerta_fixo)

    def test_parar_contagens_remove_teste_e_aviso_expirado(self):
        m, e = self.motor_expirado()
        m._previas_ate = m._barras_ate = 999
        m.parar_todos()
        self.assertTrue(m.alerta.esconder.called)
        self.assertEqual((m._previas_ate, m._barras_ate), (0, 0))
        self.assertIsNone(m._alerta_fixo)

    def test_desligar_apenas_aviso_remove_texto_sem_parar_contagem(self):
        m, e = TimerVisualTests()._motor_falso()
        m.personagem = 'Teste'
        with patch.object(at, 'salvar'):
            m.atualizar_cfg({**m.cfg, 'timers': [{**e.cfg, 'alerta': False}]})
        m.alerta.esconder.assert_called_once()
        self.assertTrue(e.rodando)

    def janela(self):
        obj = overlay.Overlay.__new__(overlay.Overlay)
        obj.hwnd = 1
        obj._trava = threading.Lock()
        obj._pedido = ('exibição pendente',)
        obj._visivel = True
        obj._image = Image.new('RGBA', (40, 20))
        obj._alpha = 80
        obj._progresso = {'fracao': 1, 'duracao': 10}
        obj._pisca_ini = obj._progresso_ini = 0
        obj._cor = (0, 230, 60)
        obj._texto = 'Aviso'
        obj._tamanho = 34
        obj._visual = visual.aparencia({'estilo': 'simples'})
        obj._largura_texto = 800
        return obj

    def test_esconder_cancela_mostrar_que_ainda_esta_na_fila(self):
        obj = self.janela()
        with patch.object(overlay, '_u32') as native:
            obj.esconder()
            self.assertIsNone(obj._pedido)
            obj._wndproc(1, overlay.WM_APP + 1, 0, 0)
            native.SetWindowPos.assert_not_called()
            native.PostMessageW.assert_called_once_with(1, overlay.WM_APP + 2, 0, 0)

    def test_ocultar_ou_expirar_nao_redesenha_e_ignora_eventos_atrasados(self):
        for msg, param in [(overlay.WM_APP + 2, 0), (overlay.WM_TIMER, 1)]:
            with self.subTest(msg=msg):
                obj = self.janela()
                with patch.object(overlay, '_u32') as native, patch.object(overlay.layered_image, 'mostrar') as draw:
                    obj._wndproc(1, msg, param, 0)
                    obj._wndproc(1, overlay.WM_TIMER, 2, 0)
                    obj._wndproc(1, overlay.WM_TIMER, 3, 0)
                    obj._wndproc(1, overlay.WM_PAINT, 0, 0)
                    draw.assert_not_called()
                    native.ShowWindow.assert_called_once_with(1, overlay.SW_HIDE)
                    self.assertFalse(obj._visivel)
                    self.assertIsNone(obj._image)
                    self.assertIsNone(obj._progresso)

    def test_alerta_pode_ser_mostrado_de_novo_apos_ocultar(self):
        obj = self.janela()
        with patch.object(overlay, '_u32') as native, patch.object(overlay, 'janela_do_tibia', return_value=(0, 0, 800, 600)), patch.object(overlay.layered_image, 'mostrar') as draw:
            obj._wndproc(1, overlay.WM_APP + 2, 0, 0)
            obj.mostrar('Novo aviso', so_tibia=False)
            obj._wndproc(1, overlay.WM_APP + 1, 0, 0)
            obj._wndproc(1, overlay.WM_PAINT, 0, 0)
            self.assertTrue(obj._visivel)
            self.assertEqual(obj._texto, 'Novo aviso')
            self.assertTrue(draw.called)


if __name__=='__main__':
    unittest.main()
