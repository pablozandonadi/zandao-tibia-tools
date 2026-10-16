"""Funções que a página (web/index.html) chama via window.pywebview.api.*"""

import json
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import webview

import atualizacoes
import publicacao_beta
import radio_brasilhits
import audio_timers
import voz
import assistente_tibiano
import mirror_core
from mirror_service import MirrorService
import backup
import damage_core
import embuimentos as emb
import equipamentos
import historico
import classificador
import hunt
import itens_set
import monstros
import planejador
import hunt_catalog
import organizer
import prints_schedule
import personagens
import task_items
import task_item_images
import guild_stats
import posturas
import proficiencia
import precos
import preys_charms
import roda
import roda as roda_mod
import sets
import stats_set
import tibia_info
import zandaobot
import world_board
import zandaobot_report
from versao import VERSAO_APP

from app_paths import data_dir, install_dir, resource_dir
BASE_DIR = data_dir()

IMBUEMENTS_PATH = os.path.join(install_dir(), "data", "imbuements.json")
DADOS_PATH = os.path.join(BASE_DIR, "dados_embuimentos.json")

PREFS_PATH = os.path.join(BASE_DIR, "preferencias.json")
RASCUNHO_PATH = os.path.join(BASE_DIR, "hunt_atual.json")  # textos colados da última hunt, para reabrir o app sem perder
MAX_MONSTROS = 15  # fichas buscadas por análise (os de mais kills / mais dano)

SEM_JANELA = getattr(subprocess, "CREATE_NO_WINDOW", 0)


# ---------- janela: sempre por cima + transparência (Win32) ----------
def hwnd_do_app(titulo):
    """Janela de topo deste processo com o título do app (não usa window.native: evita chamada entre threads)."""
    import ctypes
    from ctypes import wintypes

    u32 = ctypes.windll.user32
    meu_pid = os.getpid()
    achou = []

    def cb(h, _):
        pid = wintypes.DWORD()
        u32.GetWindowThreadProcessId(h, ctypes.byref(pid))
        if pid.value == meu_pid and u32.IsWindowVisible(h):
            n = u32.GetWindowTextLengthW(h)
            buf = ctypes.create_unicode_buffer(n + 1)
            u32.GetWindowTextW(h, buf, n + 1)
            if buf.value == titulo:
                achou.append(h)
                return False
        return True

    u32.EnumWindows(ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(cb), 0)
    return achou[0] if achou else None


def aplicar_janela(hwnd, por_cima, opacidade):
    """por_cima: fica na frente de outras janelas (inclusive do Tibia) mesmo sem foco.
    opacidade: 40 a 100 (%). Não ativa nem traz a janela para frente (SWP_NOACTIVATE)."""
    import ctypes

    u32 = ctypes.windll.user32
    u32.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p] + [ctypes.c_int] * 4 + [ctypes.c_uint]
    GWL_EXSTYLE, WS_EX_LAYERED, LWA_ALPHA = -20, 0x00080000, 0x2
    HWND_TOPMOST, HWND_NOTOPMOST = ctypes.c_void_p(-1), ctypes.c_void_p(-2)
    SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE = 0x1, 0x2, 0x10

    alpha = max(40, min(100, int(opacidade)))
    estilo = u32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    if alpha >= 100:
        if estilo & WS_EX_LAYERED:
            u32.SetWindowLongW(hwnd, GWL_EXSTYLE, estilo & ~WS_EX_LAYERED)
    else:
        u32.SetWindowLongW(hwnd, GWL_EXSTYLE, estilo | WS_EX_LAYERED)
        u32.SetLayeredWindowAttributes(hwnd, 0, round(alpha * 255 / 100), LWA_ALPHA)
    u32.SetWindowPos(hwnd, HWND_TOPMOST if por_cima else HWND_NOTOPMOST, 0, 0, 0, 0,
                     SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE)
    import overlay
    overlay._hwnd_app_fixado = hwnd if por_cima else None


WS_CAPTION, WS_THICKFRAME = 0x00C00000, 0x00040000   # barra de título (com a borda) e borda de redimensionar


def estilo_moldura(estilo, mostrar):
    """Estilo da janela com ou sem a barra de título do Windows. A borda de redimensionar (WS_THICKFRAME) não é mexida."""
    return (estilo | WS_CAPTION) if mostrar else (estilo & ~WS_CAPTION)


def posicao_arrasto(origem, cursor_inicio, cursor_agora):
    """Canto da janela quando o mouse andou do cursor_inicio até o cursor_agora (a janela acompanha o mouse)."""
    return (origem[0] + cursor_agora[0] - cursor_inicio[0], origem[1] + cursor_agora[1] - cursor_inicio[1])


def definir_moldura(hwnd, mostrar):
    """Mostra ou tira a barra de título do Windows da janela (modo gadget: sem barra, só a faixa do app com o X)."""
    import ctypes

    u32 = ctypes.windll.user32
    u32.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p] + [ctypes.c_int] * 4 + [ctypes.c_uint]
    GWL_STYLE = -16
    SWP_NOSIZE, SWP_NOMOVE, SWP_NOZORDER, SWP_NOACTIVATE, SWP_FRAMECHANGED = 0x1, 0x2, 0x4, 0x10, 0x20
    estilo = u32.GetWindowLongW(hwnd, GWL_STYLE)
    u32.SetWindowLongW(hwnd, GWL_STYLE, estilo_moldura(estilo, mostrar))
    u32.SetWindowPos(hwnd, None, 0, 0, 0, 0, SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED)


def _cursor():
    """Posição do mouse na tela, em pixels."""
    import ctypes
    from ctypes import wintypes

    p = wintypes.POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(p))
    return (p.x, p.y)


def _canto_da_janela(hwnd):
    import ctypes
    from ctypes import wintypes

    r = wintypes.RECT()
    ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(r))
    return (r.left, r.top)


def _mover_janela(hwnd, x, y):
    import ctypes

    u32 = ctypes.windll.user32
    u32.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p] + [ctypes.c_int] * 4 + [ctypes.c_uint]
    SWP_NOSIZE, SWP_NOZORDER, SWP_NOACTIVATE = 0x1, 0x4, 0x10
    u32.SetWindowPos(hwnd, None, int(x), int(y), 0, 0, SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE)


PREFS_LOCK = threading.RLock()
PERSONAGEM_LOCK = threading.RLock()


def ler_prefs():
    with PREFS_LOCK:
        try:
            with open(PREFS_PATH, "r", encoding="utf-8") as f:
                p = json.load(f)
        except (OSError, json.JSONDecodeError):
            p = {}
        if not isinstance(p, dict):
            p = {}
        prefs = {"por_cima": bool(p.get("por_cima", False)), "opacidade": int(p.get("opacidade", 100)), "escala": _escala(p.get("escala"))}
        tamanhos = p.get("tamanhos", {})
        if isinstance(tamanhos, dict):
            validos = {modo: list(tamanho) for modo in ("normal", "gadget")
                       if (tamanho := _tamanho_valido(tamanhos.get(modo)))}
            if validos:
                prefs["tamanhos"] = validos
        if p.get("modo") in ("normal", "gadget"):
            prefs["modo"] = p["modo"]
        if "radio" in p:
            prefs["radio"] = radio_brasilhits.normalize_preferences(p.get("radio"))
        return prefs


def _tamanho_valido(valor):
    if not isinstance(valor, (list, tuple)) or len(valor) != 2:
        return None
    try:
        w, h = map(int, valor)
    except (ValueError, TypeError, OverflowError):
        return None
    return (w, h) if 280 <= w <= 16000 and 320 <= h <= 16000 else None


def salvar_prefs(alteracoes):
    with PREFS_LOCK:
        prefs = ler_prefs()
        prefs.update(alteracoes)
        try:
            with open(PREFS_PATH, "w", encoding="utf-8") as f:
                json.dump(prefs, f, indent=2)
        except OSError:
            pass
        return prefs


ESCALA_MIN, ESCALA_MAX = 50, 130           # tamanho da interface em % (menor para virar um gadget no canto do Tibia)
TAMANHO_GADGET = (340, 640)                # presets de tamanho da janela
TAMANHO_NORMAL = (1320, 840)


def _escala(v):
    """Tamanho da interface em %, entre ESCALA_MIN e ESCALA_MAX (100 se não for número)."""
    try:
        return max(ESCALA_MIN, min(ESCALA_MAX, int(v)))
    except (TypeError, ValueError):
        return 100


# ---------- área de transferência (Win32, aceita acentos) ----------
def copiar_para_clipboard(texto):
    import ctypes
    from ctypes import wintypes

    k32, u32 = ctypes.windll.kernel32, ctypes.windll.user32
    k32.GlobalAlloc.restype = wintypes.HGLOBAL
    k32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    k32.GlobalLock.restype = wintypes.LPVOID
    k32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    k32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    u32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]

    dados = texto.encode("utf-16-le") + b"\x00\x00"
    if not u32.OpenClipboard(None):
        return False
    try:
        u32.EmptyClipboard()
        h = k32.GlobalAlloc(0x0002, len(dados))  # GMEM_MOVEABLE
        p = k32.GlobalLock(h)
        ctypes.memmove(p, dados, len(dados))
        k32.GlobalUnlock(h)
        u32.SetClipboardData(13, h)  # CF_UNICODETEXT
        return True
    finally:
        u32.CloseClipboard()


def ler_clipboard():
    import ctypes
    from ctypes import wintypes

    k32, u32 = ctypes.windll.kernel32, ctypes.windll.user32
    u32.GetClipboardData.restype = wintypes.HANDLE
    k32.GlobalLock.restype = wintypes.LPVOID
    k32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    k32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    if not u32.OpenClipboard(None):
        return ""
    try:
        h = u32.GetClipboardData(13)  # CF_UNICODETEXT
        if not h:
            return ""
        p = k32.GlobalLock(h)
        try:
            return ctypes.wstring_at(p) if p else ""
        finally:
            k32.GlobalUnlock(h)
    finally:
        u32.CloseClipboard()


