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
    @unittest.skipUnless(sys.platform=='win32','Win32 pinned editor')
    def test_pinned_editor_shows_bound_crop_but_never_starts_selection(self):
        from unittest.mock import Mock
        e=MirrorEngine();e.hwnd=100;e.character='test'
        item=dict(id='one',origem=dict(x=1,y=1,w=32,h=32),destino=dict(x=50,y=50),contexto=dict(w=800,h=600,dpi=96))
        e.profile={'recortes':[item]};crop,glow=Mock(),Mock();e._surfaces={'one':(crop,glow)}
        with patch.object(native,'geometry',return_value=dict(x=-1920,y=0,w=800,h=600,dpi=96)) as geometry, \
                patch.object(native.u,'GetForegroundWindow',return_value=42) as foreground, \
                patch.object(native.O,'_hwnd_app_fixado',42), \
                patch.object(native.u,'GetWindowLongW',return_value=native.O.WS_EX_TOPMOST) as style, \
                patch.object(native.u,'IsWindowVisible',return_value=True), \
                patch.object(native.layered_image,'mostrar'), patch.object(e,'_install_hooks') as hooks:
            e._tick();crop.position.assert_called_once();self.assertEqual(e.status()['estado'],'ativo')
            e._selection=dict(mode='quadrado',existing=None,active=False)
            e._tick();hooks.assert_not_called();self.assertFalse(e._selection['active'])
            e._selection=None
            foreground.return_value=99;e._tick();crop.hide.assert_called()
            foreground.return_value=42;style.return_value=0;crop.reset_mock();e._tick();crop.position.assert_not_called()
            style.return_value=native.O.WS_EX_TOPMOST;geometry.return_value=None
            e._tick();self.assertEqual(e.status()['estado'],'sem_cliente')

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
    def test_square_click_positions_then_enter_confirms_without_native_work_in_hook(self):
        import ctypes
        from unittest.mock import Mock
        e=MirrorEngine();e.hwnd=100
        e._selection={'active':True,'model':Selection('quadrado',dict(w=800,h=600,dpi=96))}
        callback=Mock();e._callback=callback
        mouse=native.Mouse(native.W.POINT(100,100),0,0,0,0)
        with patch.object(native.u,'GetForegroundWindow',return_value=100),patch.object(native.u,'GetAsyncKeyState',return_value=0),patch.object(native,'geometry',return_value=dict(x=0,y=0,w=800,h=600,dpi=96)),patch.object(native.u,'SetWindowsHookExW',return_value=1),patch.object(native.u,'UnhookWindowsHookEx',return_value=True),patch.object(native.u,'CallNextHookEx',return_value=0) as next_hook:
            e._install_hooks()
            self.assertEqual(e._mouse_cb(0,0x201,ctypes.addressof(mouse)),1)
            self.assertTrue(e._selection['button_down'])
            mouse.pt.x=900
            self.assertEqual(e._mouse_cb(0,0x202,ctypes.addressof(mouse)),1)
            self.assertIsNotNone(e._selection)
            self.assertEqual(e._selection['model'].rect,dict(x=84,y=84,w=32,h=32))
            self.assertIsNone(e._pending_finish)
            self.assertFalse(e._selection['button_down'])
            key=native.Keyboard(13,0,0,0,0)
            e._key_cb(0,0x100,ctypes.addressof(key));e._key_cb(0,0x101,ctypes.addressof(key))
            self._assert_deferred_finish(e)
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
    @unittest.skipUnless(sys.platform=='win32','Win32 selection renderer')
    def test_selection_4k_uses_small_strips_and_no_upload_on_movement(self):
        import ctypes
        class FakeSurface:
            def __init__(self,*args,**kwargs):self.hwnd=id(self);self.appearance=None;self.positions=[];self.updates=[]
            def hide(self):pass
            def position(self,*args):self.positions.append(args)
            def update(self,*args):self.updates.append(args)
        e=MirrorEngine();e.hwnd=100
        context=dict(w=3840,h=2160,dpi=96)
        s=Selection('manual',context,{'origem':dict(x=100,y=100,w=2000,h=1000)})
        def cursor(point):
            pt=ctypes.cast(point,ctypes.POINTER(native.W.POINT)).contents;pt.x=200;pt.y=200;return True
        with patch.object(native,'Surface',FakeSurface),patch.object(native.u,'GetCursorPos',side_effect=cursor),patch.object(native.layered_image,'mostrar') as upload:
            e._draw_selection(dict(context,x=0,y=0),s)
            self.assertEqual(upload.call_count,14)
            self.assertEqual(e._surfaces['loupe'][0].updates[-1],(dict(x=184,y=184,w=32,h=32),200,200))
            shaded=sum(p[-1][2]*p[-1][3] for p in (surface.positions for surface in e._surfaces['shade']) if p)
            self.assertEqual(shaded,context['w']*context['h']-s.rect['w']*s.rect['h'])
            self.assertLess(sum(call.args[1].width*call.args[1].height for call in upload.call_args_list),100000)
            self.assertTrue(all(call.args[1].width<context['w'] for call in upload.call_args_list))
            upload.reset_mock();s.key('right');e._draw_selection(dict(context,x=0,y=0),s)
            upload.assert_not_called()
        e._surfaces.clear();e.close()
    @unittest.skipUnless(sys.platform=='win32','Win32 Enter hook')
    def test_enter_release_finishes_manual_selection_and_delivers_crop(self):
        import ctypes
        from unittest.mock import Mock
        e=MirrorEngine();e.hwnd=100
        rect=dict(x=10,y=20,w=120,h=80)
        e._selection={'active':True,'model':Selection('manual',dict(w=800,h=600,dpi=96),{'origem':rect})}
        callback=Mock();e._callback=callback
        key=native.Keyboard(13,0,0,0,0)
        with patch.object(native.u,'GetForegroundWindow',return_value=100),patch.object(native.u,'GetAsyncKeyState',return_value=0),patch.object(native.u,'SetWindowsHookExW',return_value=1),patch.object(native.u,'UnhookWindowsHookEx',return_value=True),patch.object(native.u,'CallNextHookEx',return_value=0) as next_hook:
            e._install_hooks()
            self.assertEqual(e._key_cb(0,0x100,ctypes.addressof(key)),1)
            self.assertIsNotNone(e._selection)
            self.assertEqual(e._key_cb(0,0x101,ctypes.addressof(key)),1)
            self.assertIsNotNone(e._selection);self.assertIsNotNone(e._pending_finish)
            self._assert_deferred_finish(e);self.assertEqual(e._hooks,[])
            next_hook.assert_not_called()
        delivered,args=e._events.get_nowait()
        self.assertIs(delivered,callback);self.assertEqual(args[0]['origem'],rect)
        e.close()
    @unittest.skipUnless(sys.platform=='win32','Win32 initial manual guidance')
    def test_manual_shows_full_dim_and_hint_before_first_drag(self):
        import ctypes
        class FakeSurface:
            def __init__(self,*args,**kwargs):self.hwnd=id(self);self.appearance=None;self.positions=[]
            def position(self,*args):self.positions.append(args)
            def update(self,*args):pass
            def hide(self):pass
        engine=MirrorEngine();engine.hwnd=100
        context=dict(x=-1920,y=100,w=1920,h=1080,dpi=96)
        model=Selection('manual',{key:context[key] for key in ('w','h','dpi')})
        def cursor(point):
            pt=ctypes.cast(point,ctypes.POINTER(native.W.POINT)).contents;pt.x=-1500;pt.y=300;return True
        with patch.object(native,'Surface',FakeSurface),patch.object(native.u,'GetCursorPos',side_effect=cursor),patch.object(native.u,'SetWindowPos'),patch.object(native.layered_image,'mostrar') as upload:
            engine._draw_selection(context,model)
            self.assertIsNone(model.rect)
            self.assertEqual(engine._surfaces['shade'][0].positions[-1],(-1920,100,1920,1080))
            self.assertTrue(engine._surfaces['selector'][4].positions)
            self.assertNotIn('handles',engine._surfaces)
            self.assertLess(sum(call.args[1].width*call.args[1].height for call in upload.call_args_list),100000)
        engine._surfaces.clear();engine.close()
    def test_manual_handles_resize_and_interior_moves_without_new_selection(self):
        context=dict(w=800,h=600,dpi=144)
        expected=((40,50,140,80),(100,50,80,80),(100,50,141,80),(40,100,140,30),
                  (100,100,141,30),(40,100,140,151),(100,100,80,151),(100,100,141,151))
        from mirror_selector import handles
        for index,point in enumerate(handles(dict(x=100,y=100,w=80,h=30))):
            model=Selection('manual',context,{'origem':dict(x=100,y=100,w=80,h=30)})
            model.mouse('down',*point)
            x=40 if index in (0,3,5) else 240
            y=50 if index in (0,1,2) else 250
            model.mouse('up',x,y)
            self.assertEqual(tuple(model.rect[k] for k in ('x','y','w','h')),expected[index])
        model=Selection('manual',context,{'origem':dict(x=100,y=100,w=80,h=30)})
        model.mouse('down',130,115);model.mouse('up',150,135)
        self.assertEqual(model.rect,dict(x=120,y=120,w=80,h=30))
    def test_square_placement_stays_still_until_reposition_or_confirmation(self):
        model=Selection('quadrado',dict(w=800,h=600,dpi=192))
        self.assertIsNone(model.mouse('down',100,100));model.mouse('up',100,100)
        model.move(400,400);self.assertEqual(model.rect,dict(x=84,y=84,w=32,h=32))
        self.assertEqual(model.key('enter')['origem'],dict(x=84,y=84,w=32,h=32))
    @unittest.skipUnless(sys.platform=='win32','Win32 wake and coalescence')
    def test_command_wakes_worker_and_mouse_moves_only_mark_dirty(self):
        import ctypes
        from unittest.mock import Mock
        engine=MirrorEngine();engine.hwnd=100;engine._thread_id=42
        with patch.object(native.u,'PostThreadMessageW') as wake:
            engine._command('cancel',None);wake.assert_called_once_with(42,0x8001,0,0)
        engine._selection=dict(active=True,model=Selection('quadrado',dict(w=800,h=600,dpi=96)),geometry=dict(x=-800,y=100,w=800,h=600,dpi=96))
        mouse=native.Mouse(native.W.POINT(-700,200),0,0,0,0)
        with patch.object(native.u,'GetForegroundWindow',return_value=100),patch.object(native.u,'SetWindowsHookExW',return_value=1),patch.object(native.u,'UnhookWindowsHookEx'),patch.object(native.u,'CallNextHookEx',return_value=0),patch.object(engine,'_draw_selection') as draw,patch.object(native.layered_image,'mostrar') as upload:
            engine._install_hooks()
            for x in range(-700,-600):
                mouse.pt.x=x;engine._mouse_cb(0,0x200,ctypes.addressof(mouse))
            self.assertTrue(engine._selection_dirty)
            self.assertEqual(engine._selection['model'].rect,dict(x=183,y=84,w=32,h=32))
            draw.assert_not_called();upload.assert_not_called();self.assertTrue(engine._commands.empty() is False)
            engine._finish()
        engine.close()
    @unittest.skipUnless(sys.platform=='win32','Win32 selection cleanup')
    def test_finish_closes_shade_handles_guides_and_loupe(self):
        from unittest.mock import Mock
        engine=MirrorEngine();engine._selection=dict(active=True);engine._hooks=[1,2]
        surfaces=[Mock() for _ in range(4)]
        engine._surfaces=dict(zip(('shade','handles','selector','loupe'),[(surface,) for surface in surfaces]))
        with patch.object(native.u,'UnhookWindowsHookEx') as unhook:
            engine._finish();self.assertEqual(unhook.call_count,2)
        for surface in surfaces:surface.close.assert_called_once()
        self.assertEqual(engine._surfaces,{});self.assertFalse(engine._selection_dirty)
        engine.close()
    @unittest.skipUnless(sys.platform=='win32','Win32 wait')
    def test_worker_waits_for_input_instead_of_sleeping_after_messages(self):
        engine=MirrorEngine()
        with patch.object(native.u,'MsgWaitForMultipleObjectsEx') as wait:
            def finish(*args):engine._command('close',None);return 0
            wait.side_effect=finish
            engine._worker()
        wait.assert_called_once_with(0,None,25,0x04ff,4)
        self.assertEqual(engine.status()['estado'],'encerrado')
        self.assertEqual(engine._thread_id,0)
    def _assert_deferred_finish(self,e):
        self.assertIsNotNone(e._pending_finish)
        e._finish(e._pending_finish[0])
        self.assertIsNone(e._selection)
    def test_status_is_defensive(self):
        e=MirrorEngine();state=e.status();state['hwnd']=1;self.assertEqual(e.status()['hwnd'],0);e.close()
if __name__=='__main__':unittest.main()
