"""Funções que a página (web/index.html) chama via window.pywebview.api.*"""

import json
import os
import shutil
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

import webview

import atualizacoes
import damage_core
import embuimentos as emb
import historico
import hunt
import monstros
import organizer
from versao import VERSAO_APP

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

IMBUEMENTS_PATH = os.path.join(BASE_DIR, "data", "imbuements.json")
DADOS_PATH = os.path.join(BASE_DIR, "dados_embuimentos.json")
MACRO_PATH = os.path.join(BASE_DIR, "macro", "tibia_macro_f1.ahk")
# Simulated Keys compilado (Ahk2Exe): roda sem o AutoHotkey instalado. É o que vai no instalador;
# rodando pelo código-fonte, sem ele, usa o AutoHotkey v1.1 + o .ahk.
SIMKEYS_EXE = os.path.join(BASE_DIR, "macro", "SimulatedKeys.exe")

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


def ler_prefs():
    try:
        with open(PREFS_PATH, "r", encoding="utf-8") as f:
            p = json.load(f)
    except (OSError, json.JSONDecodeError):
        p = {}
    return {"por_cima": bool(p.get("por_cima", False)), "opacidade": int(p.get("opacidade", 100))}


# ---------- macro ----------
def achar_autohotkey():
    """O macro é AutoHotkey v1.1."""
    for pasta in (os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramFiles(x86)", "")):
        for exe in ("AutoHotkeyU64.exe", "AutoHotkey.exe", "AutoHotkeyU32.exe"):
            caminho = os.path.join(pasta, "AutoHotkey", exe)
            if pasta and os.path.isfile(caminho):
                return caminho
    return shutil.which("AutoHotkey.exe")


def pids_do_macro():
    """PIDs do Simulated Keys desta pasta (o .exe compilado ou o AutoHotkey rodando o .ahk)."""
    cmd = (
        "Get-CimInstance Win32_Process -Filter \"Name like 'AutoHotkey%' or Name = 'SimulatedKeys.exe'\" | "
        "ForEach-Object { \"$($_.ProcessId)|$($_.CommandLine)\" }"
    )
    try:
        saida = subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            capture_output=True, text=True, timeout=15, creationflags=SEM_JANELA,
        ).stdout
    except (OSError, subprocess.TimeoutExpired):
        return []
    alvos = (os.path.normcase(MACRO_PATH), os.path.normcase(SIMKEYS_EXE))
    pids = []
    for linha in (saida or "").splitlines():
        pid, _, cmdline = linha.partition("|")
        if any(a in os.path.normcase(cmdline) for a in alvos) and pid.strip().isdigit():
            pids.append(int(pid))
    return pids


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
        self._window = None  # preenchido em zandao_tibia_tools.py (nunca público: o pywebview recursa nele)
        self._imbs = emb.carregar_imbuements(IMBUEMENTS_PATH)
        self._organizando = False
        self._atualizacao_info = None  # release lida em verificar_atualizacao, até instalar_atualizacao

    def _emit(self, funcao_js, dados):
        if self._window:
            self._window.evaluate_js(f"{funcao_js}({json.dumps(dados, ensure_ascii=False)})")

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
            },
            "prints": prints,
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

    def organizar(self, cfg):
        if self._organizando:
            return {"ok": False, "erro": "Já está organizando."}
        try:
            organizer.salvar_config(cfg)
        except OSError as e:
            return {"ok": False, "erro": f"Não consegui salvar as configurações: {e}"}
        self._organizando = True
        threading.Thread(target=self._trabalho_organizar, args=(cfg,), daemon=True).start()
        return {"ok": True}

    def _trabalho_organizar(self, cfg):
        try:
            resultado, por_tipo = organizer.organizar(cfg, lambda m: self._emit("logPrints", m))
            if cfg.get("open-when-done") and resultado["processadas"]:
                self.abrir_pasta(cfg["destination"])
            self._emit("fimPrints", {"resultado": dict(resultado), "porTipo": por_tipo.most_common()})
        except Exception as e:
            self._emit("erroPrints", str(e))
        finally:
            self._organizando = False

    # ================= macro =================
    def macro_status(self):
        return {"ahk": os.path.isfile(SIMKEYS_EXE) or bool(achar_autohotkey()), "rodando": bool(pids_do_macro())}

    def macro_ligar(self):
        if os.path.isfile(SIMKEYS_EXE):
            subprocess.Popen([SIMKEYS_EXE], cwd=os.path.dirname(SIMKEYS_EXE))
            return {"ok": True}
        ahk = achar_autohotkey()
        if not ahk:
            return {"ok": False, "erro": "Simulated Keys não encontrado. Reinstale o Zandao Tibia Tools."}
        if not os.path.isfile(MACRO_PATH):
            return {"ok": False, "erro": f"Script do Simulated Keys não encontrado: {MACRO_PATH}"}
        subprocess.Popen([ahk, MACRO_PATH], cwd=os.path.dirname(MACRO_PATH))
        return {"ok": True}

    def macro_fechar(self):
        for pid in pids_do_macro():
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, creationflags=SEM_JANELA)
        return {"ok": True}

    def macro_abrir_pasta(self):
        return self.abrir_pasta(os.path.dirname(MACRO_PATH))

    # ================= hunt analyser (loot split + dano) =================
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

    def hunt_ler_clipboard(self):
        """Lê o que foi copiado no Tibia e diz qual dos três textos é."""
        try:
            texto = ler_clipboard()
        except Exception:
            texto = ""
        return {"texto": texto, "tipo": hunt.detectar(texto)}

    def hunt_detectar(self, texto):
        return hunt.detectar(texto)

    def hunt_analisar(self, entrada):
        """Análise na hora (split, resumo, kills) + salva no histórico. A parte de monstros/dano
        (internet) roda em segundo plano e chega depois em window.huntDano()."""
        entrada = {k: entrada.get(k) for k in ("nome", "party", "solo", "dano", "despesas", "excluidos", "personagem", "id")}
        a = hunt.montar(entrada)
        if a.get("vazio"):
            self._salvar_rascunho(entrada, entrada.get("id"))
            return {"analise": a, "id": entrada.get("id")}

        ass = hunt.assinatura(entrada)
        salvar = True
        if entrada.get("id"):
            antigo = historico.obter(entrada["id"])
            if antigo and antigo.get("data_hunt") and a.get("data") and antigo["data_hunt"] != a["data"]:
                # colou outra hunt (outro horário) sem clicar em "Nova hunt": vira outra entrada, não sobrescreve
                entrada["id"] = None
                entrada["nome"] = ""
            elif antigo and any((antigo.get("entrada") or {}).get(k, "").strip() and not (entrada.get(k) or "").strip()
                                for k in ("party", "solo", "dano")):
                # limpou uma caixa de uma hunt já salva: não apaga nada do histórico até colar algo no lugar
                salvar = False
        nome = (entrada.get("nome") or "").strip() or f"Hunt {a.get('data') or ''}".strip()
        if salvar:
            registro = historico.salvar({
                "id": entrada.get("id"), "assinatura": ass, "nome": nome, "data_hunt": a.get("data"),
                "personagem": (entrada.get("personagem") or "").strip(),
                "entrada": {k: entrada.get(k) or ("" if k in ("party", "solo", "dano") else [])
                            for k in ("party", "solo", "dano", "despesas", "excluidos")},
                "resumo": a["resumo"], "membros": a.get("personagens", []), "monstros": a.get("kills", [])[:20],
            })
        else:
            registro = antigo
        self._salvar_rascunho(entrada, registro["id"])

        threading.Thread(target=self._trabalho_dano, args=(registro["id"], ass, nome, a, salvar), daemon=True).start()
        return {"analise": a, "id": registro["id"], "assinatura": ass, "nome": nome, "salvo": salvar,
                "pagos": registro.get("pagos", []), "texto": hunt.texto_discord(nome, a)}

    def _trabalho_dano(self, id_, ass, nome, a, salvar=True):
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
            if analise and salvar:
                historico.atualizar(id_, monstros=kills[:20], dano={
                    "elementos": analise["elementos"], "protecoes": analise["protecoes"],
                    "ofensivo": [o for o in analise["ofensivo"] if not o["sem_dados"]][:3],
                })
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

    def hunt_renomear(self, id_, nome):
        nome = (nome or "").strip() or "Hunt"
        r = self.hunt_carregar()
        if r["id"] == id_:  # senão, ao reabrir o app, a reanálise voltaria o nome antigo
            r["entrada"]["nome"] = nome
            self._salvar_rascunho(r["entrada"], id_)
        return bool(historico.atualizar(id_, nome=nome))

    def hunt_historico(self, personagem=""):
        todas = historico.ordenar(historico.carregar())
        personagens = sorted({h.get("personagem") for h in todas if h.get("personagem")}, key=str.lower)
        lista = [h for h in todas if historico.do_personagem(h, personagem)] if personagem else todas
        return {
            "personagens": personagens,
            "totais": historico.totais(lista),
            "hunts": [{
                "id": h["id"], "nome": h.get("nome"), "data": h.get("data_hunt") or (h.get("criado_em") or "")[:16].replace("T", " "),
                "personagem": h.get("personagem"), "membros": h.get("membros", []), "resumo": h.get("resumo") or {},
                "monstros": (h.get("monstros") or [])[:4],
                "protecoes": [p["rotulo"] for p in ((h.get("dano") or {}).get("protecoes") or [])[:3]],
                "importada": bool(h.get("importado_em")),
            } for h in lista],
        }

    def hunt_abrir(self, id_):
        h = historico.obter(id_)
        if not h:
            return None
        e = dict(h.get("entrada") or {})
        e.update({"nome": h.get("nome"), "personagem": h.get("personagem"), "id": h["id"]})
        return e

    def hunt_apagar(self, id_):
        return historico.apagar(id_)

    def hunt_exportar(self, personagem=""):
        pacote = historico.exportar(personagem=personagem or None)
        if not pacote["hunts"]:
            return {"ok": False, "erro": "Nenhuma hunt para exportar."}
        sufixo = (personagem or "todas").replace(" ", "-").lower()
        tipo = getattr(getattr(webview, "FileDialog", None), "SAVE", None) or webview.SAVE_DIALOG
        r = self._window.create_file_dialog(tipo, save_filename=f"hunts-{sufixo}.json",
                                            file_types=("Hunts do Zandao Tibia Tools (*.json)",))
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
        r = self._window.create_file_dialog(tipo, file_types=("Hunts do Zandao Tibia Tools (*.json)", "Todos os arquivos (*.*)"))
        if not r:
            return {"ok": False, "cancelado": True}
        try:
            with open(r[0], "r", encoding="utf-8") as f:
                dados = json.load(f)
            novas, repetidas = historico.importar(dados, substituir=bool(substituir))
        except (OSError, json.JSONDecodeError, ValueError) as e:
            return {"ok": False, "erro": str(e)}
        return {"ok": True, "novas": novas, "repetidas": repetidas}

    # ================= atualização automática (GitHub Releases, ver atualizacoes.py) =================
    def versao_app(self):
        return VERSAO_APP

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
        caminho = atualizacoes.baixar_instalador(info["url_instalador"],
                                                 lambda pct: self._emit("onProgressoAtualizacao", {"pct": pct}))
        if not caminho:
            self._emit("onFalhaAtualizacao", {"mensagem": "Não consegui baixar a atualização agora.",
                                              "url_release": info["url_release"]})
            return
        try:
            subprocess.Popen([caminho])
        except Exception as e:
            self._emit("onFalhaAtualizacao", {"mensagem": f"Erro ao abrir o instalador: {e}", "url_release": info["url_release"]})
            return
        os._exit(0)

    # ================= janela =================
    def janela_prefs(self):
        return ler_prefs()

    def janela_aplicar(self, por_cima, opacidade):
        """Chamado pela página ao abrir e a cada mudança no 'Fixar por cima' / transparência."""
        prefs = {"por_cima": bool(por_cima), "opacidade": max(40, min(100, int(opacidade)))}
        try:
            with open(PREFS_PATH, "w", encoding="utf-8") as f:
                json.dump(prefs, f, indent=2)
        except OSError:
            pass
        hwnd = hwnd_do_app(self._window.title) if self._window else None
        if not hwnd:
            return False
        aplicar_janela(hwnd, prefs["por_cima"], prefs["opacidade"])
        return True
