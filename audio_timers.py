"""Timers de áudio (igual ao TibiaAudio do TibiaVision): uma tecla apertada no Tibia começa um timer,
e quando ele acaba o app toca um som. Funciona com o app minimizado.

- Teclas: o app só PERGUNTA ao Windows se as teclas cadastradas estão apertadas (GetAsyncKeyState),
  várias vezes por segundo. Não grava o que é digitado, não manda tecla nenhuma, não mexe no jogo.
- Por padrão só conta com o Tibia em foco (client.exe), para "K" num navegador não disparar o timer.
- Som: MCI do Windows (winmm), que toca .wav e .mp3 com volume, sem biblioteca extra.
  Os sons prontos são gerados pelo próprio app (sons/), os do usuário ficam em sons_usuario/.

Modos de um timer:
  "reinicia" - cada aperto (re)começa a contagem, mesmo no meio;
  "ignora"   - apertar enquanto conta não faz nada; ao acabar avisa e espera o próximo aperto;
  "loop"     - um aperto começa a repetir sozinho (avisa a cada volta); outro aperto para.
"antes" (s): o som toca esse tanto antes de acabar (ex.: 3 s antes da poção).

Arquivo audio_timers.json (ao lado do programa, cada pessoa tem o seu):
  {"ligado": true, "volume": 90, "so_tibia": true,
   "timers": [{"id": "a1b2", "nome": "Poção", "tecla": {"vk": 75, "nome": "K", "ctrl": false, "shift": false,
               "alt": false}, "duracao": 120, "modo": "reinicia", "antes": 0, "som": "pronto:bipe",
               "volume": 100, "ativo": true}]}
"""

import ctypes
import json
import math
import os
import queue
import shutil
import struct
import sys
import threading
import time
import uuid
import wave

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

ARQUIVO = os.path.join(BASE_DIR, "audio_timers.json")
PASTA_SONS = os.path.join(BASE_DIR, "sons")
PASTA_SONS_USUARIO = os.path.join(BASE_DIR, "sons_usuario")
MODOS = ("reinicia", "ignora", "loop")
PROCESSOS_TIBIA = ("client.exe", "tibia.exe")

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
PADRAO = {"ligado": True, "volume": 90, "so_tibia": True, "timers": []}


def carregar(caminho=None):
    try:
        with open(caminho or ARQUIVO, "r", encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, json.JSONDecodeError):
        d = {}
    cfg = {**PADRAO, **{k: v for k, v in d.items() if k in PADRAO}}
    cfg["timers"] = [normalizar(t) for t in cfg.get("timers") or [] if isinstance(t, dict)]
    return cfg


def salvar(cfg, caminho=None):
    caminho = caminho or ARQUIVO
    tmp = caminho + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=1)
    os.replace(tmp, caminho)


def _duracao(v):
    """Segundos entre 1 s e 24 h; vazio, zero ou inválido vira o padrão (60 s)."""
    try:
        d = float(v or 0)
    except (TypeError, ValueError):
        d = 0
    return 60.0 if d <= 0 else max(1.0, min(24 * 3600.0, d))


def normalizar(t):
    """Garante todos os campos e valores válidos num timer vindo da tela ou do arquivo."""
    tecla = t.get("tecla") or {}
    return {
        "id": t.get("id") or uuid.uuid4().hex[:8],
        "nome": (t.get("nome") or "Timer").strip()[:40] or "Timer",
        "tecla": {"vk": int(tecla.get("vk") or 0), "nome": str(tecla.get("nome") or ""),
                  "ctrl": bool(tecla.get("ctrl")), "shift": bool(tecla.get("shift")), "alt": bool(tecla.get("alt"))},
        "duracao": _duracao(t.get("duracao")),
        "modo": t.get("modo") if t.get("modo") in MODOS else "reinicia",
        "antes": max(0.0, float(t.get("antes") or 0)),
        "som": str(t.get("som") or "pronto:bipe"),
        "volume": max(0, min(100, int(t.get("volume") if t.get("volume") is not None else 100))),
        "ativo": bool(t.get("ativo", True)),
    }


