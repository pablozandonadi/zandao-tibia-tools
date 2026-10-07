"""Junta os três textos copiados do Tibia numa análise só, no estilo do hunt-analyser.com:

- Party Hunt Analyser ("Session Data" do grupo)  -> Loot Split (loot_core)
- Hunting Analyser (a sua hunt: XP, monstros, itens) -> solo_hunt_core
- Received Damage (Damage Input)                  -> damage_core (a parte de monstros/wiki é feita depois, em segundo plano)

Qualquer um dos três pode faltar. Sem internet nem IA: é só parsing e conta.
"""

import hashlib
import re

import damage_core
import embuimentos as emb
import loot_core as lc
import solo_hunt_core as sc


def detectar(texto):
    """'party', 'solo', 'dano' ou None, olhando só o conteúdo do texto."""
    t = texto or ""
    if not t.strip():
        return None
    if damage_core.eh_damage_input(t):
        return "dano"
    low = t.lower()
    if "loot type" in low:
        return "party"
    if re.search(r"raw xp gain|xp gain|killed monsters|looted items|xp/h", low):
        return "solo"
    try:
        if lc.parse_session(t).players:
            return "party"
    except lc.ParseError:
        pass
    return None


def assinatura(entrada):
    """Identifica a hunt pelos textos colados: analisar de novo a mesma hunt atualiza o histórico em vez de duplicar."""
    partes = [(entrada.get(k) or "").strip() for k in ("party", "solo", "dano")]
    return hashlib.sha1("\0".join(partes).encode("utf-8")).hexdigest()


def fmt(n):
    """Número no padrão do Tibia: 1,234,567."""
    return "—" if n is None else lc.format_number(int(n))


def _por_hora(valor, minutos):
    return (valor * 60) // minutos if (valor is not None and minutos) else None


def _data_hunt(periodo):
    iso = lc.hunt_start_iso(periodo or "")
    return iso[:16].replace("T", " ") if iso else None


def montar(entrada):
    """entrada: {'nome', 'party', 'solo', 'dano', 'despesas': [{'descricao','valor','pago_por'}],
                 'excluidos': [nomes], 'personagem'}"""
    erros = {}
    party = solo = dano = None

    if (entrada.get("party") or "").strip():
        try:
            party = lc.parse_session(entrada["party"])
        except lc.ParseError as e:
            erros["party"] = str(e)
    if (entrada.get("solo") or "").strip():
        try:
            solo = sc.build_solo_summary(sc.parse_solo_session(entrada["solo"]))
        except lc.ParseError as e:
            erros["solo"] = str(e)
    if (entrada.get("dano") or "").strip():
        dano = damage_core.parse_damage_input(entrada["dano"])
        if not dano["tipos"] and not dano["fontes"]:
            erros["dano"] = "Texto não reconhecido. Copie o 'Received Damage' (Damage Input) do cliente do Tibia."
            dano = None

    if not (party or solo or dano):
        return {"vazio": True, "erros": erros}

    # ---------- despesas extras ----------
    despesas = []
    for d in entrada.get("despesas") or []:
        valor = emb.parse_num(str(d.get("valor") or ""))
        if valor:
            despesas.append(lc.ExtraExpense(description=(d.get("descricao") or "Despesa").strip(),
                                            amount=int(valor), paid_by=d.get("pago_por") or ""))

    personagem = (entrada.get("personagem") or "").strip()
    out = {"vazio": False, "erros": erros, "tem": {"party": bool(party), "solo": bool(solo), "dano": bool(dano)}}

    duracao = (party.duration if party else "") or (solo.duration if solo else "")
    minutos = lc.duration_to_minutes(duracao)
    out["data"] = _data_hunt(party.period if party else "") or (solo.hunt_start[:16].replace("T", " ") if solo and solo.hunt_start else None)

    resumo = {"duracao": duracao or "—", "minutos": minutos}
    if solo:
        resumo.update({
            "xp": solo.xp_gain, "xp_raw": solo.raw_xp_gain,
            "xp_h": solo.xp_per_hour or _por_hora(solo.xp_gain, minutos),
            "xp_raw_h": solo.raw_xp_per_hour or _por_hora(solo.raw_xp_gain, minutos),
        })

    # ---------- loot split ----------
    if party:
        excluidos = {n for n in (entrada.get("excluidos") or []) if any(p.name == n for p in party.players)}
        if len(excluidos) >= len(party.players):
            excluidos = set()
        split = lc.compute_split(party, despesas, excluidos)
        res = {r.name: r for r in split.players}
        ativos = [p for p in party.players if p.name not in excluidos]
        tot_dano = sum(p.damage for p in ativos) or 0
        tot_cura = sum(p.healing for p in ativos) or 0
        membros = []
        for p in party.players:
            r = res[p.name]
            membros.append({
                "nome": p.name, "lider": p.is_leader, "excluido": r.excluded,
                "dano": p.damage, "dano_pct": (p.damage / tot_dano * 100) if tot_dano and not r.excluded else 0,
                "cura": p.healing, "cura_pct": (p.healing / tot_cura * 100) if tot_cura and not r.excluded else 0,
                "loot": p.loot, "supplies": p.supplies, "balance": p.balance,
                "dano_h": _por_hora(p.damage, minutos), "cura_h": _por_hora(p.healing, minutos),
                "balance_h": _por_hora(p.balance, minutos),  # "Profit/h" na tela: o de cada um, antes da divisão
                "ajuste": r.adjustment, "eu": p.name.lower() == personagem.lower(),
            })
        membros.sort(key=lambda m: (m["excluido"], -m["dano"]))
        transf = [{"pagador": t.payer, "recebedor": t.receiver, "valor": t.amount,
                   "comando": lc.format_transfer_command(t), "chave": f"{t.payer}>{t.receiver}"}
                  for t in split.transfers]
        top = max(ativos, key=lambda p: p.damage) if ativos else None
        resumo.update({
            "balance": party.balance, "loot": party.loot, "supplies": party.supplies,
            "lucro": split.fair_share_per_player, "lucro_h": _por_hora(split.fair_share_per_player, minutos),
            "balance_h": _por_hora(party.balance, minutos), "loot_h": _por_hora(party.loot, minutos),
            "top_dano_nome": top.name if top else None, "top_dano": top.damage if top else None,
            "despesas": sum(d.amount for d in despesas), "membros": len(ativos),
            "loot_type": party.loot_type,
        })
        out["membros"] = membros
        out["transferencias"] = transf
        out["personagens"] = [p.name for p in party.players]
        detalhes = []
        for m in membros:
            detalhes.append({
                **m,
                "paga": [t for t in transf if t["pagador"] == m["nome"]],
                "recebe": [t for t in transf if t["recebedor"] == m["nome"]],
                "fica_com": m["balance"] + m["ajuste"],
                "hunt": bool(solo) and m["eu"],
            })
        out["detalhes"] = detalhes
        out["texto_split"] = lc.render_summary_text(lc.build_summary(party, split))
    elif solo:
        resumo.update({
            "balance": solo.balance, "loot": solo.loot, "supplies": solo.supplies, "lucro": solo.balance,
            "balance_h": solo.balance_per_hour, "loot_h": _por_hora(solo.loot, minutos),
            "top_dano_nome": personagem or None, "top_dano": solo.damage, "despesas": 0, "membros": 1,
        })

    if solo:
        out["solo"] = {
            "dano": solo.damage, "dano_h": solo.damage_per_hour, "cura": solo.healing, "cura_h": solo.healing_per_hour,
            "loot": solo.loot, "supplies": solo.supplies, "balance": solo.balance,
            "xp": solo.xp_gain, "xp_raw": solo.raw_xp_gain, "bonus": solo.bonus_xp,
            "kills_total": solo.total_kills, "itens_total": solo.total_looted,
            "itens": [{"nome": i.name, "qtd": i.count} for i in solo.looted_items],
        }
        out["kills"] = [{"nome": k.name, "kills": k.count} for k in solo.killed_monsters]
    else:
        out["kills"] = []
    out["dano_input"] = dano
    out["resumo"] = resumo
    return out


