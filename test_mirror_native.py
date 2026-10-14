import unittest,time,sys,threading
from unittest.mock import patch
import mirror_native as native
from mirror_selector import Selection,clamp_rect,mouse_policy
from mirror_visual import frame
from mirror_native import compatible,MirrorEngine,list_clients
class MirrorTests(unittest.TestCase):
    def test_physical_square_and_limits(self):
        s=Selection('quadrado',dict(w=800,h=600,dpi=192));s.move(100,100)
        self.assertEqual(s.rect,dict(x=84,y=84,w=32,h=32))
        s.mouse('wheel',1,1,120);self.assertEqual(s.rect,dict(x=0,y=0,w=36,h=36))
    def test_reverse_manual_and_fine_adjust(self):
        s=Selection('manual',dict(w=800,h=600,dpi=96));s.mouse('down',100,100);s.move(40,20);s.mouse('up',40,20)
        self.assertEqual(s.rect,dict(x=40,y=20,w=60,h=80))
        s.key('right',ctrl=True);s.key('down');r=s.key('enter');self.assertEqual(r['origem'],dict(x=40,y=21,w=61,h=80))
    def test_cancel_has_no_result(self):
        s=Selection('manual',dict(w=10,h=10,dpi=96));self.assertIsNone(s.key('escape'));self.assertTrue(s.done)
    def test_geometry_change_pauses_but_move_does_not(self):
        c=dict(w=800,h=600,dpi=96);self.assertTrue(compatible(c,dict(c,x=-1920,y=100)))
        self.assertFalse(compatible(c,dict(c,dpi=120)));self.assertFalse(compatible(c,dict(c,w=801)))
    def test_glow_clear_interior_distinct_levels_cached(self):
        totals=[]
        for level in ('off','min','med','max'):
            image,m,t=frame(32,32,'#ff0000',level)
            self.assertEqual(image.getpixel((m+16,m+t+16)),(0,0,0,0))
            totals.append(sum(image.getchannel('A').tobytes()))
        self.assertEqual(totals,sorted(totals));self.assertEqual(len(set(totals)),4)
        self.assertIs(frame(32,32)[0],frame(32,32)[0])
    @unittest.skipUnless(sys.platform=='win32','Win32 lifecycle')
    def test_native_lifecycle_does_not_resurrect(self):
        e=MirrorEngine();e.configure('test',{'recortes':[]});self.assertTrue(e._thread.is_alive())
        e.configure('',None);self.assertEqual(e.character,'')
        e.close();self.assertFalse(e._thread.is_alive());e.configure('test',{'recortes':[]});self.assertFalse(e._thread.is_alive())
    @unittest.skipUnless(sys.platform=='win32','Win32 focus policy')
    def test_focus_hides_crop_and_glow_together(self):
        from unittest.mock import Mock
        e=MirrorEngine();e.hwnd=100;e.character='test'
        e.profile={'recortes':[dict(id='one',origem=dict(x=1,y=1,w=32,h=32),contexto=dict(w=800,h=600,dpi=96))]}
        crop,glow=Mock(),Mock();e._surfaces={'one':(crop,glow)}
        with patch.object(native,'geometry',return_value=dict(x=-1920,y=0,w=800,h=600,dpi=96)),patch.object(native.u,'GetForegroundWindow',return_value=101):
            e._tick()
        crop.hide.assert_called_once();glow.hide.assert_called_once();self.assertEqual(e.status()['estado'],'oculto')
    @unittest.skipUnless(sys.platform=='win32','Win32 callbacks')
    def test_blocked_callback_cannot_block_profile_teardown(self):
        entered=threading.Event();release=threading.Event()
        def change(state):entered.set();release.wait(2)
        e=MirrorEngine(on_change=change)
        try:
            e.configure('test',{'recortes':[]})
            e._emit(change,{})
            self.assertTrue(entered.wait(1))
            start=time.monotonic();e.configure('new',{'recortes':[]})
            self.assertLess(time.monotonic()-start,.5);self.assertEqual(e.character,'new')
        finally:e.close();release.set()
    def test_square_resize_keeps_both_dimensions_and_cursor_size(self):
        s=Selection('quadrado',dict(w=800,h=600,dpi=96));s.move(100,100)
        s.key('right',ctrl=True);self.assertEqual((s.rect['w'],s.rect['h'],s.size),(33,33,33))
        s.move(200,200);self.assertEqual((s.rect['w'],s.rect['h']),(33,33))
    def test_outside_click_cancel_pass_preserves_consumed_release(self):
        context=dict(w=800,h=600)
        self.assertEqual(mouse_policy(-1,20,context),'cancel_pass')
        self.assertEqual(mouse_policy(800,20,context),'cancel_pass')
        self.assertEqual(mouse_policy(20,20,context),'consume')
        self.assertEqual(mouse_policy(-1,20,context,True),'consume')
    def test_select_without_client_and_cancel_idempotent(self):
        e=MirrorEngine();self.assertFalse(e.select('manual',lambda r:None)['ok'])
        self.assertTrue(e.cancel_selection()['ok']);e.close();self.assertTrue(e.cancel_selection()['ok'])
    @unittest.skipUnless(sys.platform=='win32','Win32 cache')
    def test_surface_reuses_compositor_state_and_restores_after_hide(self):
        surface=native.Surface.__new__(native.Surface)
        surface.hwnd=1;surface.thumbnail=1;surface._position=None;surface._update=None;surface.shown=False
        rect=dict(x=10,y=20,w=32,h=32)
        with patch.object(native.u,'SetWindowPos') as position,patch.object(native.u,'ShowWindow') as hide,patch.object(native.d,'DwmUpdateThumbnailProperties',return_value=0) as update:
            surface.position(10,20,32,32);surface.position(10,20,32,32)
            surface.update(rect,32,32);surface.update(rect,32,32)
            self.assertEqual(position.call_count,1);self.assertEqual(update.call_count,1)
            surface.hide();surface.hide();self.assertEqual(hide.call_count,1)
            surface.position(10,20,32,32);self.assertEqual(position.call_count,2)
            surface.update(rect,32,32,128);self.assertEqual(update.call_count,2)
    @unittest.skipUnless(sys.platform=='win32','Win32 hook pairing')
    def test_consumed_square_down_consumes_release_outside_client(self):
        import ctypes
        from unittest.mock import Mock
        e=MirrorEngine();e.hwnd=100
        e._selection={'active':True,'model':Selection('quadrado',dict(w=800,h=600,dpi=96))}
        callback=Mock();e._callback=callback
        mouse=native.Mouse(native.W.POINT(100,100),0,0,0,0)
        with patch.object(native.u,'GetForegroundWindow',return_value=100),patch.object(native,'geometry',return_value=dict(x=0,y=0,w=800,h=600,dpi=96)),patch.object(native.u,'SetWindowsHookExW',return_value=1),patch.object(native.u,'UnhookWindowsHookEx',return_value=True),patch.object(native.u,'CallNextHookEx',return_value=0) as next_hook:
            e._install_hooks()
            self.assertEqual(e._mouse_cb(0,0x201,ctypes.addressof(mouse)),1)
            self.assertTrue(e._selection['button_down'])
            mouse.pt.x=900
            self.assertEqual(e._mouse_cb(0,0x202,ctypes.addressof(mouse)),1)
            self.assertIsNone(e._selection)
            next_hook.assert_not_called()
        delivered,args=e._events.get_nowait()
        self.assertIs(delivered,callback)
        self.assertEqual(args[0]['origem'],dict(x=84,y=84,w=32,h=32))
        e.close()
    @unittest.skipUnless(sys.platform=='win32','Win32 source identity')
    def test_recycled_window_handle_never_mirrors_another_process(self):
        import ctypes
        from unittest.mock import Mock
        e=MirrorEngine();e.hwnd=100;e._source_pid=7;e.character='test';e.profile={'recortes':[]}
        crop,glow=Mock(),Mock();e._surfaces={'old':(crop,glow)}
        def other_pid(hwnd,pid):ctypes.cast(pid,ctypes.POINTER(native.W.DWORD)).contents.value=8;return 1
        with patch.object(native,'geometry',return_value=dict(x=0,y=0,w=800,h=600,dpi=96)),patch.object(native.u,'GetWindowThreadProcessId',side_effect=other_pid):
            e._tick()
        crop.close.assert_called_once();glow.close.assert_called_once()
        self.assertEqual(e.hwnd,0);self.assertEqual(e.status()['estado'],'sem_cliente')
        e.close()
    def test_status_is_defensive(self):
        e=MirrorEngine();state=e.status();state['hwnd']=1;self.assertEqual(e.status()['hwnd'],0);e.close()
if __name__=='__main__':unittest.main()
