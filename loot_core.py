#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
loot_core.py
============

Lógica pura (sem interface gráfica) do ZANDAO SPLIT LOOT:
  - parsing do texto "Session Data" copiado do Party Hunt Analyzer do Tibia
  - cálculo da divisão justa do saldo entre os membros do grupo, do mesmo
    jeito que o TibiaLootSplit (tibiapal.com/tibialootsplit)
  - geração do resumo final (o "card" com Balance / Individual balance /
    Loot per hour / % de Dano / % de Cura / Transferências)

Não depende de Tkinter nem de nada além da biblioteca padrão do Python,
para poder ser testado isoladamente e reaproveitado em outra interface
(CLI, bot de Discord, etc.) se um dia for preciso.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


# ---------------------------------------------------------------------------
# Modelo de dados
# ---------------------------------------------------------------------------

@dataclass
class PlayerStats:
    name: str
    is_leader: bool = False
    loot: int = 0
    supplies: int = 0
    balance: int = 0
    damage: int = 0
    healing: int = 0


@dataclass
class SessionData:
    period: str = ""
    duration: str = ""
    loot_type: str = ""
    loot: int = 0
    supplies: int = 0
    balance: int = 0
    damage: int = 0
    healing: int = 0
    players: list[PlayerStats] = field(default_factory=list)


@dataclass
class ExtraExpense:
    description: str
    amount: int
    paid_by: str


class ParseError(Exception):
    pass


# ---------------------------------------------------------------------------
# Parser do texto de "Session Data" do Tibia
# ---------------------------------------------------------------------------

_NUMBER_RE = re.compile(r"-?\d[\d\s.,]*\d|-?\d")
_FIELD_RE = re.compile(r"^(Loot|Supplies|Balance|Damage|Healing)\s*:\s*(.+)$", re.IGNORECASE)


def _to_int(raw: str) -> int:
    """Converte um número do Tibia ('1,234,567', '1 234 567', '-12345') para int."""
    match = _NUMBER_RE.search(raw)
    if not match:
        raise ParseError(f"Não foi possível interpretar o número: {raw!r}")
    cleaned = match.group(0)
    negative = cleaned.strip().startswith("-")
    digits = re.sub(r"[^\d]", "", cleaned)
    if digits == "":
        raise ParseError(f"Não foi possível interpretar o número: {raw!r}")
    value = int(digits)
    return -value if negative else value


def parse_session(text: str) -> SessionData:
    """Analisa o texto colado do Party Hunt Analyzer do Tibia.

    Aceita tanto o formato com linhas em branco/indentação entre os
    jogadores quanto o formato "compacto" que o próprio jogo às vezes
    gera (sem indentação e sem linhas em branco entre blocos).
    """
    if not text or not text.strip():
        raise ParseError("Cole o texto da sessão (Session Data) antes de calcular.")

    lines = [ln.rstrip() for ln in text.splitlines()]
    session = SessionData()
    current_player: Optional[PlayerStats] = None
    seen_any_field = False

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        lower = line.lower()

        if lower.startswith("session data"):
            session.period = line.split(":", 1)[1].strip() if ":" in line else ""
            continue
        if lower.startswith("session:"):
            session.duration = line.split(":", 1)[1].strip()
            continue
        if lower.startswith("loot type"):
            session.loot_type = line.split(":", 1)[1].strip()
            continue

        field_match = _FIELD_RE.match(line)
        if field_match:
            key = field_match.group(1).lower()
            value = _to_int(field_match.group(2))
            target = current_player if current_player is not None else session
            setattr(target, key, value)
            seen_any_field = True
            continue

        # Linha que não é campo conhecido nem vazia -> nome de um jogador
        # (possivelmente terminando em "(Leader)").
        name = line
        is_leader = False
        leader_match = re.search(r"\(leader\)\s*$", name, re.IGNORECASE)
        if leader_match:
            is_leader = True
            name = name[: leader_match.start()].strip()
        if name:
            current_player = PlayerStats(name=name, is_leader=is_leader)
            session.players.append(current_player)

    if not seen_any_field:
        raise ParseError(
            "Texto não reconhecido. Cole exatamente o texto copiado do "
            "Party Hunt Analyzer do Tibia (botão 'Session Data')."
        )
    if not session.players:
        raise ParseError(
            "Nenhum jogador foi encontrado no texto colado. Verifique se "
            "o texto inclui o bloco de cada personagem do grupo."
        )

    return session


