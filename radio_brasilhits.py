"""Cliente somente de leitura da Brasil Hits, independente do player de áudio."""
import copy
import json
import re
import threading
import time
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

BASE = "https://www.brasilhits.com"
HOSTS = {"www.brasilhits.com", "brasilhits.com", "live.brasilhits.com"}
IDENT = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
MAX_BYTES = 512 * 1024


def safe_url(value):
    if not isinstance(value, str) or len(value) > 2048:
        return ""
    try:
        p = urlsplit(value)
        return value if (p.scheme == "https" and p.hostname in HOSTS
                         and not p.username and not p.password and p.port in (None, 443)) else ""
    except ValueError:
        return ""


class SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not safe_url(newurl):
            raise ValueError("Redirecionamento da rádio não permitido.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_json(path):
    request = Request(BASE + path, headers={"User-Agent": "TibiaTudo-BrasilHits/1", "Accept": "application/json"})
    with build_opener(SafeRedirect()).open(request, timeout=8) as response:
        if not safe_url(response.url):
            raise ValueError("Origem da rádio não permitida.")
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("Resposta da rádio muito grande.")
    return json.loads(raw.decode("utf-8"))


def text(value, limit=200):
    return value[:limit] if isinstance(value, str) else ""


def normalize_catalog(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get("stations"), list):
        raise ValueError("Catálogo da rádio inválido.")
    stations, seen = [], set()
    for item in payload["stations"][:50]:
        if not isinstance(item, dict):
            continue
        sid, slug = item.get("id"), item.get("slug")
        if not isinstance(sid, str) or not isinstance(slug, str) or not IDENT.fullmatch(sid) or not IDENT.fullmatch(slug) or sid in seen:
            continue
        seen.add(sid)
        qualities = []
        for q in (item.get("qualities") if isinstance(item.get("qualities"), list) else [])[:10]:
            if not isinstance(q, dict) or not isinstance(q.get("id"), str) or not IDENT.fullmatch(q["id"]) or not safe_url(q.get("url")):
                continue
            if any(x["id"] == q["id"] for x in qualities):
                continue
            qualities.append({"id": q["id"], "label": text(q.get("label"), 40) or q["id"], "url": safe_url(q["url"])})
        # An explicit unsupported stream must not silently become an unrelated fallback.
        configured = item.get("streamUrl")
        stream = safe_url(configured) if configured else f"https://live.brasilhits.com/listen/{slug}/acc"
        stations.append({"id": sid, "slug": slug, "label": text(item.get("label"), 80) or sid,
                         "maintenance": bool(item.get("maintenance")), "url": stream, "qualities": qualities})
    if not stations:
        raise ValueError("Nenhuma estação válida disponível.")
    return stations


def normalize_preferences(value):
    p = value if isinstance(value, dict) else {}
    channel = p.get("channel", "pop")
    quality = p.get("quality", "")
    try:
        volume = max(0, min(100, int(p.get("volume", 50))))
    except (ValueError, TypeError, OverflowError):
        volume = 50
    return {"channel": channel if isinstance(channel, str) and IDENT.fullmatch(channel) else "pop",
            "quality": quality if isinstance(quality, str) and IDENT.fullmatch(quality) else "", "volume": volume}


class Client:
    def __init__(self, fetch=fetch_json, clock=time.monotonic):
        self._fetch, self._clock = fetch, clock
        self._lock = threading.RLock()
        self._stations = []
        self._updated = float("-inf")
        self._stale = False

    def catalog(self):
        with self._lock:
            if self._clock() - self._updated >= 60:
                try:
                    stations = normalize_catalog(self._fetch("/api/stations"))
                    self._stations = stations
                    self._stale = False
                except Exception:
                    if not self._stations:
                        return {"ok": False, "error": "Não foi possível carregar as rádios. Tente novamente."}
                    self._stale = True
                self._updated = self._clock()
            return {"ok": True, "stations": copy.deepcopy(self._stations), "stale": self._stale}

    def now_playing(self, station_id):
        with self._lock:
            if not any(s["id"] == station_id for s in self._stations):
                return {"ok": False, "error": "Estação inválida."}
        try:
            data = self._fetch("/api/np/" + station_id)
            if not isinstance(data, dict):
                raise ValueError("Metadados inválidos")
            current = data.get("current") or {}
            if not isinstance(current, dict):
                current = {}
            return {"ok": True, "title": text(current.get("title")), "artist": text(current.get("artist")),
                    "online": data.get("isOnline") is not False, "maintenance": bool(data.get("maintenance"))}
        except Exception:
            return {"ok": False, "error": "Informações da música indisponíveis."}
