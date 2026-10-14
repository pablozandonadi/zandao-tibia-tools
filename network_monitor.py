"""Bounded, interface-bound IPv4 TCP monitoring. Never changes system routes."""
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import ctypes as C
import errno
import json
import math
import os
from pathlib import Path
import socket
import statistics
import struct
import sys
import threading
import time

TARGETS = (("Cloudflare", "1.1.1.1", 443), ("Google", "8.8.8.8", 443))
MAX_INTERFACES = 8
LABELS = {"checking": "Verificando", "healthy": "Saudável", "degraded": "Instável",
          "offline": "Sem acesso confirmado", "disconnected": "Desconectada",
          "unavailable": "Medição indisponível", "paused": "Pausada"}


def adapters():
    """GetAdaptersAddresses, without subprocesses or third-party dependencies."""
    if sys.platform != "win32":
        raise OSError("Monitor disponível no Windows.")
    U32 = C.c_uint32
    class SockAddr(C.Structure):
        _fields_ = [("ptr", C.c_void_p), ("length", C.c_int)]
    class Unicast(C.Structure):
        pass
    Unicast._fields_ = [("alignment", C.c_uint64), ("next", C.POINTER(Unicast)), ("address", SockAddr)]
    class Adapter(C.Structure):
        pass
    Adapter._fields_ = [("length", U32), ("index", U32), ("next", C.POINTER(Adapter)),
        ("name", C.c_char_p), ("unicast", C.POINTER(Unicast)), ("anycast", C.c_void_p),
        ("multicast", C.c_void_p), ("dns", C.c_void_p), ("suffix", C.c_wchar_p),
        ("description", C.c_wchar_p), ("friendly", C.c_wchar_p), ("physical", C.c_ubyte * 8),
        ("physical_length", U32), ("flags", U32), ("mtu", U32), ("kind", U32), ("status", U32)]
    api = C.WinDLL("iphlpapi").GetAdaptersAddresses
    api.argtypes = [U32, U32, C.c_void_p, C.c_void_p, C.POINTER(U32)]
    api.restype = U32
    size = U32(16384)
    for _ in range(3):
        buf = C.create_string_buffer(size.value)
        result = api(socket.AF_INET, 0xE, None, buf, C.byref(size))
        if result == 111:
            continue
        if result == 232:
            return []
        if result:
            raise OSError(result, "Não foi possível consultar os adaptadores.")
        rows = []
        node = C.cast(buf, C.POINTER(Adapter))
        while node:
            a = node.contents
            ips, u = [], a.unicast
            while u:
                addr = u.contents.address
                if addr.ptr and addr.length >= 8:
                    raw = C.string_at(addr.ptr, addr.length)
                    if struct.unpack_from("H", raw)[0] == socket.AF_INET:
                        ip = socket.inet_ntoa(raw[4:8])
                        if not ip.startswith(("127.", "169.254.")) and ip != "0.0.0.0":
                            ips.append(ip)
                u = u.contents.next
            if a.kind not in (24, 131) and a.index:
                rows.append({"id": a.name.decode("ascii", "replace"), "index": a.index,
                    "name": a.friendly or "Conexão", "description": a.description or "",
                    "ip": ips[0] if ips else None, "up": a.status == 1, "kind": a.kind,
                    "virtual": any(t in ((a.description or "") + " " + (a.friendly or "")).lower()
                                   for t in ("hyper-v", "vethernet", "virtual", "vpn", "tap-", "wireguard", "tunnel"))})
            node = a.next
        return rows
    raise OSError("A lista de adaptadores mudou durante a consulta.")


