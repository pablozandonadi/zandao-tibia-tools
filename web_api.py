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
import audio_timers
import backup
import damage_core
import embuimentos as emb
import equipamentos
import historico
import hunt
import monstros
import organizer
import personagens
import precos
import tibia_info
from versao import VERSAO_APP

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

IMBUEMENTS_PATH = os.path.join(BASE_DIR, "data", "imbuements.json")
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


def ler_prefs():
    try:
        with open(PREFS_PATH, "r", encoding="utf-8") as f:
            p = json.load(f)
    except (OSError, json.JSONDecodeError):
        p = {}
    return {"por_cima": bool(p.get("por_cima", False)), "opacidade": int(p.get("opacidade", 100))}


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
        self._window = None  # preenchido em zandao_tibia_tools.py (nunca público: o pywebview recursa nele)
        self._imbs = emb.carregar_imbuements(IMBUEMENTS_PATH)
        self._organizando = False
        self._atualizacao_info = None  # release lida em verificar_atualizacao, até instalar_atualizacao
        self._dano_cache = {}  # assinatura da hunt -> monstros/dano já analisados (para o Salvar)
        self._audio = None      # motor dos timers de áudio (liga em audio_iniciar)
        self._capturas = {}     # tipo ('party'/'solo'/'dano') -> {"texto", "t"}: últimos textos do Tibia copiados
        self._trava_capturas = threading.Lock()
        self._monitor = False

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

    def precos_registrar(self, precos_texto):
        valores = {k: emb.parse_num(str(v or "")) for k, v in (precos_texto or {}).items()}
        try:
            return {"gravados": precos.registrar(valores, self._hoje(), self._precos_path)}
        except OSError:
            return {"erro": "Não consegui salvar o histórico de preços"}

    def precos_variacoes(self, precos_texto):
        hist, hoje = precos.carregar(self._precos_path), self._hoje()
        return {k: precos.variacao(emb.parse_num(str(v or "")), k, hoje, hist) for k, v in (precos_texto or {}).items()}

    def precos_serie(self, chave):
        return precos.serie(precos.carregar(self._precos_path), chave)

    def precos_apagar(self, chave, data):
        precos.apagar(chave, data, self._precos_path)
        return self.precos_serie(chave)

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
        return personagens.carregar()

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

    def personagem_adicionar(self, nome):
        d, erro = personagens.adicionar(nome)
        return {"erro": erro} if erro else d

    def personagem_remover(self, nome):
        return personagens.remover(nome)

    def personagem_usar(self, nome):
        return personagens.usar(nome)

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
        return {k: entrada.get(k) for k in ("nome", "party", "solo", "dano", "despesas", "excluidos", "personagem", "id", "prey")}

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
            "entrada": {k: entrada.get(k) or ("" if k in ("party", "solo", "dano") else [])
                        for k in ("party", "solo", "dano", "despesas", "excluidos")},
            "resumo": a["resumo"], "membros": a.get("personagens", []), "monstros": a.get("kills", [])[:20],
            "pagos": list(pagos or []),
        }
        if entrada.get("prey") is not None:  # None = o usuário não mexeu na prey: o historico mantém a gravada
            registro["prey"] = entrada["prey"]
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
                "prey": historico.rotulo_prey(h.get("prey")), "prey_informada": "prey" in h,
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
                  "prey": h.get("prey")})
        return e

    def hunt_ultima_prey(self, personagem=""):
        """Prey da hunt salva mais recente desse personagem (valor inicial de uma hunt NOVA). None se não houver."""
        for h in historico.ordenar(historico.carregar()):
            if "prey" in h and (not personagem or historico.do_personagem(h, personagem)):
                return h["prey"]
        return None

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

    # ================= ferramentas: boss/criatura do dia, Rashid, server save, shared, "quando eu upo?" =================
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

    def hunt_shared(self, nomes):
        """Shared da party do Hunt Analyser, com os levels de AGORA no tibia.com (via TibiaData)."""
        info = tibia_info.personagens([n for n in nomes if n])
        achados = {n: i["level"] for n, i in info.items() if i}
        r = tibia_info.verificar_shared(achados) if len(achados) >= 2 else {
            "ok": None, "motivo": f"Só achei {len(achados)} personagem(ns) no tibia.com; preciso de pelo menos 2 para conferir o shared."}
        r["levels"] = {n: (i and {"level": i["level"], "vocacao": i["vocacao"]}) for n, i in info.items()}
        r["nao_achados"] = [n for n, i in info.items() if not i]
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

    # ================= timers de áudio (ver audio_timers.py) =================
    def audio_iniciar(self):
        """Liga o motor (lê as teclas cadastradas e toca os sons), também com o app minimizado."""
        if self._audio is None:
            self._audio = audio_timers.Motor(ao_mudar=lambda est: self._emit("audioEstado", est))
        return self.audio_carregar()

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

    def audio_testar_alerta(self, cor="amarelo", texto="", fonte=34, alerta=None, segundos=4, piscar=False):
        """Mostra o alerta por 4 s (com a posição da tela, mesmo antes de salvar)."""
        if not self._audio:
            return False
        if alerta:
            self._audio.cfg["alerta"] = audio_timers.overlay.normalizar_alerta(alerta)
        return bool(self._audio.testar_alerta(cor, texto, fonte, segundos, bool(piscar)))

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

    def audio_testar_barras(self, barra=None, nome=None, cor=None, loop=False):
        """Mostra barras de exemplo por 6 s (com a configuração da tela, mesmo antes de salvar)."""
        if not self._audio:
            return False
        if barra:
            self._audio.cfg["barra"] = audio_timers.overlay.normalizar_barra(barra)
        self._audio.testar_barras(nome=nome, cor=cor, loop=loop)
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
        return {"historico": historico.HIST_PATH, "personagens": personagens.ARQUIVO, "embuimentos": DADOS_PATH,
                "prints": organizer.SETTINGS_PATH, "janela": PREFS_PATH, "audio": audio_timers.ARQUIVO,
                "precos": precos.PRECOS_PATH}

    def config_exportar(self):
        pacote = backup.exportar(self._caminhos_backup(), VERSAO_APP)
        if not pacote["arquivos"]:
            return {"ok": False, "erro": "Ainda não há nada para guardar no backup."}
        tipo = getattr(getattr(webview, "FileDialog", None), "SAVE", None) or webview.SAVE_DIALOG
        hoje = pacote["exportado_em"][:10]
        r = self._window.create_file_dialog(tipo, save_filename=f"zandao-tibia-tools-backup-{hoje}.json",
                                            file_types=("Backup do Zandao Tibia Tools (*.json)",))
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
        r = self._window.create_file_dialog(tipo, file_types=("Backup do Zandao Tibia Tools (*.json)", "Todos os arquivos (*.*)"))
        if not r:
            return {"ok": False, "cancelado": True}
        try:
            with open(r[0], "r", encoding="utf-8") as f:
                dados = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            return {"ok": False, "erro": f"Não consegui ler o arquivo: {e}"}
        if not isinstance(dados, dict) or dados.get("formato") != backup.FORMATO:
            return {"ok": False, "erro": "Esse arquivo não é um backup do Zandao Tibia Tools. "
                                         "(Para importar só hunts, use Importar na aba Histórico.)"}
        self._backup_pendente = dados
        return {"ok": True, "itens": backup.resumo(dados), "exportado_em": dados.get("exportado_em", ""),
                "versao_app": dados.get("versao_app", "")}

    def config_restaurar(self):
        dados = getattr(self, "_backup_pendente", None)
        if not dados:
            return {"ok": False, "erro": "Escolha o arquivo de backup de novo."}
        try:
            feitos = backup.importar(dados, self._caminhos_backup())
        except (OSError, ValueError, KeyError) as e:
            return {"ok": False, "erro": str(e)}
        self._backup_pendente = None
        return {"ok": True, "itens": feitos}

    def config_abrir_pasta(self):
        return self.abrir_pasta(BASE_DIR)

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