def seq_clipboard():
    """Número que o Windows aumenta a cada cópia (barato: dá para checar várias vezes por segundo)."""
    import ctypes
    return ctypes.windll.user32.GetClipboardSequenceNumber()


def _ficha_para_tela(k, kills):
    return {
        "nome": k["nome"], "imagem": k.get("imagem"), "hp": k.get("hp"), "xp": k.get("xp"),
        "resist": k.get("resist", {}), "incertos": k.get("incertos", []), "kills": kills,
        "ataques": [a for a in k.get("ataques", []) if not a.get("cura")][:8],
        "fontes": k.get("fontes", {}), "parcial": k.get("parcial", []),
        "wiki": "https://tibia.fandom.com/wiki/" + k["nome"].replace(" ", "_"),
    }


class API:
    def __init__(self):
        self._radio = radio_brasilhits.Client()
        self._window = None  # preenchido em zandao_tibia_tools.py (nunca público: o pywebview recursa nele)
        self._imbs = emb.carregar_imbuements(IMBUEMENTS_PATH)
        self._organizando = False
        self._prints_lock = threading.Lock()
        self._prints_agenda = None
        self._prints_agenda_lock = threading.Lock()
        self._atualizacao_info = None  # release lida em verificar_atualizacao, até instalar_atualizacao
        self._dano_cache = {}  # assinatura da hunt -> monstros/dano já analisados (para o Salvar)
        self._personagem_auto_stop = threading.Event()
        self._personagem_auto_thread = None
        self._personagem_auto_pendente = None
        self._personagem_revisao = 0
        self._audio = None      # motor dos timers de áudio (liga em audio_iniciar)
        self._voz = None
        self._voz_lock = threading.Lock()
        self._mirror = None
        self._mirror_api_lock = threading.Lock()
        self._capturas = {}     # tipo ('party'/'solo'/'dano') -> {"texto", "t"}: últimos textos do Tibia copiados
        self._trava_capturas = threading.Lock()
        self._monitor = False
        from network_monitor import Monitor
        self._rede = Monitor(os.path.join(BASE_DIR, "rede_config.json"))

    # ================= mirrors por personagem e perfil =================
    def _mirror_obter(self):
        with PERSONAGEM_LOCK, self._mirror_api_lock:
            if self._mirror is None:
                self._mirror = MirrorService(personagens.carregar().get("atual", ""),
                                             emit=lambda state: self._emit("mirrorEstado", state))
            return self._mirror

    def _mirror_chamar(self, method, *args):
        try:
            return getattr(self._mirror_obter(), method)(*args)
        except (ValueError, TypeError, OSError, RuntimeError) as error:
            return {"erro": str(error)}

    def mirror_carregar(self):
        return self._mirror_chamar("carregar")

    def mirror_perfil(self, acao, id="", nome=""):
        return self._mirror_chamar("perfil", acao, id, nome)

    def mirror_recorte(self, acao, id="", dados=None):
        return self._mirror_chamar("recorte", acao, id, dados)

    def mirror_todos(self, acao):
        return self._mirror_chamar("todos", acao)

    def mirror_vincular(self, hwnd):
        return self._mirror_chamar("vincular", hwnd)

    def mirror_cancelar(self):
        return self._mirror_chamar("cancelar")

    def mirror_selecionar(self, modo, id=""):
        return self._mirror_chamar("selecionar", modo, id)

    def radio_catalogo(self):
        return self._radio.catalog()

    def radio_musica(self, station_id):
        return self._radio.now_playing(station_id)

    def radio_preferencias(self):
        return radio_brasilhits.normalize_preferences(ler_prefs().get("radio"))

    def radio_preferencias_salvar(self, value):
        prefs = radio_brasilhits.normalize_preferences(value)
        salvar_prefs({"radio": prefs})
        return prefs

    def radio_abrir_site(self):
        import webbrowser
        return webbrowser.open("https://www.brasilhits.com/")

    def _emit(self, funcao_js, dados):
        if self._window:
            self._window.evaluate_js(f"{funcao_js}({json.dumps(dados, ensure_ascii=False)})")

    def rede_estado(self, janela=300):
        self._rede.start()
        return self._rede.snapshot(janela)

    def rede_configurar(self, alteracoes):
        try:
            return self._rede.configure(alteracoes)
        except (ValueError, TypeError, OSError):
            return {"error_config": "Não foi possível salvar. Verifique os valores e tente novamente."}

    # ================= início =================
    def carregar(self):
        try:
            with open(DADOS_PATH, "r", encoding="utf-8") as f:
                dados = json.load(f)
        except (OSError, json.JSONDecodeError):
            dados = {}
        try:
            prints = organizer.carregar_config()
        except (OSError, json.JSONDecodeError):
            prints = dict(organizer.DEFAULTS)
        return {
            "imbuements": [
                {
                    "id": i["id"], "nome": i["name"], "sub": i.get("subtitle", ""), "grupo": i["group"],
                    "token": i["has_token"],
                    "itens": [{"nome": d["name"], "qtd": d["qty"], "key": emb.item_key(d["name"])} for d in i["items"]],
                    "scrollKey": emb.scroll_key(i["id"]),
                    "scrollNome": i.get("scroll_item_name", i["name"]),
                }
                for i in self._imbs
            ],
            "grupos": emb.GROUPS,
            "dados": {
                "token": dados.get("token", ""),
                "taxa": dados.get("taxa", emb.fmt(emb.DEFAULT_FEE)),
                "blank": dados.get("blank", emb.fmt(emb.DEFAULT_BLANK)),
                "fazer_scroll": dados.get("fazer_scroll", False),
                "selecionados": dados.get("selecionados", ["void", "vampirism", "strike"]),
                "precos": dados.get("precos", {}),
                "inventario": dados.get("inventario", {}),
                "mundo": dados.get("mundo"),                  # mundo a que pertencem os preços digitados (None = arquivo antigo)
                "por_mundo": dados.get("por_mundo", {}),      # preços digitados dos outros mundos {mundo: {precos, token, blank}}
                "blank_padrao": emb.fmt(emb.DEFAULT_BLANK),
            },
            "prints": prints,
            "pasta_padrao_tibia": organizer.PASTA_PADRAO_TIBIA if os.path.isdir(organizer.PASTA_PADRAO_TIBIA) else "",
        }

    # ================= embuimentos =================
    def calcular(self, entrada):
        """entrada = o mesmo formato de 'dados' devolvido por carregar(), com os textos digitados."""
        try:
            with open(DADOS_PATH, "w", encoding="utf-8") as f:
                json.dump(entrada, f, indent=2, ensure_ascii=False)
        except OSError:
            pass

        p = emb.parse_num
        estado = {
            "precos": {k: p(v) for k, v in entrada["precos"].items()},
            "inventario": {k: p(v) or 0 for k, v in entrada["inventario"].items()},
            "token": p(entrada["token"]), "taxa": p(entrada["taxa"]), "blank": p(entrada["blank"]),
            "fazer_scroll": bool(entrada["fazer_scroll"]),
        }
        sel_ids = set(entrada["selecionados"])
        sel = [i for i in self._imbs if i["id"] in sel_ids]
        if not sel:
            return {"vazio": True}

        resultados = [emb.calcular(i, estado) for i in sel]
        pl = emb.plano(resultados)
        saida = []
        for r in resultados:
            eco = emb.economia_vs_scroll(r)
            saida.append({
                "label": emb.label(r["imb"]),
                "faca": emb.o_que_fazer(r, r["melhor"], estado["fazer_scroll"]) if r["melhor"] else None,
                "custo": emb.gp(emb.custo_melhor(r)) if r["melhor"] else None,
                "economia": emb.gp(eco) if eco else None,
                "rotas": [
                    {
                        "label": ro["label"],
                        "custo": emb.gp(ro["custo"]) if ro["custo"] is not None else None,
                        "diff": emb.gp(ro["diff"]) if ro["diff"] else None,
                        "melhor": ro is r["melhor"],
                    }
                    for ro in r["rotas"]
                ],
            })
        return {
            "vazio": False,
            "falta": emb.campos_faltando(sel, estado),
            "resultados": saida,
            "plano": {
                "recomendado": emb.gp(pl["recomendado"]),
                "linhas": [
                    ["Tudo no market", emb.gp(pl["tudo_market"])],
                    ["Tudo com 6 tokens", emb.gp(pl["tudo_6"])],
                    ["Tudo com 4 tokens + último item", emb.gp(pl["tudo_4"])],
                    ["Tudo scroll pronto", emb.gp(pl["tudo_scroll"])],
                ],
                "economia": emb.gp(pl["economia"]),
                "tokens": emb.fmt(pl["tokens"]),
            },
            "texto": emb.texto_resultado(resultados, pl, estado["fazer_scroll"]),
        }

    # ----- histórico de preços (botão "Registrar preços de hoje", aviso ▲/▼ e gráfico) -----
    _precos_path = precos.PRECOS_PATH

    def _hoje(self):
        return date.today().isoformat()

    def precos_registrar(self, precos_texto, mundo=""):
        valores = {k: emb.parse_num(str(v or "")) for k, v in (precos_texto or {}).items()}
        try:
            return {"gravados": precos.registrar(valores, self._hoje(), self._precos_path, mundo)}
        except OSError:
            return {"erro": "Não consegui salvar o histórico de preços"}

    def precos_variacoes(self, precos_texto, mundo=""):
        hist, hoje = precos.carregar(self._precos_path, mundo), self._hoje()
        return {k: precos.variacao(emb.parse_num(str(v or "")), k, hoje, hist) for k, v in (precos_texto or {}).items()}

    def precos_serie(self, chave, mundo=""):
        return precos.serie(precos.carregar(self._precos_path, mundo), chave)

    def precos_apagar(self, chave, data, mundo=""):
        try:
            precos.apagar(chave, data, self._precos_path, mundo)
        except OSError:
            return {"erro": "Não consegui apagar esse registro (o arquivo de preços está bloqueado ou o disco está cheio)."}
        return self.precos_serie(chave, mundo)

    def precos_antigos(self):
        """Quantos registros de preço antigos (de antes da separação por mundo) ainda não foram movidos para um mundo."""
        return precos.contar_antigos(self._precos_path)

    def precos_mover_antigos(self, mundo):
        try:
            return {"movidos": precos.mover_antigos(mundo, self._precos_path)}
        except OSError:
            return {"erro": "Não consegui mover os preços antigos (arquivo bloqueado ou disco cheio)."}

    def task_itens_imagens(self, itens):
        return task_item_images.resolve(itens)

    def task_itens_analisar(self, texto, pessoas=1):
        return task_items.analyse(texto, pessoas)

    def copiar(self, texto):
        try:
            return copiar_para_clipboard(texto)
        except Exception:
            return False

    # ================= prints =================
    def escolher_pasta(self, atual):
        tipo = getattr(getattr(webview, "FileDialog", None), "FOLDER", None) or webview.FOLDER_DIALOG
        inicial = atual if atual and os.path.isdir(atual) else ""
        r = self._window.create_file_dialog(tipo, directory=inicial)
        return r[0].replace("\\", "/") if r else None

    def abrir_pasta(self, caminho):
        if caminho and os.path.isdir(caminho):
            os.startfile(caminho)
            return True
        return False

    def _agenda_prints(self):
        with self._prints_agenda_lock:
            if self._prints_agenda is None:
                self._prints_agenda = prints_schedule.Agendador(self._organizar_agendado)
                self._prints_agenda.iniciar()
            return self._prints_agenda

    def prints_rotina_estado(self):
        return self._agenda_prints().estado()

    def prints_rotina_salvar(self, rotina, cfg):
        try:
            rotina = prints_schedule.normalizar(rotina)
            cfg = {key: cfg.get(key, default) for key, default in organizer.DEFAULTS.items()}
            if rotina['enabled']:
                if not cfg['print-dir'] or not os.path.isdir(cfg['print-dir']):
                    raise ValueError('Escolha uma pasta de prints existente antes de ativar a rotina.')
                if not cfg['destination']:
                    raise ValueError('Escolha a pasta de destino antes de ativar a rotina.')
                if os.path.normcase(os.path.realpath(cfg['print-dir'])) == os.path.normcase(os.path.realpath(cfg['destination'])):
                    raise ValueError('A pasta de destino deve ser diferente da pasta de origem.')
            agenda = self._agenda_prints()
            organizer.salvar_config(cfg)
            return {'ok': True, 'estado': agenda.configurar(rotina, cfg)}
        except (OSError, ValueError, TypeError, AttributeError) as error:
            return {'ok': False, 'erro': str(error)}

    def prints_rotina_pausar(self):
        try:
            agenda = self._agenda_prints()
            estado = agenda.estado()
            return {'ok': True, 'estado': agenda.configurar({**estado['config'], 'enabled': False}, estado['prints'])}
        except (OSError, ValueError) as error:
            return {'ok': False, 'erro': str(error)}

    def _emit_prints(self, funcao, dados):
        try:
            self._emit(funcao, dados)
        except Exception:
            pass  # A operação continua se a janela estiver minimizada/recarregando.

    def organizar(self, cfg):
        if not self._prints_lock.acquire(blocking=False):
            return {"ok": False, "erro": "Já está organizando."}
        try:
            organizer.salvar_config(cfg)
            self._organizando = True
            threading.Thread(target=self._trabalho_organizar, args=(cfg,), daemon=True).start()
            return {"ok": True}
        except Exception as error:
            self._organizando = False
            self._prints_lock.release()
            return {"ok": False, "erro": f"Não consegui iniciar a organização: {error}"}

    def _executar_prints(self, cfg, agendado=False):
        try:
            if agendado:
                self._emit_prints('inicioPrints', {'automatico': True})
            resultado, por_tipo = organizer.organizar(cfg, lambda m: self._emit_prints("logPrints", m))
            if not agendado and cfg.get("open-when-done") and resultado["processadas"]:
                self.abrir_pasta(cfg["destination"])
            self._emit_prints("fimPrints", {"resultado": dict(resultado), "porTipo": por_tipo.most_common()})
            return {'ok': not bool(resultado['erros']),
                    'mensagem': f"{resultado['processadas']} prints novos; {resultado['existentes']} já salvos; {resultado['erros']} erros."}
        except Exception as error:
            self._emit_prints("erroPrints", str(error))
            return {'ok': False, 'mensagem': str(error)}

    def _trabalho_organizar(self, cfg):
        try:
            self._executar_prints(cfg)
        finally:
            self._organizando = False
            self._prints_lock.release()

    def _organizar_agendado(self, cfg):
        if not self._prints_lock.acquire(blocking=False):
            return {'ocupado': True}
        try:
            self._organizando = True
            return self._executar_prints(cfg, agendado=True)
        finally:
            self._organizando = False
            self._prints_lock.release()

    # ================= hunt analyser (loot split + dano) =================
    # ================= meus personagens (conferidos no tibia.com) =================
    def meus_personagens(self, atualizar=False):
        d = personagens.carregar()
        if not d["lista"]:
            antigo = (self.hunt_carregar()["entrada"] or {}).get("personagem")
            if antigo:
                personagens.adicionar(antigo)  # migra o nome que o app já lembrava (se existir no tibia.com)
        if atualizar:
            personagens.atualizar_levels()
        with PERSONAGEM_LOCK:
            return self._timers_do_personagem(personagens.carregar())

    def equip_recomendar(self, nome, distribuicao, elemento=None, vocacao=None, level=None):
        """Itens do set que protegem do dano da hunt, para uma vocação e level (os do personagem, ou os escolhidos).
        distribuicao: {elemento: parte do dano}; elemento: ordenar só por ele (None = pela hunt toda)."""
        nome = (nome or "").strip()
        info = None
        if nome:
            info = next((p for p in personagens.carregar()["lista"] if p["nome"].lower() == nome.lower()), None)                 or tibia_info.personagem(nome)
        voc = vocacao or (info or {}).get("vocacao")
        try:
            lvl = int(level) if str(level or "").strip() else (info or {}).get("level")
        except ValueError:
            lvl = None
        if not equipamentos.vocacao_base(voc) or not lvl:
            return {"erro": "Escolha o seu personagem (⚙) ou a vocação e o level para ver os itens."}
        itens = equipamentos.carregar_itens()
        if not itens:
            return {"erro": "Não consegui baixar a lista de itens da TibiaWiki (sem internet?)."}
        rec = equipamentos.recomendar(itens, voc, lvl, distribuicao or {}, elemento or None)
        return {"personagem": info and {"nome": info["nome"], "level": info.get("level"), "vocacao": info.get("vocacao")},
                "vocacao": equipamentos.vocacao_base(voc), "level": lvl, "elemento": elemento,
                "slots": [{"slot": s, "rotulo": r, "itens": rec.get(s, [])} for s, r in equipamentos.SLOTS]}

    def personagem_skills(self, nome, skills, modo="offensive"):
        """Guarda as skills base (sem itens) e o modo de combate do personagem: com elas o Combat Stats calcula Attack e Defence."""
        return personagens.salvar_skills(nome, skills, modo)

    def personagem_adicionar(self, nome):
        d, erro = personagens.adicionar(nome)
        if erro:
            return {"erro": erro}
        with PERSONAGEM_LOCK:
            return self._timers_do_personagem(personagens.carregar())

    def personagem_remover(self, nome):
        with PERSONAGEM_LOCK:
            return self._timers_do_personagem(personagens.remover(nome))

    def criaturas_locais(self, atualizar=False):
        return hunt_catalog.catalogo(atualizar)

    def criaturas_local_detalhes(self, id_, contexto='all', dias=90):
        return hunt_catalog.detalhes(id_, contexto, dias)

    def criaturas_local_usar(self, id_, modo='wiki', sessao='', input_index=0, contexto='all', dias=90):
        return hunt_catalog.preset(id_, modo, sessao, input_index, contexto, dias)

    def criaturas_catalogo(self, atualizar=False):
        return planejador.catalogo_visual(atualizar)

    def criaturas_importar(self, texto):
        return planejador.importar_texto(texto)

    def criaturas_hunts(self):
        """Só leitura: lista logs salvos com composição para comparar a mesma sessão."""
        return [{'id':h['id'], 'nome':h.get('nome') or 'Hunt sem nome', 'personagem':h.get('personagem') or '',
                 'data':h.get('data_hunt') or '', 'tem_dano':bool((h.get('entrada') or {}).get('dano'))}
                for h in historico.ordenar(historico.carregar()) if (h.get('entrada') or {}).get('solo')]

    def criaturas_importar_hunt(self, id_):
        h = historico.obter(id_)
        if not h:
            return {'erro':'Hunt não encontrada no histórico.'}
        entrada = h.get('entrada') or {}
        r = planejador.importar_texto(entrada.get('solo') or '')
        if 'erro' not in r:
            dano = entrada.get('dano') or ''
            parsed = damage_core.parse_damage_input(dano)
            real = any(v['valor'] > 0 for e,v in parsed['tipos'].items() if e != 'manadrain')
            r.update(log_texto=entrada.get('solo') or '', dano_texto=dano if real else '', real=real, hunt_nome=h.get('nome') or 'Hunt salva')
        return r

    def criaturas_analisar(self, selecao, atualizar=False, dano_texto=""):
        return planejador.analisar(selecao, atualizar, dano_texto)

    def guildstats_comparar(self, nomes, atualizar=False, interagir=False):
        return guild_stats.comparar(nomes, atualizar, interagir)

    def guildstats_buscar(self, nome="", aba="experience", atualizar=False, pagina=1, interagir=False):
        return guild_stats.buscar(nome or personagens.carregar()["atual"], aba, atualizar, pagina, interagir)

    def guildstats_abrir(self, nome, aba="experience"):
        return guild_stats.buscar(nome or personagens.carregar()["atual"], aba, True, 1, True)

    def personagem_usar(self, nome):
        with PERSONAGEM_LOCK:
            return self._timers_do_personagem(personagens.usar(nome))

    def personagem_auto_iniciar(self):
        with PERSONAGEM_LOCK:
            if self._personagem_auto_thread is not None and self._personagem_auto_thread.is_alive():
                return
            self._personagem_auto_stop.clear()
            self._personagem_auto_thread = threading.Thread(target=self._personagem_auto_monitorar,
                                                             name="personagem-tibia", daemon=True)
            self._personagem_auto_thread.start()

    def _personagem_auto_parar(self):
        self._personagem_auto_stop.set()
        thread = self._personagem_auto_thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2)

    def _personagem_auto_monitorar(self):
        while not self._personagem_auto_stop.wait(1):
            try:
                self._personagem_auto_sincronizar()
            except Exception:
                pass  # Uma janela fechada ou callback indisponível não encerra o monitor.

    def _personagem_auto_sincronizar(self):
        from overlay import personagem_tibia_em_foco
        nome = personagem_tibia_em_foco()
        with PERSONAGEM_LOCK:
            if self._personagem_auto_stop.is_set():
                return
            if nome:
                d = personagens.carregar()
                cadastrado = next((p["nome"] for p in d["lista"] if p["nome"].casefold() == nome.casefold()), None)
                if cadastrado and cadastrado != d["atual"] and personagem_tibia_em_foco() == nome:
                    self._personagem_auto_pendente = self.personagem_usar(cadastrado)
            pendente = getattr(self, "_personagem_auto_pendente", None)
        if pendente is not None and not self._personagem_auto_stop.is_set():
            self._emit("personagemEstado", pendente)
            self._personagem_auto_pendente = None

    def hunt_carregar(self):
        """Rascunho da última hunt (textos colados) para reabrir o app sem perder nada."""
        try:
            with open(RASCUNHO_PATH, "r", encoding="utf-8") as f:
                r = json.load(f)
        except (OSError, json.JSONDecodeError):
            r = {}
        return {"entrada": r.get("entrada") or {}, "id": r.get("id")}

    def _salvar_rascunho(self, entrada, id_):
        try:
            with open(RASCUNHO_PATH, "w", encoding="utf-8") as f:
                json.dump({"entrada": entrada, "id": id_}, f, ensure_ascii=False, indent=1)
        except OSError:
            pass

    # Cada Copy do Tibia apaga o anterior na área de transferência. Para o "Colar do Tibia" preencher os
    # 3 cards de uma vez, enquanto o programa está aberto ele guarda o último texto de cada tipo copiado.
    # Só textos reconhecidos como do Tibia são guardados (em memória); qualquer outra cópia é ignorada.
    VALIDADE_CAPTURA = 3 * 3600

    def hunt_monitor_iniciar(self):
        if not self._monitor:
            self._monitor = True
            threading.Thread(target=self._vigiar_clipboard, daemon=True).start()
            # baixa a lista de itens da TibiaWiki em segundo plano (cache de 30 dias), para os itens recomendados
            threading.Thread(target=equipamentos.carregar_itens, daemon=True).start()
        return self._tipos_capturados()

    def _tipos_capturados(self):
        agora = time.time()
        with self._trava_capturas:
            for t in [t for t, c in self._capturas.items() if agora - c["t"] > self.VALIDADE_CAPTURA]:
                del self._capturas[t]
            return sorted(self._capturas)

    def _vigiar_clipboard(self):
        ultimo = None
        while True:
            try:
                seq = seq_clipboard()
                if seq != ultimo:
                    ultimo = seq
                    texto = ler_clipboard()
                    tipo = hunt.detectar(texto)
                    if tipo:
                        with self._trava_capturas:
                            self._capturas[tipo] = {"texto": texto, "t": time.time()}
                        self._emit("huntCapturado", {"tipo": tipo, "tipos": self._tipos_capturados()})
            except Exception:
                pass
            time.sleep(0.5)

    def hunt_colar(self):
        """Colar do Tibia: os textos do Tibia copiados (um de cada tipo) + o que está na área de transferência agora."""
        try:
            atual = ler_clipboard()
        except Exception:
            atual = ""
        tipo_atual = hunt.detectar(atual)
        self._tipos_capturados()  # descarta capturas velhas
        with self._trava_capturas:
            textos = {t: c["texto"] for t, c in self._capturas.items()}
            self._capturas.clear()
        if tipo_atual:
            textos[tipo_atual] = atual
        return {"textos": textos, "vazio": not atual.strip()}

    def hunt_ler_clipboard(self):
        """Lê o que foi copiado no Tibia e diz qual dos três textos é."""
        try:
            texto = ler_clipboard()
        except Exception:
            texto = ""
        return {"texto": texto, "tipo": hunt.detectar(texto)}

    def hunt_detectar(self, texto):
        return hunt.detectar(texto)

    def _entrada(self, entrada):
        return {k: entrada.get(k) for k in ("nome", "party", "solo", "dano", "despesas", "excluidos", "personagem", "id", "prey", "charms", "duracao", "roda", "set", "postura")}

    def _mesma_hunt(self, id_, a):
        """id_ continua valendo para esta análise? Se a hunt salva é de outro horário, é outra hunt."""
        if not id_:
            return None
        antigo = historico.obter(id_)
        if not antigo:
            return None
        if antigo.get("data_hunt") and a.get("data") and antigo["data_hunt"] != a["data"]:
            return None
        return id_

    def hunt_analisar(self, entrada):
        """Só analisa (split, resumo, kills); NÃO grava no Histórico, isso é o botão Salvar (hunt_salvar).
        A parte de monstros/dano (internet) roda em segundo plano e chega depois em window.huntDano()."""
        entrada = self._entrada(entrada)
        self._salvar_rascunho({"personagem": entrada.get("personagem") or ""}, None)  # só lembra o personagem
        a = hunt.montar(entrada)
        if a.get("vazio"):
            return {"analise": a, "id": entrada.get("id")}
        ass = hunt.assinatura(entrada)
        id_ = self._mesma_hunt(entrada.get("id"), a)
        salvo = historico.obter(id_) if id_ else None
        if salvo and salvo.get("assinatura") == ass and salvo.get("task_itens"):
            a["task_itens"] = salvo["task_itens"]
        # colou uma hunt de outro horário por cima de uma salva: o nome antigo não vale para ela
        nome = "" if (entrada.get("id") and not id_) else (entrada.get("nome") or "").strip()
        nome = nome or f"Hunt {a.get('data') or ''}".strip()
        threading.Thread(target=self._trabalho_dano, args=(id_, ass, nome, a), daemon=True).start()
        return {"analise": a, "id": id_, "assinatura": ass, "nome": nome, "texto": hunt.texto_discord(nome, a)}

    def hunt_salvar(self, entrada, pagos=None):
        """Botão Salvar: grava a hunt no Histórico (cria, ou atualiza a mesma se já foi salva)."""
        entrada = self._entrada(entrada)
        a = hunt.montar(entrada)
        if a.get("vazio"):
            return {"ok": False, "erro": "Cole pelo menos um texto do Tibia antes de salvar."}
        ass = hunt.assinatura(entrada)
        id_ = self._mesma_hunt(entrada.get("id"), a)
        nome = (entrada.get("nome") or "").strip() or f"Hunt {a.get('data') or ''}".strip()
        registro = {
            "id": id_, "assinatura": ass, "nome": nome, "data_hunt": a.get("data"),
            "personagem": (entrada.get("personagem") or "").strip(),
            "entrada": {k: entrada.get(k) or ("" if k in ("party", "solo", "dano", "duracao") else [])
                        for k in ("party", "solo", "dano", "despesas", "excluidos", "duracao")},  # duracao: tempo real digitado
            "resumo": a["resumo"], "membros": a.get("personagens", []), "monstros": a.get("kills", [])[:20],
            "pagos": list(pagos or []),
            "task_itens": a.get("task_itens"),
        }
        for campo in ("prey", "charms", "roda", "set", "postura"):  # None = o usuário não mexeu: o historico mantém o gravado
            if entrada.get(campo) is not None:
                registro[campo] = entrada[campo]
        extra = self._dano_cache.get(ass)  # análise de dano já pronta (monstros com imagem, proteções)
        if extra:
            registro.update(extra)
        salvo = historico.salvar(registro)
        return {"ok": True, "id": salvo["id"], "nome": salvo["nome"]}

    def _trabalho_dano(self, id_, ass, nome, a):
        """Busca as fichas dos monstros (wiki/TibiaData, com cache) e monta a análise de dano."""
        try:
            jogadores = {n.lower() for n in a.get("personagens", [])}
            pedidos = {}  # nome singular -> kills
            for k in a.get("kills", []):
                pedidos[monstros.singularizar(k["nome"])] = k["kills"]
            for f in (a.get("dano_input") or {}).get("fontes", []):
                s = monstros.singularizar(f["nome"])
                if f["nome"].lower() not in jogadores and s not in pedidos and not f["nome"].startswith("("):
                    pedidos[s] = None
            if not pedidos and not (a.get("dano_input") or {}).get("tipos"):
                self._emit("huntDano", {"id": id_, "assinatura": ass, "vazio": True})
                return

            lista = monstros.lista_criaturas()
            alvos, fora, imagem_por_nome = [], [], {}
            for s, kills in pedidos.items():
                c = monstros.casar_criatura(s, lista) if lista else None
                if c:
                    imagem_por_nome[s] = (monstros.canonico(c["name"]), c.get("image_url"))
                    if not any(x["race"] == c["race"] for x in alvos):
                        alvos.append({"nome": monstros.canonico(c["name"]), "race": c["race"],
                                      "imagem": c.get("image_url"), "kills": kills})
                elif lista:
                    fora.append(monstros.canonico(s))
                else:  # sem lista (offline e sem cache): tenta direto pelo nome
                    alvos.append({"nome": monstros.canonico(s), "race": None, "imagem": None, "kills": kills})
            alvos.sort(key=lambda x: -(x["kills"] or 0))
            alvos = alvos[:MAX_MONSTROS]

            with ThreadPoolExecutor(max_workers=6) as ex:
                fichas = list(ex.map(lambda x: monstros.carregar_monstro(x["nome"], x["race"], x["imagem"]), alvos))
            mons = [{"nome": x["nome"], "kills": x["kills"], "ficha": f} for x, f in zip(alvos, fichas)]
            analise = damage_core.analisar(mons, a.get("dano_input"), monstros.singularizar)
            if analise and fora:
                analise["avisos"].insert(0, "Não reconhecidos como monstro (ignorados): " + ", ".join(fora[:6]) + ".")
            if analise and not lista:
                analise["avisos"].insert(0, "Sem internet e sem cache: fichas dos monstros podem estar incompletas.")

            fichas_tela = [_ficha_para_tela(f, x["kills"]) for x, f in zip(alvos, fichas)]
            kills = []
            for k in a.get("kills", []):
                canon, img = imagem_por_nome.get(monstros.singularizar(k["nome"]), (monstros.canonico(k["nome"]), None))
                kills.append({"nome": canon, "kills": k["kills"], "imagem": img})
            if analise:
                extra = {"monstros": kills[:20], "dano": {
                    "elementos": analise["elementos"], "protecoes": analise["protecoes"],
                    "ofensivo": [o for o in analise["ofensivo"] if not o["sem_dados"]][:3],
                }}
                self._dano_cache[ass] = extra  # entra no Histórico quando o usuário clicar em Salvar
                salvo = historico.obter(id_) if id_ else None
                if salvo and salvo.get("assinatura") == ass:  # já estava salva com estes textos: completa
                    historico.atualizar(id_, **extra)
            self._emit("huntDano", {"id": id_, "assinatura": ass, "analise": analise, "fichas": fichas_tela,
                                    "kills": kills, "texto": hunt.texto_discord(nome, a, analise)})
        except Exception as e:
            self._emit("huntDano", {"id": id_, "assinatura": ass, "erro": str(e)})

    def hunt_pago(self, id_, chave, pago):
        h = historico.obter(id_)
        if not h:
            return False
        pagos = [p for p in h.get("pagos", []) if p != chave] + ([chave] if pago else [])
        historico.atualizar(id_, pagos=pagos)
        return True

    def hunt_historico(self, personagem="", tamanho="", monstro=""):
        todas = historico.ordenar(historico.carregar())
        personagens = sorted({h.get("personagem") for h in todas if h.get("personagem")}, key=str.lower)
        lista = historico.filtrar(todas, personagem, tamanho, monstro)
        return {
            "personagens": personagens,
            "monstros": [{"nome": m, "hunts": q} for m, q in historico.opcoes_monstros(todas)],
            "totais": historico.totais(lista),
            "hunts": [{
                "id": h["id"], "nome": h.get("nome"), "data": h.get("data_hunt") or (h.get("criado_em") or "")[:16].replace("T", " "),
                "personagem": h.get("personagem"), "membros": h.get("membros", []), "resumo": h.get("resumo") or {},
                "monstros": (h.get("monstros") or [])[:4],
                "protecoes": [p["rotulo"] for p in ((h.get("dano") or {}).get("protecoes") or [])[:3]],
                "importada": bool(h.get("importado_em")),
                "prey": historico.rotulo_prey(historico.normalizar_prey(h.get("prey"))), "prey_informada": "prey" in h,
                "charms": preys_charms.rotulo_charms(preys_charms.normalizar_charms(h.get("charms"))),
                "charms_informados": "charms" in h,
                "roda": roda.rotulo_roda(roda.normalizar_roda(h.get("roda"))), "roda_informada": "roda" in h,
                "set": sets.rotulo_set(sets.normalizar_set(h.get("set"))), "set_informado": "set" in h,
                "postura": posturas.rotulo_postura(posturas.normalizar_postura(h.get("postura"))), "postura_informada": "postura" in h,
            } for h in lista],
        }

    def hunt_panorama(self, personagem="", tamanho="", monstro=""):
        """Comparar todas: as hunts do filtro atual numa tabela/ranking."""
        lista = historico.filtrar(historico.carregar(), personagem, tamanho, monstro)
        if len(lista) < 2:
            return {"erro": "Precisa de pelo menos 2 hunts salvas (com esse filtro) para comparar."}
        return historico.panorama(lista)

    def hunt_comparar(self, ids):
        """Compara de 2 a 4 hunts do histórico (na ordem em que foram escolhidas)."""
        todas = {h["id"]: h for h in historico.carregar()}
        hunts = [todas[i] for i in ids if i in todas][:4]
        if len(hunts) < 2:
            return {"erro": "Escolha pelo menos 2 hunts para comparar."}
        return historico.comparar(hunts)

    def hunt_abrir(self, id_):
        h = historico.obter(id_)
        if not h:
            return None
        e = dict(h.get("entrada") or {})
        e.update({"nome": h.get("nome"), "personagem": h.get("personagem"), "id": h["id"], "pagos": h.get("pagos", []),
                  "prey": h.get("prey"), "charms": h.get("charms"), "roda": h.get("roda"), "set": sets.normalizar_set(h.get("set")), "postura": posturas.normalizar_postura(h.get("postura"))})
        return e

    def _ultimo_campo(self, campo, personagem):
        """Valor do campo na hunt salva mais recente desse personagem que o tenha (valor inicial de uma hunt NOVA)."""
        for h in historico.ordenar(historico.carregar()):
            # só hunts em que ele é o "Seu personagem": numa hunt de amigo ele é só membro e a prey é do amigo
            if campo in h and (not personagem or (h.get("personagem") or "").lower() == personagem.lower()):
                return h[campo]
        return None

    def hunt_ultima_prey(self, personagem=""):
        return self._ultimo_campo("prey", personagem)

    def hunt_ultimos_charms(self, personagem=""):
        return self._ultimo_campo("charms", personagem)

    def hunt_ultima_roda(self, personagem=""):
        return self._ultimo_campo("roda", personagem)

    def hunt_ultima_postura(self, personagem=""):
        return self._ultimo_campo("postura", personagem)

    def hunt_posturas(self, voc=""):
        """Posturas (stance spells) que o jogador pode marcar: as da vocação, ou todas."""
        return posturas.listar(voc)

    def hunt_ultimo_set(self, personagem=""):
        return sets.normalizar_set(self._ultimo_campo("set", personagem))   # hunts antigas guardavam os consumíveis como texto

    # ----- Character Sets: cadastro em Configurações; os itens vêm da TibiaWiki (cache por slot) -----
    def set_listar(self):
        return sets.listar()

    def set_vincular(self, id_, personagem):
        return sets.vincular(id_, personagem)

    def set_salvar(self, dados):
        try:
            return {"ok": True, "set": sets.salvar(dados)}
        except ValueError as e:
            return {"ok": False, "erro": str(e)}
        except OSError:
            return {"ok": False, "erro": "Não consegui salvar o set."}

    def set_remover(self, id_):
        return sets.remover(id_)

    def set_tabelas(self):
        """Slots e embuimentos que o editor de sets oferece."""
        try:
            imbs = emb.carregar_imbuements(IMBUEMENTS_PATH)
        except (OSError, ValueError):
            imbs = []
        return {"slots": [list(s) for s in itens_set.SLOTS],
                "embuimentos": [{"nome": i["name"], "sub": i.get("subtitle") or ""} for i in imbs]}

    def set_perks(self, nome):
        """Colunas de perks de proficiência da arma (TibiaWiki em português; a 1ª vez baixa tudo e leva ~10 s)."""
        armas = proficiencia.carregar().get("armas", {})
        achado = next((v for k, v in armas.items() if k.lower() == (nome or "").lower()), [])
        return {"colunas": achado, "icones": proficiencia.carregar().get("icones", {})}

    def set_icones_prof(self):
        """Endereços dos ícones da proficiência (para desenhar a tabela de perks da arma)."""
        return proficiencia.carregar().get("icones", {})

    def set_shaping(self, voc=""):
        """Opções do Perk Shaping: as de todas as vocações e as da vocação pedida (todas, se voc vazio)."""
        return [o for o in proficiencia.carregar().get("opcoes", []) if not voc or o.get("voc") in ("", voc)]

    def hunt_stats(self, set_, prey, charms, roda, postura=None, nivel=None, personagem=""):
        """Combat Stats da hunt (set + prey + charms + roda) para o painel da tela; a roda entra pelo resumo do planner já guardado."""
        r = roda_mod.normalizar_roda(roda) if roda else None
        resumo = roda_mod.resumo_obter(r["codigo"]) if r else None
        return stats_set.linhas_hunt(sets.normalizar_set(set_), historico.normalizar_prey(prey) or [],
                                     preys_charms.normalizar_charms(charms) or [], resumo,
                                     postura=posturas.normalizar_postura(postura) or "", nivel=nivel if isinstance(nivel, int) else None,
                                     skills=_skills_do_personagem(personagem))

    def set_stats(self, valor):
        """Combat Stats (soma dos itens e embuimentos) do set pedido: lista de linhas para a tela."""
        return stats_set.linhas(stats_set.somar(sets.normalizar_set(valor)))

    def set_itens(self, slot):
        """Todos os itens do slot (primeira vez baixa da TibiaWiki; vale alguns segundos), já com a descrição pronta."""
        return [{**i, "desc": itens_set.descricao(i)} for i in itens_set.itens_do_slot(slot)]

    # ----- rodas (Wheel of Destiny): cadastro em Configurações e arquivos do planner do tibia.com -----
    def roda_listar(self):
        return roda.listar()

    def roda_adicionar(self, titulo, codigo, personagem=""):
        try:
            return {"ok": True, "roda": roda.adicionar(titulo, codigo, personagem=personagem)}
        except ValueError as e:
            return {"ok": False, "erro": str(e)}
        except OSError:
            return {"ok": False, "erro": "Não consegui salvar a roda."}

    def roda_vincular(self, id_, personagem):
        return roda.vincular(id_, personagem)

    def roda_atualizar(self, id_, codigo, titulo=None):
        """Guarda o código novo de uma roda (e o novo nome, se vier) depois de editada no planner."""
        try:
            r = roda.atualizar_codigo(id_, codigo)
            if r is None:
                return {"ok": False, "erro": "Essa roda não existe mais."}
            if titulo is not None and titulo.strip():
                roda.renomear(id_, titulo)
                r = roda.obter(id_)
            return {"ok": True, "roda": r}
        except ValueError as e:
            return {"ok": False, "erro": str(e)}
        except OSError:
            return {"ok": False, "erro": "Não consegui salvar a roda."}

    def roda_renomear(self, id_, titulo):
        return roda.renomear(id_, titulo)

    def roda_remover(self, id_):
        return roda.remover(id_)

    def roda_guardar_resumo(self, codigo, secoes):
        """O planner da roda manda o resumo dele (perks por seção); fica guardado por código para o Combat Stats."""
        try:
            return roda.resumo_guardar(codigo, secoes)
        except OSError:
            return False

    def roda_pontos(self, secoes):
        """Revelações, augments e gemas (com as bolinhas) a partir do resumo do planner, para mostrar embaixo da roda."""
        return stats_set.pontos_roda(secoes)

    def roda_resumo(self, codigo):
        return roda.resumo_obter(codigo)

    def roda_arquivos(self):
        """Os arquivos do planner da roda (baixados do tibia.com na primeira vez; ver roda.py)."""
        return roda.arquivos_planner()

    def hunt_icones_charms(self):
        """{nome do charm: URL do ícone na TibiaWiki}; {} sem internet e sem cache (a tela mostra só o nome)."""
        return preys_charms.icones_charms()

    def hunt_tabelas(self):
        """Tabelas de Prey (bônus por estrela) e Charms (% por nível) para a tela."""
        return preys_charms.tabelas()

    def hunt_apagar(self, id_):
        apagada = historico.apagar(id_)
        if apagada:
            try:
                classificador.apagar_sessao(id_)      # a sessão do classificador morre junto com a hunt
            except OSError:
                pass
        return apagada

    # ----- classificador de dano (página da comunidade baixada no PC; a sessão fica salva na hunt) -----
    def classificador_pagina(self):
        """A página do classificador numa string só (css e js embutidos). Baixa os arquivos na primeira vez."""
        r = classificador.arquivos()
        return {"ok": True, "html": classificador.montar_pagina(r["arquivos"])} if r["ok"] else r

    def classificador_sessao(self, id_hunt):
        """Os logs salvos da hunt (sem o resultado, que é grande): {local, server, t, linhas_local, linhas_server, tem_resultado} ou None."""
        s = classificador.obter_sessao(id_hunt)
        if not s:
            return None
        s["tem_resultado"] = bool(s.pop("html"))
        return s

    def classificador_resultado(self, id_hunt):
        """Página só com o último resultado salvo da hunt, para ver na hora sem reclassificar."""
        s = classificador.obter_sessao(id_hunt)
        if not s or not s["html"]:
            return {"ok": False}
        r = classificador.arquivos()
        return {"ok": True, "html": classificador.pagina_resultado(r["arquivos"], s["html"])} if r["ok"] else r

    def classificador_salvar(self, id_hunt, local, server, html=None):
        try:
            return classificador.salvar_sessao(id_hunt, local, server, html)
        except OSError:
            return False

    def classificador_apagar(self, id_hunt):
        try:
            return classificador.apagar_sessao(id_hunt)
        except OSError:
            return False

    def hunt_exportar(self, personagem="", ids=None):
        pacote = historico.exportar(ids=ids, personagem=personagem or None)
        if not pacote["hunts"]:
            return {"ok": False, "erro": "Nenhuma hunt para exportar."}
        sufixo = (personagem or "todas").replace(" ", "-").lower()
        tipo = getattr(getattr(webview, "FileDialog", None), "SAVE", None) or webview.SAVE_DIALOG
        r = self._window.create_file_dialog(tipo, save_filename=f"hunts-{sufixo}.json",
                                            file_types=("Hunts do Tibia Tudo (*.json)",))
        if not r:
            return {"ok": False, "cancelado": True}
        caminho = r if isinstance(r, str) else r[0]
        try:
            with open(caminho, "w", encoding="utf-8") as f:
                json.dump(pacote, f, ensure_ascii=False, indent=1)
        except OSError as e:
            return {"ok": False, "erro": str(e)}
        return {"ok": True, "qtd": len(pacote["hunts"]), "caminho": caminho}

    def hunt_importar(self, substituir=False):
        tipo = getattr(getattr(webview, "FileDialog", None), "OPEN", None) or webview.OPEN_DIALOG
        r = self._window.create_file_dialog(tipo, file_types=("Hunts do Tibia Tudo (*.json)", "Todos os arquivos (*.*)"))
        if not r:
            return {"ok": False, "cancelado": True}
        try:
            with open(r[0], "r", encoding="utf-8") as f:
                dados = json.load(f)
            novas, repetidas = historico.importar(dados, substituir=bool(substituir))
        except (OSError, json.JSONDecodeError, ValueError) as e:
            return {"ok": False, "erro": str(e)}
        return {"ok": True, "novas": novas, "repetidas": repetidas}

    # ================= ferramentas: boss/criatura do dia, Rashid, server save, shared, "quando eu upo?" =================
    def zandaobot_buscar(self, mundo="", forcar=False):
        d = personagens.carregar()
        p = next((p for p in d["lista"] if p["nome"] == d["atual"]), {})
        mundo = (mundo or "").strip() or p.get("mundo", "")
        return world_board.aplicar(zandaobot.buscar(mundo, bool(forcar)), d["atual"])

    def world_board_analisar(self, texto, mundo="", dia="", completo=False):
        personagem, mundo = world_board.contexto(personagens.carregar(), mundo)
        return world_board.preparar(texto, personagem, mundo, dia, bool(completo))

    def world_board_salvar(self, texto, mundo="", dia="", completo=False, personagem_esperado=""):
        personagem, mundo = world_board.contexto(personagens.carregar(), mundo)
        if personagem.casefold() != (personagem_esperado or "").casefold():
            return {"erro": "O personagem em uso mudou. Analise o texto novamente antes de salvar."}
        return world_board.salvar(texto, personagem, mundo, dia, bool(completo))

    def world_board_remover(self, mundo, dia, personagem_esperado=""):
        personagem, mundo = world_board.contexto(personagens.carregar(), mundo)
        if not personagem or personagem.casefold() != (personagem_esperado or "").casefold():
            return {"erro": "O personagem em uso mudou. Abra o ZandaoBot novamente."}
        try:
            return world_board.remover(personagem, mundo, dia)
        except OSError:
            return {"erro": "Não foi possível remover o registro do perfil."}

    def zandaobot_mensagem(self, mundo="", campos=None):
        resumo = self.zandaobot_buscar(mundo)
        if resumo.get("erro"):
            return resumo
        return {"mensagem": zandaobot_report.gerar(resumo, campos)}

    def zandaobot_mundos(self):
        return zandaobot.mundos()

    def tibia_dia(self, forcar=False):
        return {**tibia_info.resumo_do_dia(), **tibia_info.boostados(bool(forcar))}

    def tibia_shared(self, levels):
        """levels: lista de números (ou {nome: level}) digitados na calculadora."""
        if isinstance(levels, list):
            levels = {f"Level {l}": l for l in levels}
        try:
            levels = {n: int(str(l).strip()) for n, l in levels.items() if str(l).strip()}
        except ValueError:
            return {"ok": None, "motivo": "Digite só números (ex.: 300, 250, 420)."}
        r = tibia_info.verificar_shared(levels)
        if len(levels) == 1:
            lo, hi = tibia_info.faixa_shared(next(iter(levels.values())))
            r = {"ok": None, "faixa_individual": [lo, hi],
                 "motivo": f"Level {next(iter(levels.values()))} divide XP com levels de {lo} a {hi}."}
        return r

    def tibia_upar(self, nome, xp_atual="", alvo="", xp_h_manual=""):
        """Quanto falta para o level alvo e quantas horas/hunts, pela XP/h média das hunts salvas desse personagem."""
        nome = (nome or "").strip()
        xp = emb.parse_num(str(xp_atual)) if str(xp_atual).strip() else None
        aproximado = False
        if xp is None:
            info = tibia_info.personagem(nome) if nome else None
            if not info:  # sem internet: usa o level guardado em Meus personagens
                info = next((p for p in personagens.carregar()["lista"] if p["nome"].lower() == nome.lower()), None)
            if not info:
                return {"erro": "Digite a XP atual (janela Skills do Tibia) ou um personagem que exista no tibia.com."}
            xp, aproximado = tibia_info.xp_total(info["level"]), True
        level = tibia_info.level_da_xp(xp)
        try:
            alvo = int(str(alvo).strip()) if str(alvo).strip() else level + 1
        except ValueError:
            return {"erro": "Level alvo inválido."}
        if alvo <= level:
            return {"erro": f"O level alvo precisa ser maior que o atual ({level})."}
        falta = tibia_info.xp_total(alvo) - xp

        hunts = [h for h in historico.carregar()
                 if nome and (h.get("personagem") or "").lower() == nome.lower()
                 and (h.get("resumo") or {}).get("xp") and (h.get("resumo") or {}).get("minutos")]
        minutos = sum(h["resumo"]["minutos"] for h in hunts)
        xp_h_hist = (sum(h["resumo"]["xp"] for h in hunts) * 60 // minutos) if minutos else None
        xp_h = emb.parse_num(str(xp_h_manual)) if str(xp_h_manual).strip() else xp_h_hist
        r = {"level": level, "xp": xp, "aproximado": aproximado, "alvo": alvo, "falta": falta,
             "progresso_pct": round((xp - tibia_info.xp_total(level)) * 100 / (tibia_info.xp_total(level + 1) - tibia_info.xp_total(level)), 1),
             "xp_h": xp_h, "xp_h_hist": xp_h_hist, "hunts_usadas": len(hunts),
             "fonte": "digitada" if str(xp_h_manual).strip() else ("histórico" if xp_h_hist else None)}
        if xp_h:
            horas = falta / xp_h
            dur_media = (minutos / len(hunts)) if hunts else None
            r.update({"horas": round(horas, 1), "hunts_equiv": round(horas * 60 / dur_media, 1) if dur_media else None,
                      "duracao_media_min": round(dur_media) if dur_media else None})
        return r

    # ================= assistente de voz =================
    def _voz_obter(self):
        with self._voz_lock:
            if self._voz is None:
                self._voz = voz.Servico(BASE_DIR, store=assistente_tibiano.Store(BASE_DIR))
            return self._voz

    def assistente_estado(self):
        try:
            service=self._voz_obter()
            with PERSONAGEM_LOCK, service._lock:
                store=service.store
                context=store.context()
                history=store.execute('history',{},context)['events']
                # revision muda a cada gravação: a aba Bosstiary só recarrega quando algo mudou (ex.: "matei" por voz).
                return {'context':context, 'timers':store.execute('timer.list',{},context)['timers'],
                        'catalog':store.execute('boss.catalog',{},context),
                        'revision':history[-1]['id'] if history else None}
        except (ValueError,OSError) as error:
            return {'erro':str(error)}

    # "argumentos", não "arguments": o wrapper JS do pywebview usa o nome do parâmetro e "arguments" apaga a chamada.
    def assistente_executar(self, intent, argumentos=None, context=None, request_id=None):
        try:
            service=self._voz_obter()
            with PERSONAGEM_LOCK, service._lock:
                result=service.store.execute(intent, argumentos, context, request_id)
                result['message']=assistente_tibiano.reply(result)
                return result
        except (ValueError,OSError,TypeError) as error:
            return {'erro':str(error)}

    def assistente_level(self, character_id, level, confirmed=False):
        if confirmed is not True:
            return {'erro':'Confirme explicitamente a alteração do cadastro.'}
        try:
            assistente_tibiano.integer(level)
            with PERSONAGEM_LOCK, personagens._trava:
                dados=personagens.carregar()
                person=next((p for p in dados['lista'] if p['nome']==character_id),None)
                if person is None: return {'erro':'Personagem não encontrado.'}
                person['level']=level
                personagens._gravar(dados)
            return {'message':'Level local atualizado com confirmação.'}
        except (ValueError,OSError) as error:
            return {'erro':str(error)}

    def voz_iniciar(self):
        return self._voz_obter().iniciar()

    def voz_escutar(self):
        return self._voz_obter().escutar()

    def voz_parar(self):
        return self._voz_obter().parar()

    def voz_estado(self):
        return self._voz_obter().estado()

    def voz_configurar_online(self, token, enabled):
        return self._voz_obter().configurar_online(token, enabled)

    def voz_criar(self, valor, unidade):
        return self._voz_obter().criar(valor, unidade)

    def voz_cancelar(self, timer_id):
        return self._voz_obter().cancelar(timer_id)

    # ================= timers de áudio (ver audio_timers.py) =================
    def audio_iniciar(self):
        """Liga o motor (lê as teclas cadastradas e toca os sons), também com o app minimizado."""
        with PERSONAGEM_LOCK:
            if self._audio is None:
                self._audio = audio_timers.Motor(ao_mudar=lambda est: self._emit("audioEstado", est),
                                                 personagem=personagens.carregar()["atual"])
            return self.audio_carregar()

    def _timers_do_personagem(self, d):
        """Os timers só valem para o personagem em uso: avisa o motor quando ele muda. Devolve d."""
        if getattr(self, "_audio", None):
            self._audio.definir_personagem((d or {}).get("atual", ""))
        if getattr(self, "_mirror", None):
            self._mirror.definir_personagem((d or {}).get("atual", ""))
        self._personagem_auto_pendente = None
        self._personagem_revisao = getattr(self, "_personagem_revisao", 0) + 1
        return {**d, "revisao": self._personagem_revisao}

    def audio_carregar(self):
        m = self._audio
        cfg = m.cfg if m else audio_timers.carregar()
        return {"cfg": cfg, "sons": audio_timers.lista_sons(),
                "estado": m.estado() if m else {"ligado": cfg["ligado"], "timers": {}},
                "teclas": {t["id"]: audio_timers.texto_da_tecla(t["tecla"]) for t in cfg["timers"]}}

    def audio_salvar(self, cfg):
        cfg = {**audio_timers.PADRAO, **{k: cfg.get(k) for k in audio_timers.PADRAO if k in cfg}}
        cfg["timers"] = [audio_timers.normalizar(t) for t in cfg["timers"] or []]
        cfg["volume"] = max(0, min(100, int(cfg["volume"])))
        cfg["ligado"], cfg["so_tibia"] = bool(cfg["ligado"]), bool(cfg["so_tibia"])
        cfg["barra"] = audio_timers.overlay.normalizar_barra(cfg.get("barra"))
        cfg["alerta"] = audio_timers.overlay.normalizar_alerta(cfg.get("alerta"))
        if self._audio:
            self._audio.atualizar_cfg(cfg)
        else:
            audio_timers.salvar(cfg)
        return self.audio_carregar()

    def audio_gravar_tecla(self):
        """Espera a próxima tecla apertada (até 8 s)."""
        t = audio_timers.gravar_tecla()
        return {**t, "texto": audio_timers.texto_da_tecla(t)} if t else None

    def audio_tocar(self, som, volume=100):
        if self._audio:
            self._audio.tocar(som, volume)
        return True

    def audio_testar_alerta(self, cor="amarelo", texto="", fonte=34, alerta=None, segundos=4, piscar=False, visual=None, progresso=None):
        """Mostra o alerta por 4 s (com a posição da tela, mesmo antes de salvar)."""
        if not self._audio:
            return False
        return bool(self._audio.testar_alerta(cor, texto, fonte, segundos, bool(piscar), visual, progresso, pos=alerta))

    def audio_testar_timers(self, timers, segundos=0):
        return bool(self._audio and self._audio.testar_timers(timers, segundos))

    def audio_parar_teste(self):
        if self._audio:
            self._audio.parar_teste()
        return True

    def audio_tv_perfis(self):
        """Perfis de timers do TibiaVision instalado neste PC (para importar)."""
        return {"perfis": [p for p in audio_timers.perfis_tibiavision() if p["timers"]],
                "instalado": bool(audio_timers.pastas_tibiavision())}

    def audio_tv_sons(self):
        return {"sons": audio_timers.importar_sons_tibiavision(), "lista": audio_timers.lista_sons()}

    def audio_tv_importar(self, arquivo):
        """Copia os sons do TibiaVision deste PC e soma os timers do perfil escolhido (sem repetir)."""
        validos = {p["arquivo"] for p in audio_timers.perfis_tibiavision()}
        if arquivo not in validos:
            return {"ok": False, "erro": "Perfil do TibiaVision não encontrado."}
        sons = audio_timers.importar_sons_tibiavision()
        novos = audio_timers.timers_do_tibiavision(arquivo)
        cfg = self._audio.cfg if self._audio else audio_timers.carregar()
        ja = {(t["nome"].lower(), t["tecla"]["vk"]) for t in cfg["timers"]}
        add = [t for t in novos if (t["nome"].lower(), t["tecla"]["vk"]) not in ja]
        cfg = {**cfg, "timers": cfg["timers"] + add}
        r = self.audio_salvar(cfg)
        return {"ok": True, "timers": len(add), "repetidos": len(novos) - len(add), **r, "sons_novos": sons}

    def audio_testar_barras(self, barra=None, nome=None, cor=None, loop=False, cor_tempo=None):
        """Mostra barras de exemplo por 6 s (com a configuração da tela, mesmo antes de salvar)."""
        if not self._audio:
            return False
        self._audio.testar_barras(nome=nome, cor=cor, loop=loop, cor_tempo=cor_tempo, cfg=barra)
        return True

    def audio_parar_todos(self):
        if self._audio:
            self._audio.parar_todos()
        return True

    def audio_importar_som(self):
        tipo = getattr(getattr(webview, "FileDialog", None), "OPEN", None) or webview.OPEN_DIALOG
        r = self._window.create_file_dialog(tipo, file_types=("Sons (*.mp3;*.wav)",))
        if not r:
            return {"ok": False, "cancelado": True}
        try:
            som = audio_timers.importar_som(r[0])
        except (OSError, ValueError) as e:
            return {"ok": False, "erro": str(e)}
        return {"ok": True, "som": som, "sons": audio_timers.lista_sons()}

    # ================= configurações: backup de tudo =================
    def _caminhos_backup(self):
        return {"world_board": world_board.ARQUIVO, "historico": historico.HIST_PATH, "personagens": personagens.ARQUIVO, "embuimentos": DADOS_PATH,
                "prints": organizer.SETTINGS_PATH, "prints_rotina": prints_schedule.ARQUIVO, "janela": PREFS_PATH, "audio": audio_timers.ARQUIVO, "mirror": mirror_core.ARQUIVO,
                "assistente": os.path.join(BASE_DIR,"assistente-tibiano.json"), "precos": precos.PRECOS_PATH, "rodas": roda.RODAS_PATH, "sets": sets.SETS_PATH, "classificador": classificador.SESSOES_PATH}

    def config_exportar(self):
        pacote = backup.exportar(self._caminhos_backup(), VERSAO_APP)
        if not pacote["arquivos"]:
            return {"ok": False, "erro": "Ainda não há nada para guardar no backup."}
        tipo = getattr(getattr(webview, "FileDialog", None), "SAVE", None) or webview.SAVE_DIALOG
        hoje = pacote["exportado_em"][:10]
        r = self._window.create_file_dialog(tipo, save_filename=f"zandao-tibia-tools-backup-{hoje}.json",
                                            file_types=("Backup do Tibia Tudo (*.json)",))
        if not r:
            return {"ok": False, "cancelado": True}
        caminho = r if isinstance(r, str) else r[0]
        try:
            with open(caminho, "w", encoding="utf-8") as f:
                json.dump(pacote, f, ensure_ascii=False, indent=1)
        except OSError as e:
            return {"ok": False, "erro": str(e)}
        return {"ok": True, "itens": backup.resumo(pacote), "caminho": caminho}

    def config_ler_backup(self):
        """Escolhe o arquivo e mostra o que tem nele (a restauração só acontece em config_restaurar)."""
        tipo = getattr(getattr(webview, "FileDialog", None), "OPEN", None) or webview.OPEN_DIALOG
        r = self._window.create_file_dialog(tipo, file_types=("Backup do Tibia Tudo (*.json)", "Todos os arquivos (*.*)"))
        if not r:
            return {"ok": False, "cancelado": True}
        try:
            with open(r[0], "r", encoding="utf-8") as f:
                dados = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            return {"ok": False, "erro": f"Não consegui ler o arquivo: {e}"}
        if not isinstance(dados, dict) or dados.get("formato") != backup.FORMATO:
            return {"ok": False, "erro": "Esse arquivo não é um backup do Tibia Tudo. "
                                         "(Para importar só hunts, use Importar na aba Histórico.)"}
        self._backup_pendente = dados
        return {"ok": True, "itens": backup.resumo(dados), "exportado_em": dados.get("exportado_em", ""),
                "versao_app": dados.get("versao_app", "")}

    def config_restaurar(self):
        dados = getattr(self, "_backup_pendente", None)
        if not dados:
            return {"ok": False, "erro": "Escolha o arquivo de backup de novo."}
        with self._prints_agenda_lock:
            agenda = self._prints_agenda if 'prints_rotina' in dados.get('arquivos', {}) else None
            if agenda is not None:
                agenda.parar(esperar=True)  # Não deixa uma execução sobrescrever o backup restaurado.
            try:
                feitos = backup.importar(dados, self._caminhos_backup())
            except (OSError, ValueError, KeyError) as e:
                if agenda is not None:
                    agenda.iniciar()
                return {"ok": False, "erro": str(e)}
            self._backup_pendente = None
            if backup.ITENS['prints_rotina'] in feitos:
                self._prints_agenda = None
        if backup.ITENS["mirror"] in feitos and self._mirror is not None:
            try:
                self._mirror.reload()
            except (ValueError, OSError) as error:
                self._mirror.close()
                self._mirror = None
                return {"ok": False, "erro": str(error), "itens": feitos}
        return {"ok": True, "itens": feitos}

    def config_abrir_pasta(self):
        return self.abrir_pasta(BASE_DIR)

    # ================= atualização automática (GitHub Releases, ver atualizacoes.py) =================
    def versao_app(self):
        return VERSAO_APP

    def beta_publicacao_abrir(self, url):
        from versao import REPO_GITHUB
        import webbrowser
        base = f"https://github.com/{REPO_GITHUB}/"
        if not isinstance(url, str) or not url.startswith((base + "actions/", base + "releases/")):
            return False
        return webbrowser.open(url)

    def beta_publicacao_info(self):
        return publicacao_beta.informacoes()

    def beta_publicar_original(self):
        return publicacao_beta.publicar()

    def beta_publicacao_estado(self):
        return publicacao_beta.estado()

    def verificar_atualizacao(self):
        """Silencioso: None se não tem versão nova, sem internet etc."""
        info = atualizacoes.verificar_atualizacao()
        self._atualizacao_info = info
        if not info:
            return None
        return {"versao": info["versao"], "notas": info["notas"][:600], "versao_atual": VERSAO_APP}

    def instalar_atualizacao(self):
        # A URL vem sempre do que verificar_atualizacao() guardou aqui (nunca do JS): este método baixa e EXECUTA um instalador.
        if not self._atualizacao_info:
            return False
        threading.Thread(target=self._trabalho_instalar_atualizacao, daemon=True).start()
        return True

    def _trabalho_instalar_atualizacao(self):
        info = self._atualizacao_info
        try:
            caminho = atualizacoes.baixar_instalador(info["url_instalador"],
                lambda pct: self._emit("onProgressoAtualizacao", {"pct": pct}),
                sha256=info.get("sha256"), tamanho=info.get("tamanho"))
            # Recheck immediately before execution, including Authenticode policy.
            atualizacoes.validar_instalador(caminho, info.get("sha256"), info.get("tamanho"))
            from recovery import prepare_snapshot
            prepare_snapshot(info["versao"])
            subprocess.Popen([caminho])
        except Exception as e:
            self._emit("onFalhaAtualizacao", {"mensagem": f"Atualização não instalada: {e}", "url_release": info["url_release"]})
            return
        os._exit(0)

    # ================= janela =================
    def janela_prefs(self):
        return ler_prefs()

    def janela_aplicar(self, por_cima, opacidade, escala=None):
        """Chamado pela página ao abrir e a cada mudança no 'Fixar por cima' / transparência / tamanho da interface."""
        prefs = salvar_prefs({"por_cima": bool(por_cima), "opacidade": max(40, min(100, int(opacidade))),
                              "escala": ler_prefs()["escala"] if escala is None else _escala(escala)})
        hwnd = hwnd_do_app(self._window.title) if self._window else None
        if not hwnd:
            return False
        aplicar_janela(hwnd, prefs["por_cima"], prefs["opacidade"])
        return True

    def janela_moldura(self, mostrar):
        """Mostra (True) ou esconde (False) a barra de título do Windows. Escondida: modo gadget, só a faixa do app com o X no hover."""
        hwnd = hwnd_do_app(self._window.title) if self._window else None
        if not hwnd:
            return False
        try:
            definir_moldura(hwnd, bool(mostrar))
        except Exception:
            return False
        return True

    def janela_arrastar(self, fase):
        """Arrastar a janela sem barra de título: 'inicio' (botão do mouse desceu na faixa), 'mover' (a cada movimento) e 'fim'.
        A posição vem do mouse real do Windows (não do navegador), então não depende de zoom nem de escala da tela."""
        if fase == "fim":
            self._arrasto = None
            return True
        hwnd = hwnd_do_app(self._window.title) if self._window else None
        if not hwnd:
            return False
        if fase == "inicio":
            self._arrasto = (_cursor(), _canto_da_janela(hwnd))
            return True
        arrasto = getattr(self, "_arrasto", None)
        if fase != "mover" or not arrasto:
            return False
        x, y = posicao_arrasto(arrasto[1], arrasto[0], _cursor())
        _mover_janela(hwnd, x, y)
        return True

    def janela_fechar(self):
        """O X da faixa do modo gadget."""
        if not self._window:
            return False
        self._window.destroy()
        return True

    def janela_redimensionada(self, width, height):
        """Salva o tamanho atual no modo em uso, inclusive ao arrastar as bordas."""
        if not self._window or getattr(self, "_trocando_modo", False):
            return False
        with PREFS_LOCK:
            # Eventos podem chegar atrasados; consulte o tamanho atual da janela.
            tamanho = _tamanho_valido((getattr(self._window, "width", width),
                                      getattr(self._window, "height", height)))
            if not tamanho:
                return False
            modo = getattr(self, "_modo_janela", ler_prefs().get("modo", "normal"))
            tamanhos = ler_prefs().get("tamanhos", {})
            tamanhos[modo] = list(tamanho)
            salvar_prefs({"modo": modo, "tamanhos": tamanhos})
        return True

    def janela_tamanho(self, modo):
        """Alterna os modos restaurando o último tamanho escolhido em cada um."""
        if modo not in ("normal", "gadget") or not self._window:
            return False
        atual = getattr(self, "_modo_janela", ler_prefs().get("modo", "normal"))
        if modo != atual:
            self.janela_redimensionada(getattr(self._window, "width", 0),
                                      getattr(self._window, "height", 0))
        prefs = ler_prefs()
        tamanho = prefs.get("tamanhos", {}).get(modo, TAMANHO_GADGET if modo == "gadget" else TAMANHO_NORMAL)
        self._trocando_modo = True
        try:
            self.janela_moldura(modo == "normal")
            self._window.resize(*tamanho)
            self._modo_janela = modo
            salvar_prefs({"modo": modo})
        except Exception:
            return False
        finally:
            self._trocando_modo = False
        return True


def _skills_do_personagem(nome):
    """Skills base digitadas do personagem (para o Combat Stats da hunt), ou None."""
    return personagens.skills_de(nome)
