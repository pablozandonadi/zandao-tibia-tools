"""Character Sets: o usuário cadastra os conjuntos de equipamento dele (capacete, armadura, arma... + embuimentos de cada
item + consumíveis) em Configurações e escolhe qual usou em cada hunt.

- sets.json: {"formato": "zandao-tibia-tools-sets", "sets": [{"id", "titulo", "itens": {slot: item}, "consumiveis": [...]}]}
- item: {"nome", "imagem", "desc", "imbue" (vagas), "imbues" [nomes], + armor/defense/attack/attrib/resist/atk_elem}
  (os stats ficam guardados para a soma do "Combat Stats", fase D2)
- Na hunt salva: "set": {"titulo", "itens", "consumiveis"} (cópia, para a hunt não mudar se o set for apagado/editado);
  {} = sem set; sem o campo = não informado (hunts antigas).
"""

import json
import os
import sys
import threading
import uuid

import itens_set

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SETS_PATH = os.path.join(BASE_DIR, "sets.json")
FORMATO = "zandao-tibia-tools-sets"
MAX_CONSUMIVEIS = 12   # na foto do set cabem em duas fileiras
_ROTULO_SLOT = dict(itens_set.SLOTS)
_trava = threading.Lock()


# ---------------------------------------------------------------------------
# normalização (cadastro e cópia na hunt)
# ---------------------------------------------------------------------------
def _texto(v, tam):
    return v.strip()[:tam] if isinstance(v, str) else ""


def _inteiro(v, minimo, maximo):
    return v if isinstance(v, int) and not isinstance(v, bool) and minimo <= v <= maximo else None


def _normalizar_item(item, com_prof=False):
    if not isinstance(item, dict):
        return None
    nome = _texto(item.get("nome"), 80)
    if not nome:
        return None
    vagas = _inteiro(item.get("imbue"), 0, 4) or 0
    imbues = []
    for e in item.get("imbues") if isinstance(item.get("imbues"), list) else []:
        e = _texto(e, 40)
        if e and e not in imbues:
            imbues.append(e)
    out = {"nome": nome, "imbue": vagas, "imbues": imbues[:vagas]}
    imagem = _texto(item.get("imagem"), 400)
    if imagem.startswith(("https://", "http://")):
        out["imagem"] = imagem
    if _texto(item.get("desc"), 400):
        out["desc"] = _texto(item.get("desc"), 400)
    for chave in ("armor", "defense", "attack"):
        n = _inteiro(item.get(chave), 0, 9999)
        if n:
            out[chave] = n
    if _texto(item.get("attrib"), 200):
        out["attrib"] = _texto(item.get("attrib"), 200)
    for chave in ("resist", "atk_elem"):
        d = item.get(chave)
        if isinstance(d, dict):
            limpo = {_texto(k, 20): v for k, v in d.items() if _texto(k, 20) and _inteiro(v, -999, 999)}
            if limpo:
                out[chave] = limpo
    if com_prof:
        _proficiencia(item, out)
    return out


def _proficiencia(item, out):
    """Arma: as colunas de perks (lidas da wiki, até 7 x 3) e as escolhas do jogador (ver proficiencia.py)."""
    colunas = []
    for col in (item.get("perks") if isinstance(item.get("perks"), list) else [])[:7]:
        opcoes = [{"tipo": _texto(o.get("tipo"), 60), "texto": _texto(o.get("texto"), 200)}
                  for o in (col if isinstance(col, list) else [])[:3] if isinstance(o, dict) and _texto(o.get("texto"), 200)]
        colunas.append(opcoes)
    if not any(colunas):
        return
    out["perks"] = colunas
    prof = item.get("prof") if isinstance(item.get("prof"), dict) else {}
    nivel = _inteiro(prof.get("nivel"), 0, 7)
    escolhas = [i if isinstance(i, int) and not isinstance(i, bool) and 0 <= i < 3 else 0 for i in (prof.get("escolhas") if isinstance(prof.get("escolhas"), list) else [])[:7]]
    trocas = []   # posição importa: a 1ª é a Troca 1 e a 2ª é a Troca 2 (exige Maestria); a vazia vira {}
    for t in (prof.get("trocas") if isinstance(prof.get("trocas"), list) else [])[:2]:
        ok = isinstance(t, dict) and _inteiro(t.get("coluna"), 1, 7) and _texto(t.get("opcao"), 80)
        trocas.append({"coluna": t["coluna"], "opcao": _texto(t["opcao"], 80), "rank": max(0, min(10, _inteiro(t.get("rank"), -999, 999) or 0))} if ok else {})
    while trocas and not trocas[-1]:
        trocas.pop()
    out["prof"] = {"nivel": 7 if nivel is None else nivel, "maestria": prof.get("maestria") is True, "escolhas": escolhas, "trocas": trocas}