# ---------------------------------------------------------------------------
# Cálculo da divisão
# ---------------------------------------------------------------------------

@dataclass
class PlayerResult:
    name: str
    is_leader: bool
    loot: int
    supplies: int
    balance: int
    fair_share: int
    adjustment: int  # positivo = deve RECEBER; negativo = deve PAGAR
    excluded: bool = False


@dataclass
class Transfer:
    payer: str
    receiver: str
    amount: int


@dataclass
class SplitResult:
    total_balance_for_split: int
    fair_share_per_player: int
    players: list[PlayerResult]
    transfers: list[Transfer]
    extra_expenses: list[ExtraExpense]
    excluded_players: list[str]


def compute_split(
    session: SessionData,
    extra_expenses: Optional[list[ExtraExpense]] = None,
    excluded_players: Optional[set[str]] = None,
) -> SplitResult:
    extra_expenses = extra_expenses or []
    excluded_players = excluded_players or set()

    active_players = [p for p in session.players if p.name not in excluded_players]
    if not active_players:
        raise ParseError("Todos os jogadores foram removidos da divisão.")

    # Saldo de cada jogador, ajustado por despesas extras que ele tenha
    # adiantado do próprio bolso (fica "mais no vermelho" e por isso será
    # reembolsado na divisão final).
    adjusted_balance: dict[str, int] = {p.name: p.balance for p in active_players}
    for exp in extra_expenses:
        if exp.paid_by in adjusted_balance:
            adjusted_balance[exp.paid_by] -= exp.amount

    total_balance_for_split = sum(adjusted_balance.values())
    n = len(active_players)
    fair_share = total_balance_for_split // n

    results: list[PlayerResult] = []
    for p in active_players:
        adjustment = fair_share - adjusted_balance[p.name]
        results.append(
            PlayerResult(
                name=p.name,
                is_leader=p.is_leader,
                loot=p.loot,
                supplies=p.supplies,
                balance=p.balance,
                fair_share=fair_share,
                adjustment=adjustment,
            )
        )
    for p in session.players:
        if p.name in excluded_players:
            results.append(
                PlayerResult(
                    name=p.name,
                    is_leader=p.is_leader,
                    loot=p.loot,
                    supplies=p.supplies,
                    balance=p.balance,
                    fair_share=0,
                    adjustment=0,
                    excluded=True,
                )
            )

    # Ordem original (a mesma em que os jogadores aparecem no texto colado),
    # preservada tanto para quem paga quanto para quem recebe — é assim que
    # o TibiaLootSplit do TibiaPal lista as transferências.
    transfers = _settle_debts([r for r in results if not r.excluded])

    return SplitResult(
        total_balance_for_split=total_balance_for_split,
        fair_share_per_player=fair_share,
        players=results,
        transfers=transfers,
        extra_expenses=extra_expenses,
        excluded_players=sorted(excluded_players),
    )


def _settle_debts(active_results: list[PlayerResult]) -> list[Transfer]:
    """Casa quem precisa pagar com quem precisa receber, na ordem original
    em que os jogadores apareceram na sessão (mesma ordem que o
    TibiaLootSplit usa para listar "transfer X to Y")."""
    debtors = [[r.name, -r.adjustment] for r in active_results if r.adjustment < 0]
    creditors = [[r.name, r.adjustment] for r in active_results if r.adjustment > 0]

    transfers: list[Transfer] = []
    i, j = 0, 0
    while i < len(debtors) and j < len(creditors):
        debtor_name, debt_amt = debtors[i]
        creditor_name, credit_amt = creditors[j]
        amount = min(debt_amt, credit_amt)
        if amount > 0:
            transfers.append(Transfer(payer=debtor_name, receiver=creditor_name, amount=amount))
        debtors[i][1] -= amount
        creditors[j][1] -= amount
        if debtors[i][1] == 0:
            i += 1
        if creditors[j][1] == 0:
            j += 1
    return transfers


def format_number(value: int) -> str:
    """Formata com vírgula como separador de milhar (padrão do próprio Tibia)."""
    sign = "-" if value < 0 else ""
    return f"{sign}{abs(value):,}"


def format_transfer_command(transfer: Transfer) -> str:
    """Texto exato para colar no chat do NPC do banco dentro do Tibia."""
    return f"transfer {transfer.amount} to {transfer.receiver}"


