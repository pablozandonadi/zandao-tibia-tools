import ctypes
import threading
import unittest
from unittest.mock import Mock, patch
from ctypes import wintypes
from PIL import Image
import overlay as ov
import timer_visual

RECT = (20, 30, 820, 630)


class TimerFocusTests(unittest.TestCase):
    def setUp(self):
        self.native=patch.object(ov,'_u32').start()
        self.focus=patch.object(ov,'janela_tibia_em_foco',return_value=RECT).start()
        self.draw=patch.object(ov.layered_image,'mostrar').start()
        self.addCleanup(patch.stopall)

    def alert(self, seconds=0):
        obj=ov.Overlay.__new__(ov.Overlay)
        obj.hwnd=1;obj._trava=threading.Lock();obj._visivel=False;obj._ativo=False
        obj._fim_exibicao=None;obj._image=None;obj._alpha=255
        obj._pedido=('Buff',(0,230,60),seconds,RECT,34,dict(ov.ALERTA_PADRAO),False,timer_visual.aparencia({}),None)
        obj._wndproc(1,ov.WM_APP+1,0,0)
        self.native.reset_mock();self.draw.reset_mock()
        return obj

    def bars(self):
        obj=ov.Barras.__new__(ov.Barras)
        obj.hwnd=2;obj._trava=threading.Lock();obj._visivel=False;obj._ativo=False
        obj._dados=([('Buff',.5,'00:05','verde',False)],dict(ov.BARRA_PADRAO),RECT)
        obj._wndproc(2,ov.WM_APP+1,0,0)
        self.native.reset_mock();self.draw.reset_mock()
        return obj

    def test_fixed_alert_hides_and_restores_without_restarting(self):
        obj=self.alert();image=obj._image;start=obj._progresso_ini
        self.focus.return_value=None
        obj._wndproc(1,ov.WM_TIMER,4,0)
        self.assertFalse(obj._visivel)
        self.assertTrue(obj._ativo)
        self.assertIs(obj._image,image)
        self.native.ShowWindow.assert_called_once_with(1,ov.SW_HIDE)
        obj._wndproc(1,ov.WM_PAINT,0,0)
        self.draw.assert_not_called()
        self.focus.return_value=RECT
        obj._wndproc(1,ov.WM_TIMER,4,0)
        self.assertTrue(obj._visivel)
        self.assertEqual(obj._progresso_ini,start)
        self.native.SetTimer.assert_not_called()

    def test_alert_never_shows_initially_when_another_program_is_active(self):
        self.focus.return_value=None
        obj=self.alert()
        self.assertFalse(obj._visivel)
        self.assertTrue(obj._ativo)
        self.native.SetWindowPos.assert_not_called()
        self.focus.return_value=RECT
        obj._wndproc(1,ov.WM_TIMER,4,0)
        self.assertTrue(obj._visivel)

    def test_timed_alert_expires_in_background_and_does_not_return(self):
        with patch.object(ov.time,'monotonic',return_value=100):obj=self.alert(3)
        self.focus.return_value=None
        with patch.object(ov.time,'monotonic',return_value=101):obj._wndproc(1,ov.WM_TIMER,4,0)
        self.focus.return_value=RECT
        with patch.object(ov.time,'monotonic',return_value=104):obj._wndproc(1,ov.WM_TIMER,4,0)
        self.assertFalse(obj._ativo)
        self.assertFalse(obj._visivel)
        self.assertIsNone(obj._image)
        self.native.SetWindowPos.assert_not_called()

    def test_native_expiration_still_clears_a_hidden_alert(self):
        with patch.object(ov.time,'monotonic',return_value=100):obj=self.alert(3)
        self.focus.return_value=None
        with patch.object(ov.time,'monotonic',return_value=101):obj._wndproc(1,ov.WM_TIMER,4,0)
        with patch.object(ov.time,'monotonic',return_value=104):obj._wndproc(1,ov.WM_TIMER,1,0)
        self.assertFalse(obj._ativo)
        self.assertIsNone(obj._image)

    def test_stale_expiration_from_previous_alert_does_not_clear_new_fixed_alert(self):
        obj=self.alert()
        obj._wndproc(1,ov.WM_TIMER,1,0)
        self.assertTrue(obj._ativo)
        self.assertTrue(obj._visivel)

    def test_focus_loss_before_paint_or_animation_does_not_draw(self):
        for message,param in [(ov.WM_PAINT,0),(ov.WM_TIMER,2),(ov.WM_TIMER,3)]:
            with self.subTest(message=message,param=param):
                obj=self.alert();self.focus.return_value=None
                obj._wndproc(1,message,param,0)
                self.draw.assert_not_called()
                self.assertFalse(obj._visivel)
                self.focus.return_value=RECT

    def test_explicit_stop_prevents_returning_on_focus_change(self):
        obj=self.alert();obj._wndproc(1,ov.WM_APP+2,0,0)
        self.native.reset_mock()
        obj._wndproc(1,ov.WM_TIMER,4,0)
        self.assertFalse(obj._visivel)
        self.native.SetWindowPos.assert_not_called()

    def test_alert_tracks_foreground_tibia_window_instead_of_largest_window(self):
        obj=self.alert()
        self.focus.return_value=(300,200,900,650)
        obj._wndproc(1,ov.WM_TIMER,4,0)
        self.assertTrue(obj._visivel)
        self.assertEqual(obj._largura_texto,600)
        self.assertTrue(self.native.SetWindowPos.called)

    def test_bars_hide_and_restore_with_current_data(self):
        obj=self.bars();self.focus.return_value=None
        obj._wndproc(2,ov.WM_TIMER,4,0)
        obj._wndproc(2,ov.WM_PAINT,0,0)
        self.assertFalse(obj._visivel)
        self.draw.assert_not_called()
        self.focus.return_value=RECT
        obj._dados=([('Buff',.1,'00:01','verde',False)],dict(ov.BARRA_PADRAO),RECT)
        obj._wndproc(2,ov.WM_TIMER,4,0)
        obj._wndproc(2,ov.WM_PAINT,0,0)
        self.assertTrue(obj._visivel)
        self.draw.assert_called_once()

    def test_empty_bars_cancel_pending_render_even_while_hidden(self):
        obj=self.bars();self.focus.return_value=None
        obj._wndproc(2,ov.WM_TIMER,4,0)
        obj.atualizar([],ov.BARRA_PADRAO)
        self.native.PostMessageW.assert_called_with(2,ov.WM_APP+2,0,0)
        obj._wndproc(2,ov.WM_APP+1,0,0)
        obj._wndproc(2,ov.WM_APP+2,0,0)
        self.focus.return_value=RECT
        self.native.reset_mock()
        obj._wndproc(2,ov.WM_TIMER,4,0)
        self.native.SetWindowPos.assert_not_called()

    def test_new_values_repaint_even_when_geometry_has_not_changed(self):
        for obj,hwnd in [(self.alert(),1),(self.bars(),2)]:
            with self.subTest(hwnd=hwnd):
                self.native.reset_mock()
                if hwnd==1:
                    obj._pedido=('UE',(255,0,0),0,RECT,34,dict(ov.ALERTA_PADRAO),False,timer_visual.aparencia({}),None)
                obj._wndproc(hwnd,ov.WM_APP+1,0,0)
                self.native.InvalidateRect.assert_called()