def normalizar_set(valor):
    """{"titulo", "itens", "consumiveis"} válido; {} = sem set (informado); None continua None (não informado)."""
    if valor is None:
        return None
    if not isinstance(valor, dict):
        return {}
    itens = {}
    brutos = valor.get("itens") if isinstance(valor.get("itens"), dict) else {}
    for slot, _ in itens_set.SLOTS:                      # na ordem dos slots; slot desconhecido é descartado
        item = _normalizar_item(brutos.get(slot), com_prof=(slot == "arma"))
        if item:
            itens[slot] = item
    consumiveis, nomes = [], set()
    for c in valor.get("consumiveis") if isinstance(valor.get("consumiveis"), list) else []:
        c = {"nome": c} if isinstance(c, str) else c    # versão antiga guardava só o texto
        nome = _texto(c.get("nome"), 60) if isinstance(c, dict) else ""
        if nome and nome.lower() not in nomes:
            nomes.add(nome.lower())
            novo = {"nome": nome}
            imagem = _texto(c.get("imagem"), 400)
            if imagem.startswith(("https://", "http://")):
                novo["imagem"] = imagem
            consumiveis.append(novo)
    consumiveis = consumiveis[:MAX_CONSUMIVEIS]
    if not itens and not consumiveis:
        return {}
    saida = {"titulo": _texto(valor.get("titulo"), 60) or "Set sem título", "itens": itens, "consumiveis": consumiveis}
    if valor.get("voc") in itens_set.VOCACOES:   # vocação para a qual o set foi montado (filtra os itens ao editar)
        saida["voc"] = valor["voc"]
    return saida


def rotulo_set(valor):
    if valor is None:
        return "Set não informado"
    if not valor:
        return "Sem set"
    return f"Set: {valor.get('titulo') or 'sem título'}"


def copia_para_hunt(registro):
    """O set como fica gravado dentro da hunt (sem o id do cadastro)."""
    return normalizar_set({k: v for k, v in (registro or {}).items() if k != "id"})


def _assinatura_item(item):
    return (item["nome"], tuple(sorted(item.get("imbues") or [])))


def diferencas(a, b):
    """Rótulos (na ordem dos slots) do que mudou entre dois sets; o título não conta. {}/None = sem set."""
    a, b = a or {}, b or {}
    ia, ib = a.get("itens") or {}, b.get("itens") or {}
    saida = []
    for slot, rotulo in itens_set.SLOTS:
        x, y = ia.get(slot), ib.get(slot)
        if (x and _assinatura_item(x)) != (y and _assinatura_item(y)):
            saida.append(rotulo)
    if sorted(c["nome"] for c in a.get("consumiveis") or []) != sorted(c["nome"] for c in b.get("consumiveis") or []):
        saida.append("Consumíveis")
    return saida


# ---------------------------------------------------------------------------
# cadastro (sets.json)
# ---------------------------------------------------------------------------
def _ler(caminho=None):
    try:
        with open(caminho or SETS_PATH, "r", encoding="utf-8") as f:
            d = json.load(f)
        brutos = d.get("sets", []) if isinstance(d, dict) else []
    except (OSError, json.JSONDecodeError):
        brutos = []
    saida = []
    for b in brutos:
        if isinstance(b, dict) and b.get("id"):
            n = normalizar_set(b)
            if n:
                saida.append({"id": str(b["id"]), **n})
    return saida


def _gravar(lista, caminho=None):
    caminho = caminho or SETS_PATH
    tmp = caminho + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"formato": FORMATO, "sets": lista}, f, ensure_ascii=False, indent=1)
    os.replace(tmp, caminho)


def listar(caminho=None):
    return _ler(caminho)


def obter(id_, caminho=None):
    return next((s for s in _ler(caminho) if s["id"] == id_), None)


def salvar(dados, caminho=None):
    """Cria (sem id, ou id desconhecido) ou edita (id existente) um set. Levanta ValueError se estiver vazio."""
    n = normalizar_set(dados if isinstance(dados, dict) else None)
    if not n:
        raise ValueError("Escolha pelo menos um item (ou um consumível) para salvar o set.")
    with _trava:
        lista = _ler(caminho)
        id_ = str((dados or {}).get("id") or "")
        novo = {"id": id_ if any(s["id"] == id_ for s in lista) else uuid.uuid4().hex, **n}
        lista = [novo if s["id"] == novo["id"] else s for s in lista] if any(s["id"] == novo["id"] for s in lista) else lista + [novo]
        _gravar(lista, caminho)
    return novo


def remover(id_, caminho=None):
    with _trava:
        lista = _ler(caminho)
        resto = [s for s in lista if s["id"] != id_]
        if len(resto) == len(lista):
            return False
        _gravar(resto, caminho)
        return True
