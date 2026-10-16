"""Lê a credencial ElevenLabs protegida para o usuário atual do Windows."""
import ctypes
from ctypes import wintypes
import os
from pathlib import Path


def _desproteger(encrypted):
    class DataBlob(ctypes.Structure):
        _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_ubyte))]

    crypt32 = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    crypt32.CryptUnprotectData.argtypes = [ctypes.POINTER(DataBlob), ctypes.c_void_p,
                                          ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                                          wintypes.DWORD, ctypes.POINTER(DataBlob)]
    crypt32.CryptUnprotectData.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    buffer = (ctypes.c_ubyte * len(encrypted)).from_buffer_copy(encrypted)
    source = DataBlob(len(encrypted), buffer)
    result = DataBlob()
    try:
        if not crypt32.CryptUnprotectData(ctypes.byref(source), None, None, None, None,
                                          1, ctypes.byref(result)):
            raise ValueError('Credencial indisponível para este usuário.')
        return ctypes.string_at(result.pbData, result.cbData).decode('utf-16-le')
    finally:
        if result.pbData:
            ctypes.memset(result.pbData, 0, result.cbData)
            kernel32.LocalFree(result.pbData)


def carregar_chave():
    """Devolve a chave só em memória; ausência/arquivo inválido não gera logs."""
    local = os.environ.get('LOCALAPPDATA')
    if not local:
        return None
    path = Path(local) / 'TibiaTudo' / 'credentials' / 'elevenlabs.dpapi'
    try:
        with path.open('r', encoding='utf-8-sig') as stream:
            text = stream.read(16385).strip()
        if not text or len(text) > 16384:
            return None
        encrypted = bytes.fromhex(text)
        if not encrypted:
            return None
        return _desproteger(encrypted).strip() or None
    except (OSError, ValueError, AttributeError, UnicodeError):
        return None


def _proteger(text):
    """DPAPI CurrentUser; o arquivo resultante não contém o segredo legível."""
    class DataBlob(ctypes.Structure):
        _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_ubyte))]
    raw = text.encode('utf-16-le')
    buffer = (ctypes.c_ubyte * len(raw)).from_buffer_copy(raw)
    source, result = DataBlob(len(raw), buffer), DataBlob()
    crypt32 = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    crypt32.CryptProtectData.argtypes = [ctypes.POINTER(DataBlob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(DataBlob)]
    crypt32.CryptProtectData.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    try:
        if not crypt32.CryptProtectData(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(result)):
            raise ValueError('Não consegui proteger o código neste usuário do Windows.')
        return ctypes.string_at(result.pbData, result.cbData)
    finally:
        ctypes.memset(buffer, 0, len(raw))
        if result.pbData:
            ctypes.memset(result.pbData, 0, result.cbData)
            kernel32.LocalFree(result.pbData)