class ForegroundTibiaIdentityTests(unittest.TestCase):
    def test_checks_process_executable_and_returns_active_rect(self):
        with patch.object(ov.sys,'platform','win32'),patch.object(ov,'_u32') as native,patch.object(ov,'_k32') as kernel:
            native.GetForegroundWindow.return_value=123
            native.IsWindowVisible.return_value=True;native.IsIconic.return_value=False
            kernel.OpenProcess.return_value=456
            def process(handle,flags,path,size):path.value='client.exe';return True
            def rect(hwnd,pointer):
                value=ctypes.cast(pointer,ctypes.POINTER(wintypes.RECT)).contents
                value.left,value.top,value.right,value.bottom=RECT
                return True
            kernel.QueryFullProcessImageNameW.side_effect=process
            native.GetWindowRect.side_effect=rect
            self.assertEqual(ov.janela_tibia_em_foco(),RECT)
            kernel.CloseHandle.assert_called_once_with(456)
            kernel.QueryFullProcessImageNameW.side_effect=lambda handle,flags,path,size:(setattr(path,'value','other.exe'),True)[1]
            self.assertIsNone(ov.janela_tibia_em_foco())

    def test_pinned_editor_can_start_before_any_active_alert(self):
        with patch.object(ov.sys, 'platform', 'win32'), patch.object(ov, '_u32') as native, \
                patch.object(ov, '_hwnd_app_fixado', 42), patch.object(ov, '_ultimo_tibia', None), \
                patch.object(ov, 'janela_do_tibia', return_value=RECT) as visible:
            native.GetForegroundWindow.return_value = 42
            native.GetWindowLongW.return_value = ov.WS_EX_TOPMOST
            self.assertEqual(ov.janela_tibia_em_foco(), RECT)
            visible.return_value = None
            self.assertIsNone(ov.janela_tibia_em_foco())

    def test_pinned_app_exception_uses_last_tibia_and_rejects_other_windows(self):
        with patch.object(ov.sys, 'platform', 'win32'), patch.object(ov, '_u32') as native, \
                patch.object(ov, '_k32') as kernel, patch.object(ov, '_hwnd_app_fixado', 42), \
                patch.object(ov, '_ultimo_tibia', None):
            native.IsWindowVisible.return_value = True
            native.IsIconic.return_value = False
            native.GetWindowLongW.return_value = ov.WS_EX_TOPMOST
            kernel.OpenProcess.return_value = 456
            def process(handle, flags, path, size):
                path.value = 'client.exe' if native.GetForegroundWindow.return_value in (123, 42) else 'other.exe'
                return True
            def rect(hwnd, pointer):
                self.assertEqual(hwnd, 123)
                value = ctypes.cast(pointer, ctypes.POINTER(wintypes.RECT)).contents
                value.left, value.top, value.right, value.bottom = RECT
                return True
            kernel.QueryFullProcessImageNameW.side_effect = process
            native.GetWindowRect.side_effect = rect
            native.GetForegroundWindow.return_value = 123
            self.assertEqual(ov.janela_tibia_em_foco(), RECT)
            native.GetForegroundWindow.return_value = 42
            self.assertEqual(ov.janela_tibia_em_foco(), RECT)
            native.IsIconic.side_effect = lambda hwnd: hwnd == 123
            self.assertIsNone(ov.janela_tibia_em_foco())
            native.IsIconic.side_effect = None
            native.IsIconic.return_value = False
            native.GetForegroundWindow.return_value = 99
            self.assertIsNone(ov.janela_tibia_em_foco())
            native.GetForegroundWindow.return_value = 42
            native.GetWindowLongW.return_value = 0
            kernel.QueryFullProcessImageNameW.side_effect = lambda h, f, p, s: (setattr(p, 'value', 'app.exe'), True)[1]
            self.assertIsNone(ov.janela_tibia_em_foco())

    def test_no_foreground_minimized_or_inaccessible_process_is_hidden(self):
        with patch.object(ov.sys,'platform','win32'),patch.object(ov,'_u32') as native,patch.object(ov,'_k32') as kernel:
            native.GetForegroundWindow.return_value=0
            self.assertIsNone(ov.janela_tibia_em_foco())
            native.GetForegroundWindow.return_value=123;native.IsWindowVisible.return_value=True
            native.IsIconic.return_value=True
            self.assertIsNone(ov.janela_tibia_em_foco())
            native.IsIconic.return_value=False;kernel.OpenProcess.return_value=0
            self.assertIsNone(ov.janela_tibia_em_foco())


if __name__=='__main__':unittest.main()