# ---------------------------------------------------------------------------
# Resumo final (o "card" estilo TibiaLootSplit)
# ---------------------------------------------------------------------------

_DURATION_RE = re.compile(r"(\d+):(\d+)")
_PERIOD_FROM_RE = re.compile(r"from\s+(\d{4}-\d{2}-\d{2}),\s*(\d{2}:\d{2}:\d{2})", re.IGNORECASE)


def duration_to_minutes(duration: str) -> Optional[int]:
    match = _DURATION_RE.search(duration or "")
    if not match:
        return None
    hours, minutes = int(match.group(1)), int(match.group(2))
    total = hours * 60 + minutes
    return total if total > 0 else None


def hunt_start_iso(period: str) -> Optional[str]:
    """Extrai o horário de INÍCIO da hunt a partir de 'From ... to ...'."""
    match = _PERIOD_FROM_RE.search(period or "")
    if not match:
        return None
    date_part, time_part = match.group(1), match.group(2)
    try:
        dt = datetime.strptime(f"{date_part} {time_part}", "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    return dt.isoformat(sep="T")


@dataclass
class SummaryData:
    member_count: int
    balance: int
    individual_balance: int
    loot_per_hour: Optional[int]
    damage_pct: list[tuple[str, float]]
    healing_pct: list[tuple[str, float]]
    transfers_by_payer: list[tuple[str, list[Transfer]]]
    duration: str
    hunt_start: Optional[str]


def _percentages(session: SessionData, active_names: set[str], attr: str) -> list[tuple[str, float]]:
    values = [(p.name, getattr(p, attr)) for p in session.players if p.name in active_names]
    total = sum(v for _, v in values)
    if total <= 0:
        return [(name, 0.0) for name, _ in values]
    pct = [(name, (v / total) * 100) for name, v in values]
    pct.sort(key=lambda x: -x[1])
    return pct


def build_summary(session: SessionData, result: SplitResult) -> SummaryData:
    active_names = {p.name for p in result.players if not p.excluded}

    total_minutes = duration_to_minutes(session.duration)
    # Divisão inteira exata (evita erro de arredondamento de ponto
    # flutuante quando a duração não é um número redondo de horas).
    loot_per_hour = (session.loot * 60) // total_minutes if total_minutes else None

    transfers_by_payer_map: dict[str, list[Transfer]] = {}
    for t in result.transfers:
        transfers_by_payer_map.setdefault(t.payer, []).append(t)
    transfers_by_payer = list(transfers_by_payer_map.items())

    return SummaryData(
        member_count=len(active_names),
        balance=result.total_balance_for_split,
        individual_balance=result.fair_share_per_player,
        loot_per_hour=loot_per_hour,
        damage_pct=_percentages(session, active_names, "damage"),
        healing_pct=_percentages(session, active_names, "healing"),
        transfers_by_payer=transfers_by_payer,
        duration=session.duration,
        hunt_start=hunt_start_iso(session.period),
    )


def render_summary_text(summary: SummaryData) -> str:
    """Versão em texto puro do resumo, para copiar/colar (ex: no Discord)."""
    lines = [f"ZANDAO SPLIT LOOT - Party Hunt Session - {summary.member_count} members", ""]
    lines.append(f"Balance: {format_number(summary.balance)}")
    lines.append(f"Individual balance: {format_number(summary.individual_balance)}")
    if summary.loot_per_hour is not None:
        lines.append(f"Loot per hour: {format_number(summary.loot_per_hour)}")
    lines.append("")
    lines.append("Damage:")
    for name, pct in summary.damage_pct:
        lines.append(f"  - {name} {pct:.2f}%")
    lines.append("Healing:")
    for name, pct in summary.healing_pct:
        lines.append(f"  - {name} {pct:.2f}%")
    lines.append("")
    for payer, transfers in summary.transfers_by_payer:
        lines.append(f"Transfers for {payer}")
        for t in transfers:
            lines.append(f"  {format_transfer_command(t)}")
        lines.append("")
    if summary.duration or summary.hunt_start:
        footer = f"{summary.duration} hunt" if summary.duration else "hunt"
        if summary.hunt_start:
            footer += f" on {summary.hunt_start}"
        lines.append(footer)
    return "\n".join(lines).strip()
