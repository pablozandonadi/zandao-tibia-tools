"""Alerta visual por cima do Tibia (estilo das mensagens do próprio jogo), que não dá para clicar.

Uma janela do Windows transparente (cor-chave), sempre no topo, que ignora o mouse (WS_EX_TRANSPARENT)
e nunca pega o foco (WS_EX_NOACTIVATE): o clique passa direto para o jogo. O texto é desenhado com
contorno preto, centralizado na janela do Tibia, e some sozinho depois de alguns segundos.

Só aparece se o Tibia (client.exe) estiver aberto. Funciona com o Tibia em janela ou em tela cheia
sem bordas; no modo tela cheia exclusivo nenhum programa consegue desenhar por cima.
"""

import ctypes
import math
import os
import sys
import threading
import time
from ctypes import wintypes

PROCESSOS_TIBIA = ("client.exe", "tibia.exe")
CORES = {  # nome -> (rótulo, RGB)
    "branco": ("Branco", (255, 255, 255)),
    "amarelo": ("Amarelo", (255, 230, 60)),
    "laranja": ("Laranja", (255, 150, 30)),
    "vermelho": ("Vermelho", (255, 70, 60)),
    "verde": ("Verde", (90, 230, 110)),
}
CHAVE = (255, 0, 255)  # cor-chave: tudo nessa cor fica transparente
ALERTA_PADRAO = {"x": 50, "y": 30}  # posição do alerta em % da janela do Tibia (centro do texto)


def cor_rgb(cor):
    """'amarelo' ou '#RRGGBB' -> (r, g, b). A cor-chave exata é desviada em 1 para não sumir."""
    if isinstance(cor, str) and cor.startswith("#") and len(cor) == 7:
        try:
            rgb = tuple(int(cor[i:i + 2], 16) for i in (1, 3, 5))
            return (254, 0, 255) if rgb == CHAVE else rgb
        except ValueError:
            pass
    return CORES.get(cor, CORES["amarelo"])[1]


def normalizar_alerta(a):
    a = {**ALERTA_PADRAO, **(a or {})}
    return {"x": max(0, min(100, float(a["x"]))), "y": max(0, min(100, float(a["y"])))}

if sys.platform == "win32":
    _u32, _g32, _k32 = ctypes.windll.user32, ctypes.windll.gdi32, ctypes.windll.kernel32
    LRESULT = ctypes.c_ssize_t
    WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
    _u32.DefWindowProcW.restype = LRESULT
    _u32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    _u32.CreateWindowExW.restype = wintypes.HWND
    _u32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                                     ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                     wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
    _u32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
    # handles são ponteiros de 64 bits: sem declarar os tipos o ctypes tenta passar como int de 32 e estoura
    _g32.CreateFontW.restype = wintypes.HFONT
    _g32.CreateSolidBrush.restype = wintypes.HBRUSH
    _g32.SelectObject.restype = wintypes.HGDIOBJ
    _g32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
    _g32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    _g32.SetTextColor.argtypes = [wintypes.HDC, wintypes.COLORREF]
    _g32.SetBkMode.argtypes = [wintypes.HDC, ctypes.c_int]
    _u32.BeginPaint.restype = wintypes.HDC
    _u32.BeginPaint.argtypes = [wintypes.HWND, ctypes.c_void_p]
    _u32.EndPaint.argtypes = [wintypes.HWND, ctypes.c_void_p]
    _u32.FillRect.argtypes = [wintypes.HDC, ctypes.c_void_p, wintypes.HBRUSH]
    _u32.DrawTextW.argtypes = [wintypes.HDC, wintypes.LPCWSTR, ctypes.c_int, ctypes.c_void_p, wintypes.UINT]
    _u32.GetClientRect.argtypes = [wintypes.HWND, ctypes.c_void_p]
    _u32.InvalidateRect.argtypes = [wintypes.HWND, ctypes.c_void_p, wintypes.BOOL]
    _u32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    _u32.SetTimer.argtypes = [wintypes.HWND, ctypes.c_size_t, wintypes.UINT, ctypes.c_void_p]
    _u32.KillTimer.argtypes = [wintypes.HWND, ctypes.c_size_t]
    _u32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    _u32.SetLayeredWindowAttributes.argtypes = [wintypes.HWND, wintypes.COLORREF, ctypes.c_ubyte, wintypes.DWORD]
    _k32.GetModuleHandleW.restype = wintypes.HMODULE
    _u32.GetMessageW.argtypes = [ctypes.c_void_p, wintypes.HWND, wintypes.UINT, wintypes.UINT]
    _u32.TranslateMessage.argtypes = [ctypes.c_void_p]
    _u32.DispatchMessageW.argtypes = [ctypes.c_void_p]