def texto_discord(nome, a, analise_dano=None):
    """Texto para colar no Discord/WhatsApp com o essencial da hunt."""
    r = a["resumo"]
    linhas = [f"⚔️ {nome or 'Hunt'}" + (f" ({a['data']})" if a.get("data") else ""), ""]
    linhas.append(f"Sessão: {r['duracao']}")
    if r.get("xp") is not None:
        linhas.append(f"XP: {fmt(r['xp'])} (raw {fmt(r['xp_raw'])}) · XP/h {fmt(r.get('xp_h'))}")
    if r.get("balance") is not None:
        linhas.append(f"Balance: {fmt(r['balance'])} · Balance/h {fmt(r.get('balance_h'))}")
    if a["tem"]["party"]:
        linhas.append(f"Lucro por membro: {fmt(r['lucro'])} ({r['membros']} membros)")
        if r.get("despesas"):
            linhas.append(f"Despesas extras: {fmt(r['despesas'])}")
        linhas.append("")
        linhas.append("Dano:")
        for m in a["membros"]:
            if not m["excluido"]:
                linhas.append(f"  {m['nome']}: {fmt(m['dano'])} ({m['dano_pct']:.1f}%)")
        if a["transferencias"]:
            linhas.append("")
            linhas.append("Transferências:")
            for t in a["transferencias"]:
                linhas.append(f"  {t['pagador']}: {t['comando']}")
    if a.get("kills"):
        linhas.append("")
        linhas.append("Monstros: " + ", ".join(f"{k['kills']}x {k['nome']}" for k in a["kills"][:8]))
    if analise_dano and analise_dano.get("elementos"):
        linhas.append("")
        linhas.append("Dano recebido: " + ", ".join(f"{e['rotulo']} {e['parte'] * 100:.0f}%" for e in analise_dano["elementos"][:5]))
        if analise_dano.get("protecoes"):
            linhas.append("Proteções: " + ", ".join(p["rotulo"] for p in analise_dano["protecoes"][:3]))
        bons = [o for o in analise_dano["ofensivo"] if not o["sem_dados"]][:2]
        if bons:
            linhas.append("Melhor elemento p/ atacar: " + ", ".join(f"{o['rotulo']} ({o['media']:.0f}%)" for o in bons))
    return "\n".join(linhas).strip()