def probe(adapter, target, timeout=1.0, socket_factory=socket.socket):
    """No default-route fallback: configuration failures are not network failures."""
    name, host, port = target
    base = {"target": name, "ms": None, "error": None}
    if sys.platform != "win32":
        return dict(base, error="unsupported")
    try:
        sock = socket_factory(socket.AF_INET, socket.SOCK_STREAM)
    except OSError:
        return dict(base, error="measurement")
    with sock:
        try:
            sock.settimeout(timeout)
            # Windows sets this DWORD in network byte order, returns it in host order.
            sock.setsockopt(socket.IPPROTO_IP, 31, struct.pack("!I", adapter["index"]))
            if sock.getsockopt(socket.IPPROTO_IP, 31) != adapter["index"]:
                return dict(base, error="binding")
            sock.bind((adapter["ip"], 0))
        except (OSError, TypeError, KeyError):
            return dict(base, error="binding")
        start = time.perf_counter()
        try:
            sock.connect((host, port))
            if sock.getsockname()[0] != adapter["ip"]:
                return dict(base, error="binding")
            return dict(base, ms=round((time.perf_counter() - start) * 1000, 1))
        except OSError as exc:
            code = getattr(exc, "winerror", None) or exc.errno
            if isinstance(exc, (TimeoutError, socket.timeout)) or code in (
                    10060, 10051, 10065, 10061, errno.ETIMEDOUT, errno.ENETUNREACH,
                    errno.EHOSTUNREACH, errno.ECONNREFUSED):
                return dict(base, error="timeout" if isinstance(exc, TimeoutError) or code == 10060 else "unreachable")
            return dict(base, error="measurement")


