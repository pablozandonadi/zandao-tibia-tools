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
"alerta": também mostra um texto por cima do Tibia na hora do aviso; "barra": uma barra correndo por cima
do Tibia enquanto conta (largura/espessura/posição em cfg["barra"]). Ver overlay.py.

Arquivo audio_timers.json (ao lado do programa, cada pessoa tem o seu):
  {"ligado": true, "volume": 90, "so_tibia": true,
   "timers": [{"id": "a1b2", "nome": "Poção", "tecla": {"vk": 75, "nome": "K", "ctrl": false, "shift": false,
               "alt": false}, "duracao": 120, "modo": "reinicia", "antes": 0, "som": "padrao:Potion.mp3",
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

import overlay

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

ARQUIVO = os.path.join(BASE_DIR, "audio_timers.json")
PASTA_SONS = os.path.join(BASE_DIR, "sons")
PASTA_SONS_USUARIO = os.path.join(BASE_DIR, "sons_usuario")
# sons que vêm com o app (no .exe ficam dentro do pacote, sys._MEIPASS)
PASTA_SONS_PADRAO = os.path.join(getattr(sys, "_MEIPASS", BASE_DIR), "sons_padrao")
SOM_PADRAO = "padrao:Potion.mp3"
MODOS = ("reinicia", "ignora", "loop")
PROCESSOS_TIBIA = ("client.exe", "tibia.exe")

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
PADRAO = {"ligado": True, "volume": 90, "so_tibia": True, "barra": dict(overlay.BARRA_PADRAO),
          "alerta": dict(overlay.ALERTA_PADRAO), "timers": []}


def carregar(caminho=None):
    try:
        with open(caminho or ARQUIVO, "r", encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, json.JSONDecodeError):
        d = {}
    cfg = {**PADRAO, **{k: v for k, v in d.items() if k in PADRAO}}
    cfg["timers"] = [normalizar(t) for t in cfg.get("timers") or [] if isinstance(t, dict)]
    cfg["barra"] = overlay.normalizar_barra(cfg.get("barra"))
    cfg["alerta"] = overlay.normalizar_alerta(cfg.get("alerta"))
    return cfg


def salvar(cfg, caminho=None):
    caminho = caminho or ARQUIVO
    tmp = caminho + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=1)
    os.replace(tmp, caminho)


def _duracao(v):
    """Segundos (com milissegundos) entre 0,1 s e 24 h; vazio, zero ou inválido vira o padrão (60 s)."""
    try:
        d = float(v or 0)
    except (TypeError, ValueError):
        d = 0
    return 60.0 if d <= 0 else round(max(0.1, min(24 * 3600.0, d)), 3)


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
        "antes": round(max(0.0, min(24 * 3600.0, float(t.get("antes") or 0))), 3),
        "som": str(t.get("som") or SOM_PADRAO),
        "volume": max(0, min(100, int(t.get("volume") if t.get("volume") is not None else 100))),
        "ativo": bool(t.get("ativo", True)),
        "alerta": bool(t.get("alerta", False)),   # texto na tela do Tibia na hora do aviso
        "barra": bool(t.get("barra", False)),     # barra correndo na tela do Tibia enquanto conta
        "cor": _cor(t.get("cor")),
        "mensagem": str(t.get("mensagem") or "").strip()[:60],   # texto do alerta (vazio = automático)
        "fonte": max(14, min(96, int(t.get("fonte") or 34))),    # tamanho da letra do alerta
        "fixo": bool(t.get("fixo", False)),                      # alerta fica na tela até apertar a tecla de novo
        "piscar": _piscar(t.get("piscar")),                       # alerta pisca nos últimos N segundos (0 = não)
    }


PISCAR_OPCOES = (0, 1, 2, 3, 5)


def _piscar(v):
    try:
        v = int(v or 0)
    except (TypeError, ValueError):
        return 0
    return v if v in PISCAR_OPCOES else 0


def texto_piscando(t):
    """Texto do alerta piscando no fim (com aviso 0, o texto automático seria "acabou!" antes da hora)."""
    if t["mensagem"]:
        return t["mensagem"]
    return texto_alerta(t) if min(t["antes"], t["duracao"]) else f"{t['nome']} acabando!"


def _cor(c):
    if c in overlay.CORES:
        return c
    if isinstance(c, str) and len(c) == 7 and c.startswith("#"):
        try:
            int(c[1:], 16)
            return c.upper()
        except ValueError:
            pass
    return "amarelo"


def texto_alerta(t):
    if t["mensagem"]:
        return t["mensagem"]
    antes = min(t["antes"], t["duracao"])
    return f"{t['nome']} acaba em {antes:g}s" if antes else f"{t['nome']} acabou!"


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
    """[{id, nome}]: os que vêm com o app + bipes gerados + os importados pelo usuário."""
    sons = [{"id": "padrao:" + a, "nome": os.path.splitext(a)[0]} for a in sons_padrao()]
    sons += [{"id": "pronto:" + k, "nome": nome} for k, (nome, _) in SONS_PRONTOS.items()]
    if os.path.isdir(PASTA_SONS_USUARIO):
        for arq in sorted(os.listdir(PASTA_SONS_USUARIO), key=str.lower):
            if arq.lower().endswith((".wav", ".mp3")):
                sons.append({"id": "usuario:" + arq, "nome": "🎵 " + os.path.splitext(arq)[0]})
    return sons


def sons_padrao():
    if not os.path.isdir(PASTA_SONS_PADRAO):
        return []
    return sorted((a for a in os.listdir(PASTA_SONS_PADRAO) if a.lower().endswith((".wav", ".mp3"))), key=str.lower)


def caminho_do_som(som_id):
    tipo, _, nome = (som_id or "").partition(":")
    if tipo == "padrao" and nome and os.path.basename(nome) == nome:
        caminho = os.path.join(PASTA_SONS_PADRAO, nome)
        if os.path.isfile(caminho):
            return caminho
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


def fmt_tempo(seg):
    seg = max(0, int(seg + .999))
    return f"{seg // 60}:{seg % 60:02d}" if seg < 3600 else f"{seg // 3600}:{seg % 3600 // 60:02d}:{seg % 60:02d}"


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
        self.alerta = overlay.Overlay()
        self.barras = overlay.Barras()
        self._barras_ate = 0          # teste de posição: mostra barras de exemplo até esse instante
        self._ultima_barra = 0
        self._barras_visiveis = False
        self._alerta_fixo = None      # id do timer cujo alerta está parado na tela esperando a tecla
        self._piscou = {}             # id -> fim da volta em que o alerta já começou a piscar
        self._pisca_dono = None       # id do timer cujo alerta está piscando agora
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

    def testar_alerta(self, cor="amarelo", texto="Poção acaba em 3s", fonte=34, segundos=4, piscar=False):
        """segundos=0: o alerta fica na tela até parar_teste() (teste ao vivo)."""
        return self.alerta.mostrar(texto or "Poção acaba em 3s", cor, segundos, so_tibia=False, tamanho=fonte,
                                   pos=self.cfg["alerta"], piscar=piscar)

    def _talvez_piscar(self, e, agora):
        """Nos últimos N s da volta o alerta pisca até acabar. Devolve True se está piscando nesta volta."""
        c = e.cfg
        if not (c["alerta"] and c["piscar"] and e.rodando):
            return False
        if self._piscou.get(c["id"]) == e.fim:
            return True
        resta = e.fim - agora
        if resta > c["piscar"]:
            return False
        self._piscou[c["id"]] = e.fim
        self._pisca_dono = c["id"]
        if c["fixo"]:
            self._alerta_fixo = c["id"]
        self.alerta.mostrar(texto_piscando(c), c["cor"], 0 if c["fixo"] else resta,
                            tamanho=c["fonte"], pos=self.cfg["alerta"], piscar=True)
        return True

    def parar_teste(self):
        """Some com o alerta e as barras de exemplo."""
        self._barras_ate = 0
        self._ultima_barra = 0
        self.alerta.esconder()

    def testar_barras(self, segundos=6, nome=None, cor=None, loop=False):
        """Mostra barras de exemplo (com a configuração atual) para ajustar a posição.
        Com nome/cor, mostra só a barra daquele timer, do jeito que vai aparecer."""
        self._barras_exemplo = (nome or "Timer", _cor(cor)) if (nome or cor) else None
        self._barras_ini = time.monotonic()
        self._barras_ate = self._barras_ini + (10 ** 9 if loop else segundos)   # loop: até parar_teste()
        self._ultima_barra = 0

    def _itens_barras(self, agora):
        if agora < self._barras_ate:
            frac = 1 - ((agora - getattr(self, "_barras_ini", agora)) % 6) / 6   # esvazia em 6 s e recomeça
            if getattr(self, "_barras_exemplo", None):
                nome, cor = self._barras_exemplo
                return [(nome, frac, fmt_tempo(frac * 60), cor)]
            return [("Exemplo: Poção", frac, fmt_tempo(frac * 120), "laranja"),
                    ("Exemplo: Utito", frac * .5, fmt_tempo(frac * 10), "verde")]
        return [(e.cfg["nome"], e.restante(agora) / e.cfg["duracao"], fmt_tempo(e.restante(agora)), e.cfg["cor"])
                for e in self.estados.values() if e.rodando and e.cfg["barra"]]

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
                            if self._alerta_fixo == e.cfg["id"] or self._pisca_dono == e.cfg["id"]:
                                self._alerta_fixo = self._pisca_dono = None   # recomeçou: tira o alerta da tela
                                self.alerta.esconder()
                            mudou = True
            for e in self.estados.values():
                fim_volta = e.fim
                piscando = self._talvez_piscar(e, agora)
                if e.tick(agora):
                    self.tocador.tocar(caminho_do_som(e.cfg["som"]), e.cfg["volume"] * self.cfg["volume"] / 100)
                    # o aviso caiu dentro do trecho piscando: o alerta já está na tela (piscando)
                    if e.cfg["alerta"] and not (piscando and e.fim == fim_volta):
                        fixo = e.cfg["fixo"]
                        if self._pisca_dono == e.cfg["id"]:
                            self._pisca_dono = None
                        self.alerta.mostrar(texto_alerta(e.cfg), e.cfg["cor"], 0 if fixo else 3,
                                            tamanho=e.cfg["fonte"], pos=self.cfg["alerta"])
                        self._alerta_fixo = e.cfg["id"] if fixo else None
                    mudou = True
            rodando = any(e.rodando for e in self.estados.values())
            itens = self._itens_barras(agora)
            cfg_barra = self.cfg["barra"]
        # barras por cima do Tibia: 10x por segundo enquanto há alguma (e some quando não há mais)
        if itens and agora - self._ultima_barra > .1:
            self._ultima_barra = agora
            self._barras_visiveis = True
            self.barras.atualizar(itens, cfg_barra, so_tibia=agora >= self._barras_ate)
        elif not itens and self._barras_visiveis:
            self._barras_visiveis = False
            self.barras.atualizar([], cfg_barra)
        # manda o estado para a tela: na hora quando muda, e 4x por segundo enquanto algo conta
        if self._ao_mudar and (mudou or (rodando and agora - self._ultimo_envio > .25)):
            self._ultimo_envio = agora
            self._ao_mudar(self.estado())


# ---------------------------------------------------------------------------
# Importar do TibiaVision instalado neste PC (sons e timers da própria pessoa)
# ---------------------------------------------------------------------------
TV_DADOS = os.path.join(os.environ.get("APPDATA", ""), "TibiaVision")
# ModifierKeys do WPF (o TibiaVision é .NET): Alt=1, Control=2, Shift=4
_TV_ALT, _TV_CTRL, _TV_SHIFT = 1, 2, 4


def pastas_tibiavision():
    """Onde o TibiaVision pode estar instalado (registro do Windows + lugares comuns)."""
    achadas = []
    try:
        import winreg
        for raiz in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            for base in (r"Software\Microsoft\Windows\CurrentVersion\Uninstall",
                         r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"):
                try:
                    chave = winreg.OpenKey(raiz, base)
                except OSError:
                    continue
                for i in range(winreg.QueryInfoKey(chave)[0]):
                    try:
                        sub = winreg.OpenKey(chave, winreg.EnumKey(chave, i))
                        if "tibiavision" in str(winreg.QueryValueEx(sub, "DisplayName")[0]).lower():
                            achadas.append(winreg.QueryValueEx(sub, "InstallLocation")[0])
                    except OSError:
                        pass
    except ImportError:
        pass
    achadas += [os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "TibiaVision"),
                os.path.join(os.environ.get("ProgramFiles", ""), "TibiaVision"), r"Y:\TibiaVision"]
    vistos, out = set(), []
    for p in achadas:
        p = os.path.normpath(p) if p else ""
        if p and p.lower() not in vistos and os.path.isdir(os.path.join(p, "Resources", "Sounds")):
            vistos.add(p.lower())
            out.append(p)
    return out


def perfis_tibiavision():
    """[{nome, arquivo, timers}] dos perfis de áudio do TibiaVision deste PC."""
    perfis = []
    pasta = os.path.join(TV_DADOS, "Profiles")
    candidatos = [(os.path.join(TV_DADOS, "tibia_audio_settings.json"), "Atual")]
    if os.path.isdir(pasta):
        candidatos += [(os.path.join(pasta, a), a[:-len(".audio.json")]) for a in sorted(os.listdir(pasta))
                       if a.endswith(".audio.json")]
    for arq, nome in candidatos:
        try:
            with open(arq, "r", encoding="utf-8-sig") as f:
                n = len(json.load(f).get("Timers") or [])
        except (OSError, json.JSONDecodeError, AttributeError):
            continue
        perfis.append({"nome": nome, "arquivo": arq, "timers": n})
    return perfis


def importar_sons_tibiavision():
    """Copia os sons do TibiaVision instalado para sons_usuario/. Devolve quantos copiou."""
    n = 0
    os.makedirs(PASTA_SONS_USUARIO, exist_ok=True)
    for pasta in pastas_tibiavision():
        origem = os.path.join(pasta, "Resources", "Sounds")
        for arq in os.listdir(origem):
            if (arq.lower().endswith((".mp3", ".wav")) and not os.path.isfile(os.path.join(PASTA_SONS_USUARIO, arq))
                    and not os.path.isfile(os.path.join(PASTA_SONS_PADRAO, arq))):
                shutil.copy2(os.path.join(origem, arq), os.path.join(PASTA_SONS_USUARIO, arq))
                n += 1
    return n


def _som_tibiavision(t):
    custom = t.get("CustomSoundPath")
    if custom and os.path.isfile(custom) and custom.lower().endswith((".mp3", ".wav")):
        try:
            return importar_som(custom)
        except (OSError, ValueError):
            pass
    nome = str(t.get("SoundName") or "")
    for ext in (".mp3", ".wav"):
        if nome and os.path.isfile(os.path.join(PASTA_SONS_PADRAO, nome + ext)):
            return "padrao:" + nome + ext
        if nome and os.path.isfile(os.path.join(PASTA_SONS_USUARIO, nome + ext)):
            return "usuario:" + nome + ext
    return SOM_PADRAO


def timers_do_tibiavision(arquivo):
    """Converte os timers de um perfil do TibiaVision para o formato do app (chame importar_sons_tibiavision antes)."""
    with open(arquivo, "r", encoding="utf-8-sig") as f:
        dados = json.load(f)
    out = []
    for t in dados.get("Timers") or []:
        mods = int(t.get("HotkeyModifiers") or 0)
        vk = int(t.get("HotkeyCode") or 0)
        out.append(normalizar({
            "nome": t.get("Name"), "duracao": t.get("Duration"), "volume": t.get("Volume"),
            "tecla": {"vk": vk, "nome": nome_da_tecla(vk) if vk and _u32 else "", "ctrl": bool(mods & _TV_CTRL),
                      "shift": bool(mods & _TV_SHIFT), "alt": bool(mods & _TV_ALT)},
            "modo": "reinicia" if t.get("RetriggerEnabled", True) else "ignora",
            "alerta": t.get("ShowVisualAlert", False), "mensagem": t.get("AlertMessage") or "",
            "cor": t.get("AlertColor") or "branco", "fonte": t.get("AlertFontSize") or 34,
            "fixo": t.get("AlertStayUntilHotkey", False), "som": _som_tibiavision(t),
        }))
    return out
