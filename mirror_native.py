"""Thread-owned DWM mirrors. Every coordinate is a physical client pixel."""
import ctypes, os, sys, threading, queue, copy
from ctypes import wintypes as W
from mirror_selector import Selection, clamp_rect, mouse_policy, handles
from mirror_visual import frame, selection_hint

WIN=sys.platform=='win32'
if WIN:
    import overlay as O
    import layered_image
    u,k,d=ctypes.windll.user32,ctypes.windll.kernel32,ctypes.windll.dwmapi
    CB=ctypes.WINFUNCTYPE(ctypes.c_ssize_t,ctypes.c_int,W.WPARAM,W.LPARAM)
    for name,args,result in [('WindowFromPoint',[W.POINT],W.HWND),('GetAncestor',[W.HWND,W.UINT],W.HWND),('PostThreadMessageW',[W.DWORD,W.UINT,W.WPARAM,W.LPARAM],W.BOOL),('MsgWaitForMultipleObjectsEx',[W.DWORD,ctypes.c_void_p,W.DWORD,W.DWORD,W.DWORD],W.DWORD),('UnregisterClassW',[W.LPCWSTR,W.HINSTANCE],W.BOOL),('PeekMessageW',[ctypes.c_void_p,W.HWND,W.UINT,W.UINT,W.UINT],W.BOOL),('IsWindow',[W.HWND],W.BOOL),('SetCapture',[W.HWND],W.HWND),('GetWindowTextW',[W.HWND,W.LPWSTR,ctypes.c_int],ctypes.c_int),('ClientToScreen',[W.HWND,ctypes.POINTER(W.POINT)],W.BOOL),('DestroyWindow',[W.HWND],W.BOOL),('GetDpiForWindow',[W.HWND],W.UINT),('SetWindowsHookExW',[ctypes.c_int,CB,W.HINSTANCE,W.DWORD],W.HANDLE),('UnhookWindowsHookEx',[W.HANDLE],W.BOOL),('CallNextHookEx',[W.HANDLE,ctypes.c_int,W.WPARAM,W.LPARAM],ctypes.c_ssize_t)]:
        f=getattr(u,name);f.argtypes=args;f.restype=result
    d.DwmExtendFrameIntoClientArea.argtypes=[W.HWND,ctypes.c_void_p]
    d.DwmRegisterThumbnail.argtypes=[W.HWND,W.HWND,ctypes.POINTER(W.HANDLE)]
    d.DwmUnregisterThumbnail.argtypes=[W.HANDLE]
    d.DwmUpdateThumbnailProperties.argtypes=[W.HANDLE,ctypes.c_void_p]
    class Props(ctypes.Structure):
        _fields_=[('flags',W.DWORD),('destination',W.RECT),('source',W.RECT),('opacity',ctypes.c_ubyte),('visible',W.BOOL),('client',W.BOOL)]
    class Mouse(ctypes.Structure):
        _fields_=[('pt',W.POINT),('data',W.DWORD),('flags',W.DWORD),('time',W.DWORD),('extra',ctypes.c_size_t)]
    class Keyboard(ctypes.Structure):
        _fields_=[('key',W.DWORD),('scan',W.DWORD),('flags',W.DWORD),('time',W.DWORD),('extra',ctypes.c_size_t)]

def geometry(hwnd):
    if not WIN or not u.IsWindow(hwnd) or u.IsIconic(hwnd):return None
    rect=W.RECT();point=W.POINT()
    if not u.GetClientRect(hwnd,ctypes.byref(rect)) or not u.ClientToScreen(hwnd,ctypes.byref(point)):return None
    return dict(x=point.x,y=point.y,w=rect.right,h=rect.bottom,dpi=u.GetDpiForWindow(hwnd) or 96)

def compatible(c,g):
    return bool(g) and all(c.get(key)==g.get(key) for key in ('w','h','dpi'))

