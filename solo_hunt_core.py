#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
solo_hunt_core.py
==================

Lógica pura (sem I/O) para o modo "Solo Hunt": analisa o texto de
"Session Data" que o próprio Hunting Analyser do Tibia gera para uma
sessão individual — diferente do texto do Party Hunt Analyzer, esse
formato traz XP (bruta e com bônus), dano/cura por hora, e as listas
completas de monstros mortos e itens coletados. Exemplo:

    Session data: From 2026-09-22, 02:19:15 to 2026-09-22, 03:16:10
    Session: 00:56h
    Raw XP Gain: 295,280
    XP Gain: 357,900
    Raw XP/h: 311,249
    XP/h: 377,256
    Loot: 38,104
    Supplies: 55,520
    Balance: -17,416
    Damage: 353,076
    Damage/h: 631,309
    Healing: 25,880
    Healing/h: 46,274
    Killed Monsters:
      1x blood priest
      21x bonebeast
    Looted Items:
      17x a great health potion
      9875x a gold coin
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from loot_core import ParseError, _to_int, duration_to_minutes, format_number, hunt_start_iso

_FIELD_RE = re.compile(
    r"^(Raw XP Gain|XP Gain|Raw XP/h|XP/h|Loot|Supplies|Balance|Damage/h|Damage|Healing/h|Healing)"
    r"\s*:\s*(.+)$",
    re.IGNORECASE,
)
_COUNTED_LINE_RE = re.compile(r"^(\d[\d,\s]*)\s*x\s+(.+)$", re.IGNORECASE)

# Mapeia o texto do campo (normalizado, sem espaço/maiúsculas) -> atributo do dataclass.
_FIELD_ATTR = {
    "rawxpgain": "raw_xp_gain",
    "xpgain": "xp_gain",
    "rawxp/h": "raw_xp_per_hour",
    "xp/h": "xp_per_hour",
    "loot": "loot",
    "supplies": "supplies",
    "balance": "balance",
    "damage": "damage",
    "damage/h": "damage_per_hour",
    "healing": "healing",
    "healing/h": "healing_per_hour",
}


@dataclass
class KillEntry:
    name: str
    count: int


@dataclass
class LootEntry:
    name: str
    count: int


@dataclass
class SoloSessionData:
    period: str = ""
    duration: str = ""
    raw_xp_gain: int = 0
    xp_gain: int = 0
    raw_xp_per_hour: int = 0
    xp_per_hour: int = 0
    loot: int = 0
    supplies: int = 0
    balance: int = 0
    damage: int = 0
    damage_per_hour: int = 0
    healing: int = 0
    healing_per_hour: int = 0
    killed_monsters: list[KillEntry] = field(default_factory=list)
    looted_items: list[LootEntry] = field(default_factory=list)


def parse_solo_session(text: str) -> SoloSessionData:
    if not text or not text.strip():
        raise ParseError("Cole o texto da sessão (Session Data) antes de analisar.")

    lines = [ln.rstrip() for ln in text.splitlines()]
    session = SoloSessionData()
    seen_any_field = False

    mode: Optional[str] = None  # None | "monsters" | "items"

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        lower = line.lower()

        if lower.startswith("session data"):
            session.period = line.split(":", 1)[1].strip() if ":" in line else ""
            mode = None
            continue
        if lower.startswith("session:"):
            session.duration = line.split(":", 1)[1].strip()
            mode = None
            continue
        if lower.startswith("killed monsters"):
            mode = "monsters"
            continue
        if lower.startswith("looted items"):
            mode = "items"
            continue

        field_match = _FIELD_RE.match(line)
        if field_match and mode is None:
            key = re.sub(r"\s+", "", field_match.group(1)).lower()
            attr = _FIELD_ATTR.get(key)
            if attr:
                setattr(session, attr, _to_int(field_match.group(2)))
                seen_any_field = True
                continue

        counted_match = _COUNTED_LINE_RE.match(line)
        if counted_match and mode in ("monsters", "items"):
            count = _to_int(counted_match.group(1))
            name = counted_match.group(2).strip()
            if mode == "monsters":
                session.killed_monsters.append(KillEntry(name=name, count=count))
            else:
                session.looted_items.append(LootEntry(name=name, count=count))
            continue

    if not seen_any_field:
        raise ParseError(
            "Texto não reconhecido. Cole exatamente o texto de 'Session Data' de uma "
            "hunt solo (Hunting Analyser do Tibia)."
        )

    session.killed_monsters.sort(key=lambda k: -k.count)
    session.looted_items.sort(key=lambda i: -i.count)
    return session


@dataclass
class SoloSummary:
    duration: str
    hunt_start: Optional[str]
    raw_xp_gain: int
    xp_gain: int
    bonus_xp: int
    raw_xp_per_hour: int
    xp_per_hour: int
    loot: int
    supplies: int
    balance: int
    balance_per_hour: Optional[int]
    damage: int
    damage_per_hour: int
    healing: int
    healing_per_hour: int
    killed_monsters: list[KillEntry]
    looted_items: list[LootEntry]
    total_kills: int
    total_looted: int


def build_solo_summary(session: SoloSessionData) -> SoloSummary:
    total_minutes = duration_to_minutes(session.duration)
    balance_per_hour = (session.balance * 60) // total_minutes if total_minutes else None
    return SoloSummary(
        duration=session.duration,
        hunt_start=hunt_start_iso(session.period),
        raw_xp_gain=session.raw_xp_gain,
        xp_gain=session.xp_gain,
        bonus_xp=session.xp_gain - session.raw_xp_gain,
        raw_xp_per_hour=session.raw_xp_per_hour,
        xp_per_hour=session.xp_per_hour,
        loot=session.loot,
        supplies=session.supplies,
        balance=session.balance,
        balance_per_hour=balance_per_hour,
        damage=session.damage,
        damage_per_hour=session.damage_per_hour,
        healing=session.healing,
        healing_per_hour=session.healing_per_hour,
        killed_monsters=session.killed_monsters,
        looted_items=session.looted_items,
        total_kills=sum(k.count for k in session.killed_monsters),
        total_looted=sum(i.count for i in session.looted_items),
    )


def render_solo_summary_text(character_name: str, summary: SoloSummary) -> str:
    lines = [f"ZANDAO SPLIT LOOT - Solo Hunt - {character_name}", ""]
    lines.append(f"XP Gain: {format_number(summary.xp_gain)} (raw {format_number(summary.raw_xp_gain)}, bonus {format_number(summary.bonus_xp)})")
    lines.append(f"XP/h: {format_number(summary.xp_per_hour)} (raw {format_number(summary.raw_xp_per_hour)})")
    lines.append(f"Loot: {format_number(summary.loot)}  Supplies: {format_number(summary.supplies)}  Balance: {format_number(summary.balance)}")
    lines.append(f"Damage: {format_number(summary.damage)} ({format_number(summary.damage_per_hour)}/h)")
    lines.append(f"Healing: {format_number(summary.healing)} ({format_number(summary.healing_per_hour)}/h)")
    lines.append("")
    lines.append(f"Killed Monsters ({summary.total_kills}):")
    for k in summary.killed_monsters:
        lines.append(f"  {k.count}x {k.name}")
    lines.append("")
    lines.append(f"Looted Items ({summary.total_looted}):")
    for i in summary.looted_items:
        lines.append(f"  {i.count}x {i.name}")
    if summary.duration or summary.hunt_start:
        lines.append("")
        footer = f"{summary.duration} hunt" if summary.duration else "hunt"
        if summary.hunt_start:
            footer += f" on {summary.hunt_start}"
        lines.append(footer)
    return "\n".join(lines).strip()