class Link:
    def __init__(self, adapter):
        self.adapter = adapter
        self.state = "checking"
        self.failures = self.successes = 0
        self.healthy_since = self.last_success = None
        self.last_mono = None
        self.history = deque(maxlen=900)
        self.minutes = deque(maxlen=1440)
        self.seen = time.time()

    def reset(self):
        self.failures = self.successes = 0
        self.healthy_since = self.last_success = None
        self.state = "checking"
        self.last_mono = None
        if self.history:
            self.history.append({"t": time.time(), "ms": None, "loss": None, "state": "checking"})

    def record(self, results, now, mono, threshold):
        old = self.state
        if self.last_mono is not None and mono - self.last_mono > 15:
            self.reset()  # suspend/resume is not an ISP outage
            self.history.append({"t": now - .01, "ms": None, "loss": None, "state": "unavailable"})
        self.last_mono = mono
        valid = [r for r in results if r["error"] not in ("binding", "measurement", "unsupported")]
        good = [r["ms"] for r in valid if r["ms"] is not None]
        if not self.adapter.get("up"):
            self.state = "disconnected"
            self.failures = self.successes = 0
            self.healthy_since = None
        elif not self.adapter.get("ip") or len(valid) != len(TARGETS):
            self.state = "unavailable"
            self.failures = self.successes = 0
            self.healthy_since = None
        elif not good:
            self.failures += 1
            self.successes = 0
            self.healthy_since = None
            self.state = "offline" if self.failures >= 3 else "checking"
        else:
            self.failures = 0
            self.last_success = now
            all_good = len(good) == len(TARGETS) and max(good) < threshold
            self.successes = self.successes + 1 if all_good else 0
            if all_good:
                self.healthy_since = self.healthy_since or now
                self.state = "healthy" if self.successes >= 5 else "checking"
            else:
                self.healthy_since = None
                self.state = "degraded"
        # Fixed primary target for chart/latency: never alternate targets silently.
        primary = results[0]["ms"] if results and self.state not in ("unavailable", "disconnected") else None
        loss = round(100 * (len(valid) - len(good)) / len(valid), 1) if len(valid) == len(TARGETS) else None
        sample = {"t": now, "ms": primary, "loss": loss, "state": self.state}
        if self.state == "disconnected":
            sample.update(ms=None, loss=None)
        self.history.append(sample)
        bucket = int(now // 60)
        if not self.minutes or self.minutes[-1]["bucket"] != bucket:
            self.minutes.append({"bucket": bucket, "t": now, "sum": 0., "n": 0, "max": None,
                                 "loss_sum": 0., "loss_n": 0, "gap": False})
        b = self.minutes[-1]
        if primary is not None:
            b["sum"] += primary
            b["n"] += 1
            b["max"] = max(b["max"] or 0, primary)
        else:
            b["gap"] = True
        if sample["loss"] is not None:
            b["loss_sum"] += sample["loss"]
            b["loss_n"] += 1
        return old != self.state

    def snapshot(self, now, window):
        recent = list(self.history)
        values = [s["ms"] for s in recent if s["ms"] is not None]
        losses = [s["loss"] for s in recent if s["loss"] is not None]
        deltas = [abs(b["ms"] - a["ms"]) for a, b in zip(recent, recent[1:])
                  if a["ms"] is not None and b["ms"] is not None]
        if window <= 900:
            points = [s for s in recent if s["t"] >= now - window]
        else:
            points = [{"t": b["t"], "ms": round(b["sum"] / b["n"], 1) if b["n"] and not b["gap"] else None,
                       "max": b["max"], "loss": round(b["loss_sum"] / b["loss_n"], 1) if b["loss_n"] else None}
                      for b in self.minutes if b["t"] >= now - window]
        return {**self.adapter, "state": self.state, "label": LABELS[self.state],
            "current": recent[-1]["ms"] if recent and self.state not in ("unavailable", "disconnected") else None,
            "average": round(statistics.mean(values), 1) if values else None,
            "maximum": max(values) if values else None,
            "p95": sorted(values)[max(0, math.ceil(len(values)*.95)-1)] if values else None,
            "loss": round(statistics.mean(losses), 1) if losses else None,
            "jitter": round(statistics.mean(deltas), 1) if deltas else None,
            "healthy_for": max(0, int(now - self.healthy_since)) if self.healthy_since else 0,
            "last_success": self.last_success, "points": points}


class Monitor:
    def __init__(self, path, inventory=adapters, prober=probe, notifier=None):
        self.path = Path(path)
        self.inventory, self.prober, self.notifier = inventory, prober, notifier
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.thread = None
        self.links = {}
        self.events = deque(maxlen=200)
        self.error = None
        self.config = {"enabled": False, "sound": True, "notifications": True, "interval": 2,
                       "threshold": 150, "excluded": [], "aliases": {}, "preferred": ""}
        try:
            saved = json.loads(self.path.read_text(encoding="utf-8"))
            self.config.update(self.validate(saved))
        except (OSError, ValueError, TypeError):
            pass

    @staticmethod
    def validate(changes):
        if not isinstance(changes, dict):
            raise ValueError("Configuração inválida.")
        result = {}
        for key in ("enabled", "sound", "notifications"):
            if key in changes:
                if not isinstance(changes[key], bool):
                    raise ValueError("Opção inválida.")
                result[key] = changes[key]
        if "interval" in changes:
            if changes["interval"] not in (1, 2, 5):
                raise ValueError("Intervalo inválido.")
            result["interval"] = changes["interval"]
        if "threshold" in changes:
            value = int(changes["threshold"])
            if not 30 <= value <= 2000:
                raise ValueError("Limiar deve estar entre 30 e 2000 ms.")
            result["threshold"] = value
        if "excluded" in changes:
            if not isinstance(changes["excluded"], list) or len(changes["excluded"]) > 64:
                raise ValueError("Seleção inválida.")
            result["excluded"] = [str(x)[:200] for x in changes["excluded"]]
        if "aliases" in changes:
            if not isinstance(changes["aliases"], dict) or len(changes["aliases"]) > 64:
                raise ValueError("Nomes inválidos.")
            result["aliases"] = {str(k)[:200]: str(v).strip()[:60] for k,v in changes["aliases"].items()}
        if "preferred" in changes:
            result["preferred"] = str(changes["preferred"])[:200]
        return result

    def configure(self, changes):
        validated = self.validate(changes)
        with self.lock:
            config = dict(self.config, **validated)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.path.with_suffix(".tmp")
            temp.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
            os.replace(temp, self.path)
            if any(config[k] != self.config[k] for k in ("enabled", "excluded", "threshold")):
                for link in self.links.values():
                    link.reset()
            self.config = config
        self.start()
        return self.snapshot()

    def start(self):
        with self.lock:
            if self.thread is None:
                self.thread = threading.Thread(target=self._run, name="network-monitor", daemon=True)
                self.thread.start()

    def close(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=4)

    def _refresh(self):
        rows = self.inventory()
        now = time.time()
        with self.lock:
            ids = {a["id"] for a in rows}
            # Preserve recently unplugged interfaces, with a bounded registry.
            for link in self.links.values():
                if link.adapter["id"] not in ids:
                    link.adapter = dict(link.adapter, up=False, ip=None)
            for a in rows[:64]:
                key = a["id"]
                if key not in self.links:
                    if len(self.links) >= 64:
                        gone = next((k for k in self.links if k not in ids), None)
                        if gone is None:
                            continue
                        del self.links[gone]
                    self.links[key] = Link(a)
                    if a.get("virtual") or not a["up"]:
                        if key not in self.config["excluded"]:
                            self.config["excluded"].append(key)
                else:
                    link = self.links[key]
                    if (link.adapter["ip"], link.adapter["index"]) != (a["ip"], a["index"]):
                        link.reset()
                    link.adapter = a
                self.links[key].seen = now
            self.error = None

    def _run(self):
        next_scan = 0
        with ThreadPoolExecutor(max_workers=8, thread_name_prefix="network-probe") as pool:
            while not self.stop_event.is_set():
                began = time.monotonic()
                try:
                    if began >= next_scan:
                        self._refresh()
                        next_scan = began + 5
                    with self.lock:
                        config = dict(self.config)
                        active = [x for x in self.links.values() if x.adapter["id"] not in config["excluded"]][:MAX_INTERFACES]
                    if config["enabled"]:
                        pending = [(link, dict(link.adapter),
                                    [pool.submit(self.prober, dict(link.adapter), t) for t in TARGETS]
                                    if link.adapter["up"] and link.adapter["ip"] else []) for link in active]
                        alerts = []
                        for link, identity, futures in pending:
                            results = [f.result() for f in futures]
                            with self.lock:
                                if self.config != config:
                                    continue
                                changed = link.record(results, time.time(), time.monotonic(), config["threshold"])
                                if changed and link.state in ("healthy", "offline", "disconnected", "degraded", "unavailable"):
                                    name = config["aliases"].get(identity["id"]) or identity["name"]
                                    message = name + ": " + LABELS[link.state]
                                    event = {"t": time.time(), "name": name, "state": link.state, "message": message}
                                    self.events.appendleft(event)
                                    alerts.append(event)
                        for event in alerts:
                            self._notify(event, config)
                except Exception:
                    with self.lock:
                        self.error = "Não foi possível atualizar a medição. Tentando novamente."
                        for link in self.links.values():
                            link.reset()
                            link.state = "unavailable"
                    next_scan = 0
                self.stop_event.wait(max(.1, (config.get("interval", 2) if 'config' in locals() else 2) - (time.monotonic()-began)))

    def _notify(self, event, config):
        if config["notifications"] and self.notifier:
            try:
                self.notifier(event["message"])
            except Exception:
                pass
        if config["sound"] and sys.platform == "win32":
            try:
                import winsound
                winsound.PlaySound("SystemExclamation" if event["state"] != "healthy" else "SystemAsterisk",
                                   winsound.SND_ALIAS | winsound.SND_ASYNC)
            except (OSError, RuntimeError):
                pass

    def snapshot(self, window=300):
        window = min(86400, max(60, int(window)))
        with self.lock:
            now = time.time()
            links = [x.snapshot(now, window) for x in self.links.values()]
            eligible = [x for x in links if x["id"] not in self.config["excluded"]][:MAX_INTERFACES]
            selected = {x["id"] for x in eligible}
            for x in links:
                x["selected"] = x["id"] in selected
                x["alias"] = self.config["aliases"].get(x["id"]) or x["name"]
                if not self.config["enabled"] or not x["selected"]:
                    x.update(state="paused", label=LABELS["paused"], current=None, healthy_for=0)
            return {"config": dict(self.config), "links": links, "events": list(self.events),
                    "error": self.error, "now": now, "window": window,
                    "healthy": sum(x["state"] == "healthy" for x in links),
                    "selected": len(selected), "limit": MAX_INTERFACES,
                    "method": "TCP IPv4 · Cloudflare 1.1.1.1:443 e Google 8.8.8.8:443"}