def list_clients():
    if not WIN:return []
    found=[]
    def visit(hwnd,_):
        if not u.IsWindowVisible(hwnd):return True
        pid=W.DWORD();u.GetWindowThreadProcessId(hwnd,ctypes.byref(pid));handle=k.OpenProcess(0x1000,False,pid.value)
        if handle:
            try:
                path=ctypes.create_unicode_buffer(520);length=W.DWORD(520)
                if k.QueryFullProcessImageNameW(handle,0,path,ctypes.byref(length)) and os.path.basename(path.value).lower() in O.PROCESSOS_TIBIA:
                    title=ctypes.create_unicode_buffer(520);u.GetWindowTextW(hwnd,title,520)
                    found.append(dict(hwnd=int(hwnd),titulo=title.value))
            finally:k.CloseHandle(handle)
        return True
    cb=ctypes.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM)(visit);u.EnumWindows(cb,0)
    return found

class Surface:
    def __init__(self,engine,source,layered=False,shade=False):
        self.engine=engine;self.thumbnail=None;self.appearance=None;self._position=None;self._update=None;self._style=None;self.shown=False;self.locked=True
        ex=0x08000000|0x80|0x8|0x20|0x80000
        self.hwnd=u.CreateWindowExW(ex,engine.classname+('Shade' if shade else ''),'Mirror',0x80000000,0,0,10,10,None,None,k.GetModuleHandleW(None),None)
        if not self.hwnd:raise ctypes.WinError()
        if shade:u.SetLayeredWindowAttributes(self.hwnd,0,80,2)
        if source:
            u.SetLayeredWindowAttributes(self.hwnd,0,255,2)
            # Full glass frame gives the thumbnail alpha a transparent compositor host.
            margins=(ctypes.c_int*4)(-1,-1,-1,-1);d.DwmExtendFrameIntoClientArea(self.hwnd,ctypes.byref(margins))
            self.thumbnail=W.HANDLE()
            hr=d.DwmRegisterThumbnail(self.hwnd,source,ctypes.byref(self.thumbnail))
            if hr:
                self.close();raise RuntimeError('DWM thumbnail: 0x%08x'%(hr&0xffffffff))
    def position(self,x,y,w,h):
        position=tuple(map(int,(x,y,w,h)))
        if position!=self._position or not self.shown:
            u.SetWindowPos(self.hwnd,W.HWND(-1),*position,0x10|0x40);self._position=position;self.shown=True
    def hide(self):
        if self.shown:u.ShowWindow(self.hwnd,0);self.shown=False
    def set_locked(self,locked):
        style=0x08000000|0x80|0x8|0x80000|(0x20 if locked else 0)
        self.locked=locked
        if style!=self._style:
            setter=getattr(u,'SetWindowLongPtrW',u.SetWindowLongW);setter.argtypes=[W.HWND,ctypes.c_int,ctypes.c_ssize_t];setter.restype=ctypes.c_ssize_t
            setter(self.hwnd,-20,style);self._style=style
    def update(self,r,w,h,alpha=255):
        parameters=(r['x'],r['y'],r['w'],r['h'],w,h,alpha)
        if parameters==self._update:return
        p=Props(31,W.RECT(0,0,w,h),W.RECT(r['x'],r['y'],r['x']+r['w'],r['y']+r['h']),alpha,True,True)
        hr=d.DwmUpdateThumbnailProperties(self.thumbnail,ctypes.byref(p))
        if hr:raise RuntimeError('DWM update failed')
        self._update=parameters
    def close(self):
        if self.thumbnail:d.DwmUnregisterThumbnail(self.thumbnail);self.thumbnail=None
        if self.hwnd:u.DestroyWindow(self.hwnd);self.hwnd=None