# ---------------------------------------------------------------------------
# Lógica de um timer (sem Windows: dá para testar com um relógio falso)
# ---------------------------------------------------------------------------
class EstadoTimer:
    def __init__(self, cfg):
        self.cfg = cfg
        self.fim = None        # quando acaba a volta atual (time.monotonic) ou None se parado
        self.tocou = False     # já tocou o aviso desta volta?

    @property
    def rodando(self):
        return self.fim is not None

    def _comecar(self, agora):
        self.fim = agora + self.cfg["duracao"]
        self.tocou = False

    def apertou(self, agora):
        modo = self.cfg["modo"]
        if modo == "reinicia":
            self._comecar(agora)
        elif modo == "ignora":
            if not self.rodando:
                self._comecar(agora)
        elif modo == "loop":
            if self.rodando:
                self.fim = None  # segundo aperto para o loop
            else:
                self._comecar(agora)

    def tick(self, agora):
        """Avança o tempo. Devolve True quando é hora de tocar o som."""
        if not self.rodando:
            return False
        tocar = False
        antes = min(self.cfg["antes"], self.cfg["duracao"])
        if not self.tocou and agora >= self.fim - antes:
            tocar, self.tocou = True, True
        if agora >= self.fim:
            if self.cfg["modo"] == "loop":
                # próxima volta (se o app travou e perdeu voltas, não toca várias seguidas)
                while self.fim <= agora:
                    self.fim += self.cfg["duracao"]
                self.tocou = antes > 0 and agora >= self.fim - antes
            else:
                self.fim = None
        return tocar

    def restante(self, agora):
        return max(0.0, self.fim - agora) if self.rodando else None


# ---------------------------------------------------------------------------
# Sons prontos (gerados pelo app: sem arquivo de terceiros)
# ---------------------------------------------------------------------------
# nome -> lista de (frequência Hz, duração s); 0 Hz = pausa
SONS_PRONTOS = {
    "bipe": ("Bipe", [(1046, .18)]),
    "bipe_duplo": ("Bipe duplo", [(1046, .12), (0, .07), (1046, .12)]),
    "sino": ("Sino", [(880, .5)]),
    "alarme": ("Alarme", [(988, .14), (0, .05), (784, .14), (0, .05), (988, .14), (0, .05), (784, .14)]),
    "ding": ("Ding suave", [(1318, .09), (1760, .35)]),
    "subindo": ("Subindo", [(523, .1), (659, .1), (784, .1), (1046, .2)]),
}
TAXA = 44100