WS_POPUP = 0x80000000
WS_EX_LAYERED, WS_EX_TRANSPARENT, WS_EX_TOPMOST = 0x80000, 0x20, 0x8
WS_EX_TOOLWINDOW, WS_EX_NOACTIVATE = 0x80, 0x08000000
WM_PAINT, WM_TIMER, WM_APP = 0x000F, 0x0113, 0x8000
SW_HIDE = 0
SWP_NOACTIVATE, SWP_SHOWWINDOW = 0x10, 0x40
LWA_COLORKEY = 0x1
LWA_ALPHA = 0x2
PISCA_PERIODO = 0.8   # segundos de um ciclo some/aparece do alerta piscando
DT_CENTER, DT_VCENTER, DT_SINGLELINE, DT_NOPREFIX = 0x1, 0x4, 0x20, 0x800
NONANTIALIASED_QUALITY = 3  # sem suavização: a borda não "mistura" com a cor-chave
FW_BOLD = 700


def _rgb(c):
    return c[0] | (c[1] << 8) | (c[2] << 16)


class _PAINTSTRUCT(ctypes.Structure):
    _fields_ = [("hdc", wintypes.HDC), ("fErase", wintypes.BOOL), ("rcPaint", wintypes.RECT),
                ("fRestore", wintypes.BOOL), ("fIncUpdate", wintypes.BOOL), ("rgbReserved", ctypes.c_byte * 32)]


class _WNDCLASS(ctypes.Structure):
    _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", WNDPROC if sys.platform == "win32" else ctypes.c_void_p),
                ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE),
                ("hIcon", wintypes.HICON), ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH),
                ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR)]


def janela_do_tibia():
    """Retângulo (esq, topo, dir, base) da maior janela visível do cliente do Tibia, ou None."""
    achadas = []

    def cb(hwnd, _):
        if not _u32.IsWindowVisible(hwnd) or _u32.IsIconic(hwnd):
            return True
        pid = wintypes.DWORD()
        _u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        h = _k32.OpenProcess(0x1000, False, pid.value)
        if not h:
            return True
        try:
            buf = ctypes.create_unicode_buffer(520)
            tam = wintypes.DWORD(520)
            if _k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(tam)) and \
                    os.path.basename(buf.value).lower() in PROCESSOS_TIBIA:
                r = wintypes.RECT()
                _u32.GetWindowRect(hwnd, ctypes.byref(r))
                if r.right - r.left > 200 and r.bottom - r.top > 150:
                    achadas.append((r.left, r.top, r.right, r.bottom))
        finally:
            _k32.CloseHandle(h)
        return True

    _u32.EnumWindows(ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(cb), 0)
    return max(achadas, key=lambda r: (r[2] - r[0]) * (r[3] - r[1])) if achadas else None


BARRA_PADRAO = {"largura": 320, "espessura": 14, "x": 50, "y": 78, "nome": True}


def normalizar_barra(b):
    b = {**BARRA_PADRAO, **(b or {})}
    return {"largura": max(80, min(1200, int(b["largura"]))), "espessura": max(4, min(48, int(b["espessura"]))),
            "x": max(0, min(100, float(b["x"]))), "y": max(0, min(100, float(b["y"]))), "nome": bool(b["nome"])}


def layout_barras(n, cfg, alvo):
    """Onde fica a janela das barras: (x, y, largura, altura, altura_de_cada_linha). x/y em % da janela do Tibia."""
    esq, topo, dir_, base = alvo
    linha = cfg["espessura"] + (18 if cfg["nome"] else 0) + 6
    larg, alt = cfg["largura"] + 8, linha * n + 4
    cx = esq + (dir_ - esq) * cfg["x"] / 100
    cy = topo + (base - topo) * cfg["y"] / 100
    x = int(min(max(cx - larg / 2, esq), dir_ - larg))
    y = int(min(max(cy - alt / 2, topo), base - alt))
    return x, y, larg, alt, linha


