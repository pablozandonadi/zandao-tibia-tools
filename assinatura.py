"""Authenticode via native Windows trust API; policy is owned by the build."""
import ctypes
import json
import os
from pathlib import Path
import sys
import uuid
POLICY=Path(getattr(sys,'_MEIPASS',Path(__file__).parent))/'signing_policy.json'

def politica():
    data=json.loads(POLICY.read_text(encoding='utf-8-sig'))
    if type(data.get('required')) is not bool or not isinstance(data.get('thumbprints'),list):
        raise ValueError('Política de assinatura inválida.')
    return data

def native_signature(path):
    from ctypes import wintypes as w
    class FileInfo(ctypes.Structure):
        _fields_=[('size',w.DWORD),('path',w.LPCWSTR),('handle',w.HANDLE),('subject',ctypes.c_void_p)]
    class TrustData(ctypes.Structure):
        _fields_=[('size',w.DWORD),('policy',ctypes.c_void_p),('sip',ctypes.c_void_p),
            ('ui',w.DWORD),('revocation',w.DWORD),('choice',w.DWORD),('file',ctypes.POINTER(FileInfo)),
            ('state_action',w.DWORD),('state',w.HANDLE),('reference',w.LPCWSTR),('flags',w.DWORD),
            ('context',w.DWORD),('settings',ctypes.c_void_p)]
    class CertHead(ctypes.Structure):
        _fields_=[('size',w.DWORD),('certificate',ctypes.c_void_p)]
    system=Path(os.environ.get('SystemRoot',r'C:\Windows'))/'System32'
    trust=ctypes.WinDLL(str(system/'wintrust.dll'),use_last_error=True)
    crypt=ctypes.WinDLL(str(system/'crypt32.dll'),use_last_error=True)
    trust.WinVerifyTrust.argtypes=[w.HWND,ctypes.c_void_p,ctypes.POINTER(TrustData)]
    trust.WinVerifyTrust.restype=w.LONG
    guid=(ctypes.c_ubyte*16).from_buffer_copy(uuid.UUID('00aac56b-cd44-11d0-8cc2-00c04fc295ee').bytes_le)
    info=FileInfo(ctypes.sizeof(FileInfo),os.path.abspath(path),None,None)
    data=TrustData();data.size=ctypes.sizeof(TrustData);data.ui=2;data.revocation=1
    data.choice=1;data.file=ctypes.pointer(info);data.state_action=1
    try:
        result=trust.WinVerifyTrust(ctypes.c_void_p(-1),ctypes.byref(guid),ctypes.byref(data)) & 0xffffffff
        if result==0x800B0100:return {'status':'NotSigned','thumbprint':None}
        if result!=0:return {'status':'Invalid','code':f'{result:08X}','thumbprint':None}
        trust.WTHelperProvDataFromStateData.argtypes=[w.HANDLE];trust.WTHelperProvDataFromStateData.restype=ctypes.c_void_p
        trust.WTHelperGetProvSignerFromChain.argtypes=[ctypes.c_void_p,w.DWORD,w.BOOL,w.DWORD];trust.WTHelperGetProvSignerFromChain.restype=ctypes.c_void_p
        trust.WTHelperGetProvCertFromChain.argtypes=[ctypes.c_void_p,w.DWORD];trust.WTHelperGetProvCertFromChain.restype=ctypes.POINTER(CertHead)
        provider=trust.WTHelperProvDataFromStateData(data.state)
        signer=trust.WTHelperGetProvSignerFromChain(provider,0,False,0) if provider else None
        certificate=trust.WTHelperGetProvCertFromChain(signer,0) if signer else None
        fingerprint=None
        if certificate and certificate.contents.certificate:
            crypt.CertGetCertificateContextProperty.argtypes=[ctypes.c_void_p,w.DWORD,ctypes.c_void_p,ctypes.POINTER(w.DWORD)]
            crypt.CertGetCertificateContextProperty.restype=w.BOOL
            size=w.DWORD(20);value=(ctypes.c_ubyte*20)()
            if crypt.CertGetCertificateContextProperty(certificate.contents.certificate,3,value,ctypes.byref(size)):
                fingerprint=bytes(value).hex().upper()
        return {'status':'Valid','thumbprint':fingerprint}
    finally:
        data.state_action=2
        trust.WinVerifyTrust(ctypes.c_void_p(-1),ctypes.byref(guid),ctypes.byref(data))

def verificar_assinatura(path):
    policy=politica()
    if sys.platform!='win32':
        if policy['required']:raise ValueError('A assinatura deve ser conferida no Windows.')
        return {'status':'NotChecked'}
    signature=native_signature(path)
    if signature['status']=='NotSigned' and not policy['required']:return signature
    if signature['status']!='Valid':raise ValueError('Assinatura digital inválida ou ausente.')
    allowed=[x.upper() for x in policy['thumbprints']]
    if policy['required'] and not allowed:raise ValueError('Nenhum publicador aprovado foi configurado no build.')
    if allowed and (signature.get('thumbprint') or '').upper() not in allowed:
        raise ValueError('O instalador não foi assinado pelo publicador aprovado.')
    return signature
