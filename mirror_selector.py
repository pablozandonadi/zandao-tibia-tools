"""Pure physical-coordinate selector state, independent of Win32 hooks."""
def clamp_rect(x,y,w,h,bounds):
    bw,bh=bounds
    w,h=max(1,min(int(w),bw)),max(1,min(int(h),bh))
    return dict(x=max(0,min(int(x),bw-w)),y=max(0,min(int(y),bh-h)),w=w,h=h)

def handles(rect):
    x,y,w,h=(rect[k] for k in ('x','y','w','h'))
    return [(x,y),(x+w//2,y),(x+w-1,y),(x,y+h//2),
            (x+w-1,y+h//2),(x,y+h-1),(x+w//2,y+h-1),(x+w-1,y+h-1)]

class Selection:
    def __init__(self,mode,context,existing=None):
        self.mode=mode; self.context=context; self.size=32; self.anchor=None
        self.rect=dict((existing or {}).get('origem') or {}) or None
        self.dragging=False; self.done=False; self.placed=bool(self.rect); self.pointer=None; self.operation=None
        if mode=='quadrado' and self.rect:self.size=self.rect['w']
    def move(self,x,y):
        x=max(0,min(x,self.context['w']-1));y=max(0,min(y,self.context['h']-1));self.pointer=(x,y)
        bounds=(self.context['w'],self.context['h'])
        if self.mode=='quadrado' and not self.placed:
            self.rect=clamp_rect(x-self.size//2,y-self.size//2,self.size,self.size,bounds)
        elif self.dragging:
            ax,ay=self.anchor
            if self.operation=='move':
                r=self.original;self.rect=clamp_rect(r['x']+x-ax,r['y']+y-ay,r['w'],r['h'],bounds)
            else:
                if self.operation is not None:
                    r=self.original;l,t,rr,b=r['x'],r['y'],r['x']+r['w'],r['y']+r['h']
                    if self.operation in (0,3,5):l=x
                    if self.operation in (2,4,7):rr=x+1
                    if self.operation in (0,1,2):t=y
                    if self.operation in (5,6,7):b=y+1
                else:l,t,rr,b=ax,ay,x,y
                self.rect=clamp_rect(min(l,rr),min(t,b),abs(rr-l),abs(b-t),bounds)
    def mouse(self,event,x,y,delta=0):
        if self.done:return
        if event=='wheel' and self.mode=='quadrado':
            self.size=max(16,min(256,self.size+4*(1 if delta>0 else -1)));self.placed=False
        if event=='down':
            if self.mode=='quadrado':
                self.placed=False;self.move(x,y);self.placed=True;return
            self.operation=None
            if self.rect:
                self.original=dict(self.rect)
                self.operation=next((i for i,(hx,hy) in enumerate(handles(self.rect)) if abs(x-hx)<=4 and abs(y-hy)<=4),None)
                r=self.rect
                if self.operation is None and r['x']<=x<r['x']+r['w'] and r['y']<=y<r['y']+r['h']:self.operation='move'
            self.anchor=(max(0,min(x,self.context['w']-1)),max(0,min(y,self.context['h']-1)));self.dragging=True
        self.move(x,y)
        if event=='up':self.dragging=False;self.placed=bool(self.rect)
    def key(self,key,shift=False,ctrl=False):
        if key=='escape': self.done=True; return None
        if key=='enter' and self.rect:return self.result()
        if self.rect and key in ('left','right','up','down'):
            self.placed=True;r=self.rect; amount=10 if shift else 1
            if ctrl and self.mode=='quadrado':
                delta=amount*(-1 if key in ('left','up') else 1)
                self.size=max(16,min(256,self.context['w'],self.context['h'],r['w']+delta))
                self.rect=clamp_rect(r['x'],r['y'],self.size,self.size,(self.context['w'],self.context['h']))
                return
            field=('w' if key in ('left','right') else 'h') if ctrl else ('x' if key in ('left','right') else 'y')
            r[field]+=amount*(-1 if key in ('left','up') else 1)
            self.rect=clamp_rect(r['x'],r['y'],r['w'],r['h'],(self.context['w'],self.context['h']))
    def result(self):
        self.done=True
        return dict(origem=dict(self.rect),modo=self.mode,contexto=dict(self.context))

def mouse_policy(x,y,context,paired_release=False):
    if paired_release:return 'consume'
    return 'consume' if 0<=x<context['w'] and 0<=y<context['h'] else 'cancel_pass'
