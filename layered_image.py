"""Entrega um bitmap RGBA a uma janela Win32 layered sem capturar foco."""
import ctypes
from ctypes import wintypes
from timer_visual import bgra_premultiplicado


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("width", wintypes.LONG), ("height", wintypes.LONG),
                ("planes", wintypes.WORD), ("bits", wintypes.WORD), ("compression", wintypes.DWORD),
                ("image_size", wintypes.DWORD), ("xppm", wintypes.LONG), ("yppm", wintypes.LONG),
                ("used", wintypes.DWORD), ("important", wintypes.DWORD)]


class BLEND(ctypes.Structure):
    _fields_ = [("op", ctypes.c_ubyte), ("flags", ctypes.c_ubyte), ("alpha", ctypes.c_ubyte), ("format", ctypes.c_ubyte)]


def mostrar(hwnd, image, alpha=255):
    u, g = ctypes.windll.user32, ctypes.windll.gdi32
    g.CreateCompatibleDC.restype = wintypes.HDC
    g.CreateCompatibleDC.argtypes = [wintypes.HDC]
    g.CreateDIBSection.restype = wintypes.HBITMAP
    g.CreateDIBSection.argtypes = [wintypes.HDC, ctypes.c_void_p, wintypes.UINT, ctypes.POINTER(ctypes.c_void_p), wintypes.HANDLE, wintypes.DWORD]
    g.SelectObject.restype = wintypes.HGDIOBJ
    g.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
    g.DeleteDC.argtypes = [wintypes.HDC]
    g.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    u.UpdateLayeredWindow.argtypes = [wintypes.HWND, wintypes.HDC, ctypes.c_void_p, ctypes.c_void_p,
                                    wintypes.HDC, ctypes.c_void_p, wintypes.COLORREF, ctypes.c_void_p, wintypes.DWORD]
    hdc = g.CreateCompatibleDC(None)
    bitmap = old = None
    try:
        header = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), image.width, -image.height, 1, 32, 0, 0, 0, 0, 0, 0)
        bits = ctypes.c_void_p()
        bitmap = g.CreateDIBSection(hdc, ctypes.byref(header), 0, ctypes.byref(bits), None, 0)
        if not bitmap:
            raise ctypes.WinError()
        data = bgra_premultiplicado(image)
        ctypes.memmove(bits, data, len(data))
        old = g.SelectObject(hdc, bitmap)
        size = wintypes.SIZE(image.width, image.height)
        source = wintypes.POINT(0, 0)
        blend = BLEND(0, 0, max(0,min(255,alpha)), 1)
        if not u.UpdateLayeredWindow(hwnd, None, None, ctypes.byref(size), hdc, ctypes.byref(source), 0, ctypes.byref(blend), 2):
            raise ctypes.WinError()
    finally:
        if old:
            g.SelectObject(hdc, old)
        if bitmap:
            g.DeleteObject(bitmap)
        g.DeleteDC(hdc)