class Barras:
    """Barras de contagem por cima do Tibia (uma por timer rodando), que não dá para clicar."""

    def __init__(self):
        self._dados = ([], BARRA_PADRAO, None)
        self._trava = threading.Lock()
        self._pronto = threading.Event()
        self.hwnd = None
        self._visivel = False
        threading.Thread(target=self._rodar, daemon=True).start()
        self._pronto.wait(3)

    def atualizar(self, itens, cfg, so_tibia=True):
        """itens: [(nome, fração 0..1 que falta, texto do tempo, nome da cor)]. Lista vazia esconde."""
        alvo = janela_do_tibia() if itens else None
        if itens and alvo is None and not so_tibia:
            alvo = (0, 0, _u32.GetSystemMetrics(0), _u32.GetSystemMetrics(1))
        if not itens or alvo is None:
            if self._visivel and self.hwnd:
                _u32.PostMessageW(self.hwnd, WM_APP + 2, 0, 0)
            return alvo is not None or not itens
        with self._trava:
            self._dados = (list(itens), normalizar_barra(cfg), alvo)
        if self.hwnd:
            _u32.PostMessageW(self.hwnd, WM_APP + 1, 0, 0)
        return True

    def _rodar(self):
        self._proc = WNDPROC(self._wndproc)
        hinst = _k32.GetModuleHandleW(None)
        wc = _WNDCLASS()
        wc.lpfnWndProc = self._proc
        wc.hInstance = hinst
        wc.lpszClassName = "ZandaoTibiaToolsBarras"
        wc.hbrBackground = _g32.CreateSolidBrush(_rgb(CHAVE))
        _u32.RegisterClassW(ctypes.byref(wc))
        self.hwnd = _u32.CreateWindowExW(
            WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE,
            wc.lpszClassName, "Zandao Tibia Tools - barras", WS_POPUP, 0, 0, 300, 40, None, None, hinst, None)
        _u32.SetLayeredWindowAttributes(self.hwnd, _rgb(CHAVE), 0, LWA_COLORKEY)
        self._fonte = _g32.CreateFontW(-13, 0, 0, 0, FW_BOLD, 0, 0, 0, 0, 0, 0, NONANTIALIASED_QUALITY, 0, "Verdana")
        self._pronto.set()
        msg = wintypes.MSG()
        while _u32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            _u32.TranslateMessage(ctypes.byref(msg))
            _u32.DispatchMessageW(ctypes.byref(msg))

    def _retangulo(self, hdc, x1, y1, x2, y2, rgb):
        pincel = _g32.CreateSolidBrush(_rgb(rgb))
        r = wintypes.RECT(int(x1), int(y1), int(x2), int(y2))
        _u32.FillRect(hdc, ctypes.byref(r), pincel)
        _g32.DeleteObject(pincel)

    def _texto(self, hdc, texto, x1, y1, x2, y2, rgb, alinhar):
        flags = alinhar | DT_SINGLELINE | DT_NOPREFIX | 0x8  # DT_BOTTOM
        _g32.SetTextColor(hdc, _rgb((1, 1, 1)))
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            rr = wintypes.RECT(int(x1 + dx), int(y1 + dy), int(x2 + dx), int(y2 + dy))
            _u32.DrawTextW(hdc, texto, -1, ctypes.byref(rr), flags)
        _g32.SetTextColor(hdc, _rgb(rgb))
        r = wintypes.RECT(int(x1), int(y1), int(x2), int(y2))
        _u32.DrawTextW(hdc, texto, -1, ctypes.byref(r), flags)

    def _wndproc(self, hwnd, msg, wparam, lparam):
        if msg == WM_APP + 1:
            with self._trava:
                itens, cfg, alvo = self._dados
            x, y, larg, alt, _ = layout_barras(len(itens), cfg, alvo)
            _u32.SetWindowPos(hwnd, ctypes.c_void_p(-1), x, y, larg, alt, SWP_NOACTIVATE | SWP_SHOWWINDOW)
            self._visivel = True
            _u32.InvalidateRect(hwnd, None, True)
            return 0
        if msg == WM_APP + 2:
            _u32.ShowWindow(hwnd, SW_HIDE)
            self._visivel = False
            return 0
        if msg == WM_PAINT:
            ps = _PAINTSTRUCT()
            hdc = _u32.BeginPaint(hwnd, ctypes.byref(ps))
            with self._trava:
                itens, cfg, _ = self._dados
            _g32.SelectObject(hdc, self._fonte)
            _g32.SetBkMode(hdc, 1)
            linha = cfg["espessura"] + (18 if cfg["nome"] else 0) + 6
            for i, (nome, frac, tempo, cor) in enumerate(itens):
                rgb = cor_rgb(cor)
                y0 = 2 + i * linha
                if cfg["nome"]:
                    self._texto(hdc, nome, 4, y0, 4 + cfg["largura"], y0 + 17, (255, 255, 255), 0x0)      # DT_LEFT
                    self._texto(hdc, tempo, 4, y0, 4 + cfg["largura"], y0 + 17, rgb, 0x2)               # DT_RIGHT
                    y0 += 18
                yb = y0 + cfg["espessura"]
                self._retangulo(hdc, 2, y0 - 2, 6 + cfg["largura"], yb + 2, (1, 1, 1))                   # contorno
                self._retangulo(hdc, 4, y0, 4 + cfg["largura"], yb, (40, 44, 52))                         # fundo
                cheio = max(0.0, min(1.0, frac)) * cfg["largura"]
                if cheio >= 1:
                    self._retangulo(hdc, 4, y0, 4 + cheio, yb, rgb)
            _u32.EndPaint(hwnd, ctypes.byref(ps))
            return 0
        return _u32.DefWindowProcW(hwnd, msg, wparam, lparam)