def _gerar_wav(caminho, notas):
    amostras = []
    for freq, dur in notas:
        n = int(TAXA * dur)
        for i in range(n):
            if not freq:
                amostras.append(0)
                continue
            t = i / TAXA
            env = min(1.0, i / (TAXA * .005)) * math.exp(-3.2 * t / max(dur, .05))  # ataque curto + decaimento
            v = math.sin(2 * math.pi * freq * t) + .25 * math.sin(4 * math.pi * freq * t)
            amostras.append(int(max(-1, min(1, v * env * .7)) * 32767))
    with wave.open(caminho, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(TAXA)
        w.writeframes(b"".join(struct.pack("<h", a) for a in amostras))


def garantir_sons_prontos():
    os.makedirs(PASTA_SONS, exist_ok=True)
    for chave, (_, notas) in SONS_PRONTOS.items():
        caminho = os.path.join(PASTA_SONS, chave + ".wav")
        if not os.path.isfile(caminho):
            _gerar_wav(caminho, notas)


def lista_sons():
    """[{id, nome}]: prontos + os importados pelo usuário."""
    sons = [{"id": "pronto:" + k, "nome": nome} for k, (nome, _) in SONS_PRONTOS.items()]
    if os.path.isdir(PASTA_SONS_USUARIO):
        for arq in sorted(os.listdir(PASTA_SONS_USUARIO), key=str.lower):
            if arq.lower().endswith((".wav", ".mp3")):
                sons.append({"id": "usuario:" + arq, "nome": "🎵 " + os.path.splitext(arq)[0]})
    return sons


def caminho_do_som(som_id):
    tipo, _, nome = (som_id or "").partition(":")
    if tipo == "pronto" and nome in SONS_PRONTOS:
        return os.path.join(PASTA_SONS, nome + ".wav")
    if tipo == "usuario" and nome and os.path.basename(nome) == nome:
        caminho = os.path.join(PASTA_SONS_USUARIO, nome)
        if os.path.isfile(caminho):
            return caminho
    return os.path.join(PASTA_SONS, "bipe.wav")


def importar_som(origem):
    """Copia um .wav/.mp3 do usuário para sons_usuario/. Devolve o id do som."""
    if not origem.lower().endswith((".wav", ".mp3")):
        raise ValueError("Use um arquivo .mp3 ou .wav.")
    if os.path.getsize(origem) > 5 * 1024 * 1024:
        raise ValueError("O som pode ter no máximo 5 MB.")
    os.makedirs(PASTA_SONS_USUARIO, exist_ok=True)
    nome = os.path.basename(origem)
    shutil.copy2(origem, os.path.join(PASTA_SONS_USUARIO, nome))
    return "usuario:" + nome


# ---------------------------------------------------------------------------
# Windows: teclado, janela em foco e som
# ---------------------------------------------------------------------------
_u32 = ctypes.windll.user32 if sys.platform == "win32" else None
_k32 = ctypes.windll.kernel32 if sys.platform == "win32" else None
VK_SHIFT, VK_CONTROL, VK_MENU = 0x10, 0x11, 0x12
_NAO_TECLA = {0x01, 0x02, 0x04, 0x05, 0x06, VK_SHIFT, VK_CONTROL, VK_MENU, 0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5, 0x5B, 0x5C}


def tecla_apertada(vk):
    return bool(_u32.GetAsyncKeyState(vk) & 0x8000)


def nome_da_tecla(vk):
    especiais = {0x70 + i: f"F{i + 1}" for i in range(24)}
    especiais.update({0x20: "Espaço", 0x0D: "Enter", 0x1B: "Esc", 0x09: "Tab", 0x08: "Backspace",
                      0x2D: "Insert", 0x2E: "Delete", 0x24: "Home", 0x23: "End", 0x21: "PgUp", 0x22: "PgDn",
                      0x25: "←", 0x26: "↑", 0x27: "→", 0x28: "↓"})
    if vk in especiais:
        return especiais[vk]
    if 0x60 <= vk <= 0x69:
        return f"Num {vk - 0x60}"
    scan = _u32.MapVirtualKeyW(vk, 0)
    buf = ctypes.create_unicode_buffer(32)
    if scan and _u32.GetKeyNameTextW(scan << 16, buf, 32):
        return buf.value.upper() if len(buf.value) == 1 else buf.value
    return f"Tecla {vk}"


def gravar_tecla(espera=8.0):
    """Espera a próxima tecla (com Ctrl/Shift/Alt se estiverem segurados). None se ninguém apertar."""
    soltas = {vk for vk in range(0x08, 0xFF) if vk not in _NAO_TECLA and tecla_apertada(vk)}
    limite = time.time() + espera
    while time.time() < limite:
        for vk in range(0x08, 0xFF):
            if vk in _NAO_TECLA:
                continue
            if tecla_apertada(vk):
                if vk in soltas:
                    continue
                return {"vk": vk, "nome": nome_da_tecla(vk), "ctrl": tecla_apertada(VK_CONTROL),
                        "shift": tecla_apertada(VK_SHIFT), "alt": tecla_apertada(VK_MENU)}
            soltas.discard(vk)
        time.sleep(.01)
    return None


def texto_da_tecla(t):
    if not t or not t.get("vk"):
        return "—"
    return "+".join([m for m, on in (("Ctrl", t["ctrl"]), ("Shift", t["shift"]), ("Alt", t["alt"])) if on] + [t["nome"]])


def tibia_em_foco():
    """A janela em foco é do cliente do Tibia?"""
    from ctypes import wintypes
    hwnd = _u32.GetForegroundWindow()
    if not hwnd:
        return False
    pid = wintypes.DWORD()
    _u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    h = _k32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return False
    try:
        buf = ctypes.create_unicode_buffer(520)
        tam = wintypes.DWORD(520)
        if not _k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(tam)):
            return False
        return os.path.basename(buf.value).lower() in PROCESSOS_TIBIA
    finally:
        _k32.CloseHandle(h)


