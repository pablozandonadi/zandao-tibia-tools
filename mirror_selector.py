"""Pure physical-coordinate selector state, independent of Win32 hooks."""
def clamp_rect(x,y,w,h,bounds):
    bw,bh=bounds
    w,h=max(1,min(int(w),bw)),max(1,min(int(h),bh))
    return dict(x=max(0,min(int(x),bw-w)),y=max(0,min(int(y),bh-h)),w=w,h=h)

class Selection:
    def __init__(self,mode,context,existing=None):
        self.mode=mode; self.context=context; self.size=32; self.anchor=None
        self.rect=dict((existing or {}).get('origem') or {}) or None
        self.dragging=False; self.done=False
        if mode=='quadrado' and self.rect:self.size=self.rect['w']
    def move(self,x,y):
        bounds=(self.context['w'],self.context['h'])
        if self.mode=='quadrado': self.rect=clamp_rect(x-self.size//2,y-self.size//2,self.size,self.size,bounds)
        elif self.dragging:
            ax,ay=self.anchor
            self.rect=clamp_rect(min(ax,x),min(ay,y),abs(x-ax),abs(y-ay),bounds)
    def mouse(self,event,x,y,delta=0):
        if event=='wheel' and self.mode=='quadrado':self.size=max(16,min(256,self.size+4*(1 if delta>0 else -1)))
        self.move(x,y)
        if event=='down':
            if self.mode=='quadrado':return self.result()
            self.anchor=(x,y); self.dragging=True
        elif event=='up': self.dragging=False
    def key(self,key,shift=False,ctrl=False):
        if key=='escape': self.done=True; return None
        if key=='enter' and self.rect:return self.result()
        if self.rect and key in ('left','right','up','down'):
            r=self.rect; amount=10 if shift else 1
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