class MirrorEngine:
    def __init__(self,on_change=None,on_move=None):
        self._events=queue.Queue();self._event_thread=None;self._lock=threading.RLock();self._closed=False;self.on_change=on_change;self.on_move=on_move;self._commands=queue.Queue();self._thread=None;self._thread_id=0;self._selection_dirty=False;self._pending_finish=None
        self._state=dict(hwnd=0,estado='sem_cliente',motivo='',selecionando=False,recortes=[])
        self.character='';self.profile=None;self.hwnd=0;self._source_pid=None;self._selection=None;self._callback=None;self._surfaces={};self._hooks=[];self._drag=None
    def _start(self):
        with self._lock:
            if self._closed:return
            if not self._thread or not self._thread.is_alive():
                if not self._event_thread or not self._event_thread.is_alive():
                    self._event_thread=threading.Thread(target=self._dispatch,daemon=True,name='Mirror callbacks');self._event_thread.start()
                self._thread=threading.Thread(target=self._run,daemon=True,name='Mirror DWM');self._thread.start()
    def _dispatch(self):
        while True:
            event=self._events.get()
            if event is None:return
            callback,args=event
            if not self._closed:
                try:callback(*args)
                except Exception:pass
    def _emit(self,callback,*args):
        if callback and not self._closed:self._events.put((callback,args))
    def _command(self,op,value):
        self._commands.put((op,value))
        if self._thread_id:u.PostThreadMessageW(self._thread_id,0x8001,0,0)
    def _end_selection(self,result=None):
        self._pending_finish=(result,)
        self._selection_dirty=True
    def configure(self,character,profile):
        if self._closed:return
        self._start();barrier=threading.Event();self._command('configure',(character,copy.deepcopy(profile),barrier))
        if threading.current_thread() is not self._thread:barrier.wait(1)
    def bind_window(self,hwnd):
        if self._closed:return dict(ok=False,erro='Mirror encerrado')
        if int(hwnd) not in [c['hwnd'] for c in list_clients()]:return dict(ok=False,erro='Cliente Tibia inválido')
        self._start();barrier=threading.Event();self._command('bind',(int(hwnd),barrier))
        if threading.current_thread() is not self._thread:barrier.wait(1)
        return dict(ok=True,hwnd=int(hwnd))
    def select(self,mode,on_result,existing=None):
        if self._closed:return dict(ok=False,erro='Mirror encerrado')
        if not self.hwnd or self.hwnd not in [c['hwnd'] for c in list_clients()]:return dict(ok=False,erro='Vincule um cliente Tibia valido')
        if mode not in ('quadrado','manual'):return dict(ok=False,erro='Modo inválido')
        self._start();self._command('select',(mode,on_result,copy.deepcopy(existing)));return dict(ok=True,pendente=True)
    def cancel_selection(self):
        if not self._closed:self._command('cancel',None)
        return dict(ok=True)
    def status(self):return copy.deepcopy(self._state)
    def close(self):
        self._closed=True
        if self._thread and self._thread.is_alive():self._command('close',None);self._thread.join(3)
        self._events.put(None)
    def _notify(self,state):
        if state!=self._state:
            self._state=state
            self._emit(self.on_change,copy.deepcopy(state))
    def _clear(self):
        for pair in self._surfaces.values():
            for surface in pair:surface.close()
        self._surfaces.clear()
    def _finish(self,result=None):
        self._selection=None;self._pending_finish=None;self._selection_dirty=False
        if self._drag:u.ReleaseCapture();self._drag=None
        for hook in self._hooks:u.UnhookWindowsHookEx(hook)
        self._hooks=[]
        for key in ('selector','loupe','shade','handles'):
            for surface in self._surfaces.pop(key,[]):surface.close()
        callback=self._callback;self._callback=None
        self._emit(callback,result)
    def _install_hooks(self):
        # Pair releases even when the activating press predates hook installation.
        self._selection['pass_release']=bool(u.GetAsyncKeyState(1)&0x8000)
        if self._selection.get('active') and not self._selection.get('geometry'):self._selection['geometry']=geometry(self.hwnd)
        def mouse(code,msg,lp):
            selection=self._selection
            if code<0 or not selection:return u.CallNextHookEx(None,code,msg,lp)
            m=ctypes.cast(lp,ctypes.POINTER(Mouse)).contents
            focused=u.GetForegroundWindow()==self.hwnd
            if not selection.get('active'):
                if msg==0x201:
                    selection['pass_release']=True
                    if u.GetAncestor(u.WindowFromPoint(m.pt),2)==self.hwnd:selection['activation_mouse_seen']=True
                elif msg==0x202:selection['pass_release']=False
                return u.CallNextHookEx(None,code,msg,lp)
            if selection.get('pass_release'):
                if msg==0x202:selection['pass_release']=False
                return u.CallNextHookEx(None,code,msg,lp)
            if msg==0x201 and selection.pop('ignore_next_down',False):
                selection['pass_release']=True
                return u.CallNextHookEx(None,code,msg,lp)
            paired=msg==0x202 and bool(selection.get('button_down'))
            if not focused and not paired:return u.CallNextHookEx(None,code,msg,lp)
            g=selection.get('geometry')
            if not g:
                self._end_selection();return u.CallNextHookEx(None,code,msg,lp)
            x,y=m.pt.x-g['x'],m.pt.y-g['y'];model=selection['model']
            inside=0<=x<g['w'] and 0<=y<g['h']
            if paired:selection['button_down']=False
            card=selection.get('card')
            action=next((name for name,box in (card or {}).items() if box[0]<=x<box[2] and box[1]<=y<box[3]),None)
            if msg==0x201 and action:
                selection['button_down']=True;selection['card_press']=action;return 1
            if paired and selection.get('card_press'):
                pressed=selection.pop('card_press')
                if focused and action==pressed:
                    if action=='cancel':self._end_selection()
                    elif model.can_confirm():self._end_selection(model.result())
                return 1
            if paired and not inside:
                if model.mode=='manual':self._end_selection()
                return 1
            if mouse_policy(x,y,g,paired)=='cancel_pass':
                if msg!=0x200:self._end_selection()
                return u.CallNextHookEx(None,code,msg,lp)
            if msg in (0x201,0x202,0x20a,0x200):
                if action and paired:
                    model.mouse('up',x,y);self._selection_dirty=True;return 1
                if action or selection.get('card_press'):return 1 if msg!=0x200 else u.CallNextHookEx(None,code,msg,lp)
                event={0x201:'down',0x202:'up',0x20a:'wheel',0x200:'move'}[msg]
                if msg==0x201:selection['button_down']=True
                model.mouse(event,x,y,ctypes.c_short(m.data>>16).value)
                self._selection_dirty=True
            if msg!=0x200:return 1
            return u.CallNextHookEx(None,code,msg,lp)
        def keyboard(code,msg,lp):
            if code>=0 and self._selection and not self._selection.get('active'):
                key=ctypes.cast(lp,ctypes.POINTER(Keyboard)).contents.key
                if key==9 and msg in (0x100,0x104) and u.GetAsyncKeyState(18)&0x8000:self._selection['keyboard_focus']=True
            if code>=0 and self._selection and self._selection.get('active') and u.GetForegroundWindow()==self.hwnd:
                key=ctypes.cast(lp,ctypes.POINTER(Keyboard)).contents.key
                names={27:'escape',13:'enter',37:'left',38:'up',39:'right',40:'down'}
                if key in names:
                    selection=self._selection
                    if msg in (0x100,0x104) and not selection.get('key_release'):
                        model=selection['model'];result=model.key(names[key],bool(u.GetAsyncKeyState(16)&0x8000),bool(u.GetAsyncKeyState(17)&0x8000))
                        self._selection_dirty=True
                        if model.done:selection['key_release']=(key,result)
                    elif msg in (0x101,0x105) and selection.get('key_release') and selection['key_release'][0]==key:
                        self._end_selection(selection['key_release'][1])
                    return 1
            return u.CallNextHookEx(None,code,msg,lp)
        self._mouse_cb=CB(mouse);self._key_cb=CB(keyboard)
        for kind,cb in ((14,self._mouse_cb),(13,self._key_cb)):
            hook=u.SetWindowsHookExW(kind,cb,k.GetModuleHandleW(None),0)
            if not hook:
                self._finish();raise ctypes.WinError()
            self._hooks.append(hook)
    def _run(self):
        try:self._worker()
        except Exception as error:
            self._finish();self._clear();self._notify(dict(self._state,estado='erro',motivo=str(error),selecionando=False))
    def _worker(self):
        if not WIN:self._notify(dict(self._state,estado='indisponivel',motivo='Windows necessário'));return
        # Thread-specific PMv2 eliminates DPI virtualisation without changing the host UI.
        if hasattr(u,'SetThreadDpiAwarenessContext'):
            u.SetThreadDpiAwarenessContext.argtypes=[ctypes.c_void_p];u.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))
        self.classname='ZandaoMirror'+str(id(self))
        def proc(hwnd,msg,wp,lp):
            if msg==0x21:return 3 # MA_NOACTIVATE
            if msg==0x201:
                for rid,pair in self._surfaces.items():
                    if rid in ('selector','loupe','shade','handles'):continue
                    if pair[0].hwnd==hwnd and not pair[0].locked:
                        point=W.POINT();u.GetCursorPos(ctypes.byref(point));self._drag=(rid,point.x,point.y);u.SetCapture(hwnd);return 0
            if msg==0x200 and self._drag:
                rid,x,y=self._drag;point=W.POINT();u.GetCursorPos(ctypes.byref(point))
                for item in (self.profile or {}).get('recortes',[]):
                    if item['id']==rid:item['destino']['x']+=point.x-x;item['destino']['y']+=point.y-y;self._drag=(rid,point.x,point.y)
                return 0
            if msg==0x202 and self._drag:
                rid=self._drag[0];self._drag=None;u.ReleaseCapture()
                item=next((i for i in self.profile['recortes'] if i['id']==rid),None)
                if item:self._emit(self.on_move,rid,dict(item['destino']))
                return 0
            return u.DefWindowProcW(hwnd,msg,wp,lp)
        self._wndproc=O.WNDPROC(proc);wc=O._WNDCLASS();wc.lpfnWndProc=self._wndproc;wc.hInstance=k.GetModuleHandleW(None);wc.lpszClassName=self.classname
        if not u.RegisterClassW(ctypes.byref(wc)):raise ctypes.WinError()
        wc.lpszClassName=self.classname+'Shade'
        O._g32.GetStockObject.argtypes=[ctypes.c_int];O._g32.GetStockObject.restype=W.HBRUSH
        wc.hbrBackground=O._g32.GetStockObject(4)
        if not u.RegisterClassW(ctypes.byref(wc)):raise ctypes.WinError()
        self._thread_id=k.GetCurrentThreadId()
        message=W.MSG()
        try:
            running=True
            while running:
                while u.PeekMessageW(ctypes.byref(message),None,0,0,1):u.TranslateMessage(ctypes.byref(message));u.DispatchMessageW(ctypes.byref(message))
                while not self._commands.empty():
                    op,value=self._commands.get()
                    if op=='close':running=False;break
                    if op=='cancel':self._finish();continue
                    self._finish();self._clear()
                    if op=='configure':
                        self.character,self.profile,barrier=value;barrier.set()
                    elif op=='bind':
                        self.hwnd,barrier=value
                        pid=W.DWORD();u.GetWindowThreadProcessId(self.hwnd,ctypes.byref(pid));self._source_pid=pid.value
                        barrier.set()
                    elif op=='select':
                        mode,self._callback,existing=value;self._selection=dict(mode=mode,existing=existing,active=False);self._install_hooks()
                if self._pending_finish is not None:self._finish(self._pending_finish[0])
                if running:
                    try:self._tick()
                    except Exception as error:
                        self._finish();self._clear();self._notify(dict(self._state,estado='erro',motivo=str(error)))
                if running:u.MsgWaitForMultipleObjectsEx(0,None,25,0x04ff,4)
        finally:self._finish();self._clear();self._notify(dict(self._state,estado='encerrado',selecionando=False));u.UnregisterClassW(self.classname+'Shade',k.GetModuleHandleW(None));u.UnregisterClassW(self.classname,k.GetModuleHandleW(None));self._thread_id=0
    def _tick(self):
        g=geometry(self.hwnd)
        if self._source_pid is not None:
            pid=W.DWORD();u.GetWindowThreadProcessId(self.hwnd,ctypes.byref(pid))
            if pid.value!=self._source_pid:
                self._finish();self._clear();self.hwnd=0;self._source_pid=None;g=None
        foreground=u.GetForegroundWindow()
        focused=bool(g and foreground==self.hwnd and u.IsWindowVisible(self.hwnd))
        editing=bool(g and foreground and foreground==O._hwnd_app_fixado and u.GetWindowLongW(foreground,-20)&O.WS_EX_TOPMOST and u.IsWindowVisible(self.hwnd))
        visible=focused or editing
        if self._selection:
            s=self._selection
            if s['active'] and not focused:self._finish()
            elif focused:
                if s.get('geometry')!=g:self._selection_dirty=True
                s['geometry']=g
                if not s['active']:
                    s['model']=Selection(s['mode'],{key:g[key] for key in ('w','h','dpi')},s['existing']);s['active']=True
                    # Foreground can change before the activation mouse callback arrives.
                    s['ignore_next_down']=not (s.get('activation_mouse_seen') or s.get('keyboard_focus') or s.get('pass_release'))
                if not compatible(s['model'].context,g):self._finish()
                elif self._selection_dirty:
                    self._draw_selection(g,s['model']);self._selection_dirty=False
        paused=[]
        for item in (self.profile or {}).get('recortes',[]):
            rid=item['id'];valid=compatible(item.get('contexto',{}),g)
            r=item['origem']
            valid=valid and r['x']>=0 and r['y']>=0 and r['w']>0 and r['h']>0 and r['x']+r['w']<=g['w'] and r['y']+r['h']<=g['h']
            if not valid:paused.append(rid)
            if not visible and self._drag:u.ReleaseCapture();self._drag=None
            show=visible and self.character and valid and item.get('visivel',True) and not self._selection
            pair=self._surfaces.get(rid)
            if not show:
                if pair:
                    for surface in pair:surface.hide()
                continue
            r=item['origem'];scale=item.get('escala',1);w,h=max(1,min(4096,round(r['w']*scale))),max(1,min(4096,round(r['h']*scale)))
            margin_limit=max(12,round(20*g['dpi']/96));title_limit=max(20,round(22*g['dpi']/96)) if item.get('mostrar_nome') else 0
            w=min(w,max(1,g['w']-2*margin_limit));h=min(h,max(1,g['h']-2*margin_limit-title_limit))
            margin_est=max(12,round(20*g['dpi']/96));title_est=max(20,round(22*g['dpi']/96)) if item.get('mostrar_nome') else 0
            dest=clamp_rect(item['destino']['x']-margin_est,item['destino']['y']-margin_est-title_est,w+2*margin_est,h+2*margin_est+title_est,(g['w'],g['h']))
            dest['x']+=margin_est;dest['y']+=margin_est+title_est
            if not pair:pair=(Surface(self,self.hwnd),Surface(self,None,True));self._surfaces[rid]=pair
            image,margin,title=frame(w,h,item.get('glow',{}).get('cor','#51cfff'),item.get('glow',{}).get('intensidade','off'),item.get('nome','') if item.get('mostrar_nome') else '',g['dpi'])
            pair[0].update(r,w,h,round(item.get('opacidade',1)*255));pair[0].position(g['x']+dest['x'],g['y']+dest['y'],w,h)
            pair[0].set_locked(item.get('travado',True))
            pair[1].position(g['x']+dest['x']-margin,g['y']+dest['y']-margin-title,image.width,image.height)
            if pair[1].appearance is not image:
                layered_image.mostrar(pair[1].hwnd,image);pair[1].appearance=image
        state='selecionando' if self._selection and self._selection['active'] else 'aguardando_foco' if self._selection else 'sem_cliente' if not g else 'pausado' if paused else 'ativo' if visible and self.character else 'oculto'
        self._notify(dict(hwnd=self.hwnd,estado=state,motivo='Reposicionar recorte: geometria/DPI mudou' if paused else '',selecionando=bool(self._selection),recortes_pausados=paused))
    def _draw_selection(self,g,s):
        from PIL import Image
        point=W.POINT();u.GetCursorPos(ctypes.byref(point));x,y=point.x-g['x'],point.y-g['y']
        if s.rect is None:s.move(x,y)
        elif s.pointer:x,y=s.pointer
        r=s.rect
        shades=self._surfaces.get('shade')
        if not shades:
            shades=[Surface(self,None,shade=True) for _ in range(4)];self._surfaces['shade']=shades
        regions=((0,0,g['w'],r['y']),(0,r['y']+r['h'],g['w'],g['h']-r['y']-r['h']),
                 (0,r['y'],r['x'],r['h']),(r['x']+r['w'],r['y'],g['w']-r['x']-r['w'],r['h'])) if r else ((0,0,g['w'],g['h']),)+( (0,0,0,0),)*3
        for surface,(left,top,width,height) in zip(shades,regions):
            if width and height:surface.position(g['x']+left,g['y']+top,width,height)
            else:surface.hide()
        edges=self._surfaces.get('selector')
        if not edges:
            edges=[];self._surfaces['selector']=edges
            for _ in range(5):edges.append(Surface(self,None,True))
        if r:
            # Four one-pixel strips replace a client-sized RGBA bitmap per frame.
            # Moving a square only moves HWNDs; it never uploads another full image.
            lines=((r['x'],r['y'],r['w'],1),
                   (r['x'],r['y']+r['h']-1,r['w'],1),
                   (r['x'],r['y'],1,r['h']),
                   (r['x']+r['w']-1,r['y'],1,r['h']))
            for surface,(left,top,width,height) in zip(edges[:4],lines):
                key=(width,height)
                if surface.appearance!=key:
                    layered_image.mostrar(surface.hwnd,Image.new('RGBA',key,'white'))
                    surface.appearance=key
                surface.position(g['x']+left,g['y']+top,width,height)
            if s.mode=='manual':
                grips=self._surfaces.get('handles')
                if not grips:grips=[Surface(self,None,True) for _ in range(8)];self._surfaces['handles']=grips
                for surface,(hx,hy) in zip(grips,handles(r)):
                    if surface.appearance is None:
                        layered_image.mostrar(surface.hwnd,Image.new('RGBA',(7,7),'#ff7033'));surface.appearance=True
                    surface.position(g['x']+max(0,min(hx-3,g['w']-7)),g['y']+max(0,min(hy-3,g['h']-7)),7,7)
        hint,confirm,cancel=selection_hint(g['dpi'],s.mode,s.can_confirm(),g['w'])
        hint_surface=edges[4]
        if hint_surface.appearance is not hint:
            layered_image.mostrar(hint_surface.hwnd,hint);hint_surface.appearance=hint
        hx=max(0,(g['w']-hint.width)//2);hy=min(12,max(0,g['h']-hint.height))
        hint_surface.position(g['x']+hx,g['y']+hy,hint.width,hint.height)
        if self._selection:
            self._selection['card']={name:(box[0]+hx,box[1]+hy,box[2]+hx,box[3]+hy) for name,box in (('confirm',confirm),('cancel',cancel))}
        loupe=self._surfaces.get('loupe')
        if not loupe:loupe=(Surface(self,self.hwnd),Surface(self,None,True));self._surfaces['loupe']=loupe
        region=dict(r) if s.mode=='quadrado' else clamp_rect(x-16,y-16,32,32,(g['w'],g['h']))
        loupe[0].update(region,200,200)
        lx=point.x+28;ly=point.y+28
        if lx+200>g['x']+g['w']:lx=point.x-228
        if ly+200>g['y']+g['h']:ly=point.y-228
        lx=max(g['x']+1,min(lx,g['x']+g['w']-201));ly=max(g['y']+1,min(ly,g['y']+g['h']-201))
        if lx-1<g['x']+hx+hint.width and lx+201>g['x']+hx and ly-1<g['y']+hy+hint.height and ly+201>g['y']+hy:
            ly=min(g['y']+g['h']-201,g['y']+hy+hint.height+9)
        loupe[0].position(lx,ly,200,200)
        if loupe[1].appearance is None:
            border=Image.new('RGBA',(202,202),'#ff7033')
            border.paste((0,0,0,0),(1,1,201,201))
            layered_image.mostrar(loupe[1].hwnd,border);loupe[1].appearance=True
        loupe[1].position(lx-1,ly-1,202,202)
        # Keep guides above the dim panels after a panel changes size/position.
        for key in ('selector','handles','loupe'):
            for surface in self._surfaces.get(key,()):
                u.SetWindowPos(surface.hwnd,W.HWND(-1),0,0,0,0,0x10|0x01|0x02)