class Tocador:
    """Toca sons numa thread só (o MCI do Windows prefere assim), um alias por arquivo."""

    def __init__(self):
        self._fila = queue.Queue()
        self._abertos = {}
        threading.Thread(target=self._rodar, daemon=True).start()

    def tocar(self, caminho, volume):
        self._fila.put((caminho, max(0, min(100, int(volume)))))

    def _mci(self, cmd):
        return ctypes.windll.winmm.mciSendStringW(cmd, None, 0, None)

    def _rodar(self):
        while True:
            caminho, volume = self._fila.get()
            try:
                alias = self._abertos.get(caminho)
                if not alias:
                    alias = f"som{len(self._abertos) + 1}"
                    if self._mci(f'open "{caminho}" type mpegvideo alias {alias}') != 0:
                        continue
                    self._abertos[caminho] = alias
                self._mci(f"setaudio {alias} volume to {volume * 10}")
                self._mci(f"play {alias} from 0")
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Motor: lê as teclas, avança os timers e toca os sons
# ---------------------------------------------------------------------------
class Motor:
    INTERVALO = .015

    def __init__(self, ao_mudar=None):
        self.cfg = carregar()
        self.estados = {}
        self._apertadas = set()
        self._trava = threading.Lock()
        self._ao_mudar = ao_mudar          # função chamada com o estado (para a tela)
        self._ultimo_envio = 0
        self.tocador = Tocador()
        garantir_sons_prontos()
        self._sincronizar()
        threading.Thread(target=self._rodar, daemon=True).start()

    def _sincronizar(self):
        """Recria os estados quando a configuração muda, mantendo a contagem de quem continua igual."""
        novos = {}
        for t in self.cfg["timers"]:
            antigo = self.estados.get(t["id"])
            if antigo and antigo.cfg["duracao"] == t["duracao"] and antigo.cfg["modo"] == t["modo"]:
                antigo.cfg = t
                novos[t["id"]] = antigo
            else:
                novos[t["id"]] = EstadoTimer(t)
        self.estados = novos

    def atualizar_cfg(self, cfg):
        with self._trava:
            self.cfg = cfg
            salvar(cfg)
            self._sincronizar()

    def tocar(self, som_id, volume_timer=100):
        self.tocador.tocar(caminho_do_som(som_id), volume_timer * self.cfg["volume"] / 100)

    def parar_todos(self):
        with self._trava:
            for e in self.estados.values():
                e.fim = None

    def estado(self):
        agora = time.monotonic()
        with self._trava:
            return {"ligado": self.cfg["ligado"],
                    "timers": {tid: {"restante": e.restante(agora), "duracao": e.cfg["duracao"]}
                               for tid, e in self.estados.items()}}

    def _rodar(self):
        while True:
            try:
                self._passo()
            except Exception:
                pass
            time.sleep(self.INTERVALO)

    def _passo(self):
        agora = time.monotonic()
        mudou = False
        with self._trava:
            ligado = self.cfg["ligado"]
            ativos = [e for e in self.estados.values() if e.cfg["ativo"] and e.cfg["tecla"]["vk"]]
            if ligado and ativos:
                vks = {e.cfg["tecla"]["vk"] for e in ativos}
                agora_apertadas = {vk for vk in vks if tecla_apertada(vk)}
                novas = agora_apertadas - self._apertadas   # só a borda (apertou agora), não o segurar
                self._apertadas = agora_apertadas
                if novas and (not self.cfg["so_tibia"] or tibia_em_foco()):
                    ctrl, shift, alt = tecla_apertada(VK_CONTROL), tecla_apertada(VK_SHIFT), tecla_apertada(VK_MENU)
                    for e in ativos:
                        t = e.cfg["tecla"]
                        if t["vk"] in novas and (t["ctrl"], t["shift"], t["alt"]) == (ctrl, shift, alt):
                            e.apertou(agora)
                            mudou = True
            for e in self.estados.values():
                if e.tick(agora):
                    self.tocador.tocar(caminho_do_som(e.cfg["som"]), e.cfg["volume"] * self.cfg["volume"] / 100)
                    mudou = True
            rodando = any(e.rodando for e in self.estados.values())
        # manda o estado para a tela: na hora quando muda, e 4x por segundo enquanto algo conta
        if self._ao_mudar and (mudou or (rodando and agora - self._ultimo_envio > .25)):
            self._ultimo_envio = agora
            self._ao_mudar(self.estado())