class Overlay:
    """Uma janela de alerta com a própria thread (o Windows exige o loop de mensagens na thread que a criou)."""

    LARGURA, ALTURA = 900, 90

    def __init__(self):
        self._pedido = None
        self._trava = threading.Lock()
        self._pronto = threading.Event()
        self.hwnd = None
        threading.Thread(target=self._rodar, daemon=True).start()
        self._pronto.wait(3)

    def esconder(self):
        if self.hwnd:
            _u32.PostMessageW(self.hwnd, WM_APP + 2, 0, 0)

    def mostrar(self, texto, cor="amarelo", segundos=3.0, so_tibia=True, tamanho=34, pos=None, piscar=False):
        """Mostra o alerta. segundos=0: fica até esconder(). piscar: aparece e some suave (fade).
        Devolve False se o Tibia não está aberto (e so_tibia)."""
        alvo = janela_do_tibia() if sys.platform == "win32" else None
        if alvo is None:
            if so_tibia:
                return False
            alvo = (0, 0, _u32.GetSystemMetrics(0), _u32.GetSystemMetrics(1))
        with self._trava:
            self._pedido = (str(texto), cor_rgb(cor), float(segundos), alvo,
                            max(14, min(96, int(tamanho))), normalizar_alerta(pos), bool(piscar))
        if self.hwnd:
            _u32.PostMessageW(self.hwnd, WM_APP + 1, 0, 0)
        return True

    # ---------------- thread da janela ----------------
    def _alfa(self, a):
        _u32.SetLayeredWindowAttributes(self.hwnd, _rgb(CHAVE), max(0, min(255, a)), LWA_COLORKEY | LWA_ALPHA)

    def _rodar(self):
        self._proc = WNDPROC(self._wndproc)  # guardar a referência: senão o Python apaga e a janela trava
        self._pisca_ini = 0.0
        hinst = _k32.GetModuleHandleW(None)
        wc = _WNDCLASS()
        wc.lpfnWndProc = self._proc
        wc.hInstance = hinst
        wc.lpszClassName = "ZandaoTibiaToolsAlerta"
        wc.hbrBackground = _g32.CreateSolidBrush(_rgb(CHAVE))
        _u32.RegisterClassW(ctypes.byref(wc))
        self.hwnd = _u32.CreateWindowExW(
            WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE,
            wc.lpszClassName, "Zandao Tibia Tools - alerta", WS_POPUP, 0, 0, self.LARGURA, self.ALTURA,
            None, None, hinst, None)
        _u32.SetLayeredWindowAttributes(self.hwnd, _rgb(CHAVE), 0, LWA_COLORKEY)
        self._fontes = {}
        self._tamanho = 34
        self._texto, self._cor = "", (255, 230, 60)
        self._pronto.set()
        msg = wintypes.MSG()
        while _u32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            _u32.TranslateMessage(ctypes.byref(msg))
            _u32.DispatchMessageW(ctypes.byref(msg))

    def _wndproc(self, hwnd, msg, wparam, lparam):
        if msg == WM_APP + 1:
            with self._trava:
                pedido, self._pedido = self._pedido, None
            if pedido:
                self._texto, self._cor, segundos, (esq, topo, dir_, base), self._tamanho, pos, piscar = pedido
                _u32.KillTimer(hwnd, 2)
                self._alfa(255)
                if piscar:
                    self._pisca_ini = time.monotonic()
                    _u32.SetTimer(hwnd, 2, 30, None)
                alt = int(self._tamanho * 2.2)
                larg = min(max(self.LARGURA, int(len(self._texto) * self._tamanho * .75)), dir_ - esq)
                cx = esq + (dir_ - esq) * pos["x"] / 100
                cy = topo + (base - topo) * pos["y"] / 100
                x = int(min(max(cx - larg / 2, esq), dir_ - larg))
                y = int(min(max(cy - alt / 2, topo), base - alt))
                _u32.SetWindowPos(hwnd, ctypes.c_void_p(-1), x, y, larg, alt, SWP_NOACTIVATE | SWP_SHOWWINDOW)
                _u32.InvalidateRect(hwnd, None, True)
                _u32.KillTimer(hwnd, 1)
                if segundos > 0:
                    _u32.SetTimer(hwnd, 1, int(segundos * 1000), None)
            return 0
        if msg == WM_TIMER and wparam == 2:   # piscando: some e aparece suave
            fase = ((time.monotonic() - self._pisca_ini) % PISCA_PERIODO) / PISCA_PERIODO
            self._alfa(int(25 + 230 * (0.5 + 0.5 * math.cos(2 * math.pi * fase))))
            return 0
        if msg == WM_APP + 2 or msg == WM_TIMER:
            _u32.KillTimer(hwnd, 1)
            _u32.KillTimer(hwnd, 2)
            _u32.ShowWindow(hwnd, SW_HIDE)
            self._alfa(255)
            return 0
        if msg == WM_PAINT:
            ps = _PAINTSTRUCT()
            hdc = _u32.BeginPaint(hwnd, ctypes.byref(ps))
            r = wintypes.RECT()
            _u32.GetClientRect(hwnd, ctypes.byref(r))
            fonte = self._fontes.get(self._tamanho)
            if not fonte:
                fonte = self._fontes[self._tamanho] = _g32.CreateFontW(-self._tamanho, 0, 0, 0, FW_BOLD, 0, 0, 0, 0, 0, 0,
                                                                      NONANTIALIASED_QUALITY, 0, "Verdana")
            _g32.SelectObject(hdc, fonte)
            _g32.SetBkMode(hdc, 1)  # TRANSPARENT
            flags = DT_CENTER | DT_VCENTER | DT_SINGLELINE | DT_NOPREFIX
            # contorno preto (desenha o texto deslocado em volta) e depois o texto colorido por cima
            _g32.SetTextColor(hdc, _rgb((1, 1, 1)))
            for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2), (-2, -2), (2, 2), (-2, 2), (2, -2)):
                rr = wintypes.RECT(r.left + dx, r.top + dy, r.right + dx, r.bottom + dy)
                _u32.DrawTextW(hdc, self._texto, -1, ctypes.byref(rr), flags)
            _g32.SetTextColor(hdc, _rgb(self._cor))
            _u32.DrawTextW(hdc, self._texto, -1, ctypes.byref(r), flags)
            _u32.EndPaint(hwnd, ctypes.byref(ps))
            return 0
        return _u32.DefWindowProcW(hwnd, msg, wparam, lparam)
