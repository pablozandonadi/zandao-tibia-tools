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
READ_INTERVAL = 1.0
HIGH_PING_MS = 100
ADAPTER_INTERVAL = 0.25


def connection(state):
    return True if state in ("healthy", "degraded") else False if state in ("offline", "disconnected") else None

LABELS = {"checking": "Verificando", "healthy": "Conectado", "degraded": "Conectado",
          "offline": "Desconectado", "disconnected": "Desconectado",
          "unavailable": "Medição indisponível", "paused": "Pausada"}


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

_ADAPTER_API = None

def adapters():
    """GetAdaptersAddresses, without subprocesses or third-party dependencies."""
    if sys.platform != "win32":
        raise OSError("Monitor disponível no Windows.")
    global _ADAPTER_API
    if _ADAPTER_API is None:
        api = C.WinDLL("iphlpapi").GetAdaptersAddresses
        api.argtypes = [U32, U32, C.c_void_p, C.c_void_p, C.POINTER(U32)]
        api.restype = U32
        _ADAPTER_API = api
    api = _ADAPTER_API
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
        self.generation = 0
        self.announced = None
        self.high_event = None
        self.loss_event = None
        self.started = None
        self.total_mono = None
        self.total_connection = None
        self.total_high = False
        self.totals = {"readings": 0, "latency_n": 0, "latency_sum": 0., "maximum": None,
                       "attempts": 0, "failures": 0, "timeouts": 0, "measurement_errors": 0,
                       "high_readings": 0, "high_episodes": 0, "outages": 0,
                       "observed_seconds": 0., "connected_seconds": 0., "disconnected_seconds": 0.,
                       "unknown_seconds": 0., "high_seconds": 0.}

    def _accumulate(self, mono):
        if self.total_mono is not None:
            elapsed = mono - self.total_mono
            if 0 <= elapsed <= 3:
                self.totals["observed_seconds"] += elapsed
                key = "connected_seconds" if self.total_connection is True else "disconnected_seconds" if self.total_connection is False else "unknown_seconds"
                self.totals[key] += elapsed
                if self.total_high:
                    self.totals["high_seconds"] += elapsed
        self.total_mono = mono

    def _remember(self, mono, high=False):
        self.total_mono = mono
        self.total_connection = connection(self.state)
        self.total_high = high

    def reset(self):
        if self.loss_event is not None:
            self.loss_event["active"] = False
            self.loss_event = None
        self.total_mono = None
        self.total_high = False
        if self.high_event is not None:
            self.high_event["active"] = False
            self.high_event = None
        self.generation += 1
        self.failures = self.successes = 0
        self.healthy_since = self.last_success = None
        self.state = "checking"
        self.last_mono = None
        if self.history:
            self.history.append({"t": time.time(), "ms": None, "loss": None, "state": "checking"})

    def record(self, results, now, mono, threshold):
        old = self.state
        self.started = self.started or now
        self._accumulate(mono)
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
        elif not self.adapter.get("ip") or (not good and len(valid) != len(TARGETS)):
            self.state = "unavailable"
            self.failures = self.successes = 0
            self.healthy_since = None
        elif not good:
            self.failures += 1
            self.successes = 0
            self.healthy_since = None
            self.state = "offline" if self.failures >= 2 else "checking"
        else:
            self.failures = 0
            self.last_success = now
            all_good = len(good) == len(TARGETS) and max(good) <= HIGH_PING_MS
            self.successes = self.successes + 1 if all_good else 0
            if all_good:
                self.healthy_since = self.healthy_since or now
                self.state = "healthy"
            else:
                self.healthy_since = self.healthy_since or now
                self.state = "degraded"
        if results:
            self.totals["readings"] += 1
            self.totals["attempts"] += len(valid)
            self.totals["failures"] += len(valid) - len(good)
            self.totals["timeouts"] += sum(r["error"] == "timeout" for r in valid)
            self.totals["measurement_errors"] += len(results) - len(valid)
        high = any(v > HIGH_PING_MS for v in good)
        if high:
            self.totals["high_readings"] += 1
            if not self.total_high:
                self.totals["high_episodes"] += 1
        self._remember(mono, high)
        # Fixed primary target for chart/latency: never alternate targets silently.
        primary = results[0]["ms"] if results and self.state not in ("unavailable", "disconnected") else None
        loss = round(100 * (len(valid) - len(good)) / len(valid), 1) if len(valid) == len(TARGETS) else None
        if primary is not None:
            self.totals["latency_n"] += 1
            self.totals["latency_sum"] += primary
            self.totals["maximum"] = max(self.totals["maximum"] or 0, primary)
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
        totals = dict(self.totals)
        totals["average"] = round(totals["latency_sum"] / totals["latency_n"], 1) if totals["latency_n"] else None
        totals["failure_percent"] = round(100 * totals["failures"] / totals["attempts"], 1) if totals["attempts"] else None
        totals["high_percent"] = round(100 * totals["high_readings"] / totals["readings"], 1) if totals["readings"] else None
        totals["since"] = self.started
        return {**self.adapter, "state": self.state, "label": LABELS[self.state],
            "connected": connection(self.state),
            "quality": "Ping acima de 100 ms ou resposta parcial" if self.state == "degraded" else None,
            "current": recent[-1]["ms"] if recent and self.state not in ("unavailable", "disconnected") else None,
            "average": round(statistics.mean(values), 1) if values else None,
            "maximum": max(values) if values else None,
            "p95": sorted(values)[max(0, math.ceil(len(values)*.95)-1)] if values else None,
            "loss": round(statistics.mean(losses), 1) if losses else None,
            "jitter": round(statistics.mean(deltas), 1) if deltas else None,
            "connected_for": max(0, int(now - self.healthy_since)) if self.healthy_since else 0,
            "last_success": self.last_success, "points": points, "totals": totals}


class Monitor:
    def __init__(self, path, inventory=adapters, prober=probe, notifier=None):
        self.path = Path(path)
        self.inventory, self.prober, self.notifier = inventory, prober, notifier
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.thread = None
        self.inventory_thread = None
        self.inventory_ready = threading.Event()
        self.links = {}
        self.events = deque(maxlen=200)
        self.error = None
        self.config = {"enabled": False, "sound": True, "notifications": True, "interval": 1,
                       "threshold": HIGH_PING_MS, "excluded": [], "aliases": {}, "preferred": ""}
        try:
            saved = json.loads(self.path.read_text(encoding="utf-8"))
            self.config.update(self.validate(saved))
            self.config["interval"] = 1
            self.config["threshold"] = HIGH_PING_MS
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
        # Cadence is fixed; old saved intervals are deliberately ignored.
        if "interval" in changes:
            result["interval"] = 1
        if "threshold" in changes:
            result["threshold"] = HIGH_PING_MS
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
            if any(config[k] != self.config[k] for k in ("enabled", "excluded")):
                for link in self.links.values():
                    link.reset()
            self.config = config
        self.start()
        return self.snapshot()

    def start(self):
        with self.lock:
            if self.thread is None:
                self.inventory_thread = threading.Thread(target=self._watch_adapters, name="network-adapters", daemon=True)
                self.thread = threading.Thread(target=self._run, name="network-monitor", daemon=True)
                self.inventory_thread.start()
                self.thread.start()

    def close(self):
        self.stop_event.set()
        for thread in (self.inventory_thread, self.thread):
            if thread:
                thread.join(timeout=4)

    def _selected(self):
        return [x for x in self.links.values() if x.adapter["id"] not in self.config["excluded"]][:MAX_INTERFACES]

    def _event(self, link, physical=False):
        """Called under lock. Quality changes never produce connection notifications."""
        status = connection(link.state)
        if not self.config["enabled"] or link not in self._selected() or status is None:
            return None
        if not physical and link.announced is status:
            return None
        if status is False and link.announced is not False:
            link.totals["outages"] += 1
        link.announced = status
        name = self.config["aliases"].get(link.adapter["id"]) or link.adapter["name"]
        event = {"t": time.time(), "name": name, "state": "healthy" if status else "disconnected",
                 "kind": "connection", "message": name + (": Conectado" if status else ": Desconectado")}
        self.events.appendleft(event)
        return event

    def _quality_event(self, link, results, now):
        high = [r for r in results if r["ms"] is not None and r["ms"] > HIGH_PING_MS]
        if high:
            name = self.config["aliases"].get(link.adapter["id"]) or link.adapter["name"]
            if link.high_event is None:
                link.high_event = {"t": now, "name": name, "state": "degraded", "kind": "quality",
                                   "peak": 0, "samples": 0, "duration": 0, "active": True}
                self.events.appendleft(link.high_event)
            event = link.high_event
            event["peak"] = max(event["peak"], max(r["ms"] for r in high))
            event["samples"] += 1
            event["duration"] = max(0, round(now - event["t"], 1))
            event["message"] = (name + ": ping acima de 100 ms · pico " + str(round(event["peak"])) +
                                " ms · " + str(event["samples"]) + " leituras · " + str(event["duration"]) + " s")
        elif link.high_event is not None:
            link.high_event["active"] = False
            link.high_event = None

        failed = [r for r in results if r["error"] in ("timeout", "unreachable")]
        if failed:
            name = self.config["aliases"].get(link.adapter["id"]) or link.adapter["name"]
            if link.loss_event is None:
                link.loss_event = {"t": now, "name": name, "state": "degraded", "kind": "probe_failure",
                                   "failures": 0, "timeouts": 0, "samples": 0, "active": True}
                self.events.appendleft(link.loss_event)
            event = link.loss_event
            event["failures"] += len(failed)
            event["timeouts"] += sum(r["error"] == "timeout" for r in failed)
            event["samples"] += 1
            event["message"] = (name + ": falhas nas sondas · " + str(event["failures"]) + " falhas · " +
                                str(event["timeouts"]) + " timeouts · " + str(event["samples"]) + " leituras")
        elif link.loss_event is not None:
            link.loss_event["active"] = False
            link.loss_event = None

    def _refresh(self):
        rows = self.inventory()
        now = time.time()
        alerts = []
        with self.lock:
            ids = {a["id"] for a in rows}
            updates = list(rows[:64]) + [dict(x.adapter, up=False, ip=None)
                       for x in self.links.values() if x.adapter["id"] not in ids]
            for a in updates:
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
                    old = link.adapter
                    changed = (old["up"], old["ip"], old["index"]) != (a["up"], a["ip"], a["index"])
                    if changed:
                        link._accumulate(time.monotonic())
                        last_success = link.last_success
                        link.reset()  # invalidate any probe from before the cable/IP change
                    link.adapter = a
                    if not a["up"]:
                        link.state = "disconnected"
                        if changed:
                            link.last_success = last_success
                            link._remember(time.monotonic())
                        if old["up"]:
                            # This path never waits for external probes, even if already offline.
                            event = self._event(link, physical=True)
                            if event:
                                alerts.append(event)
                self.links[key].seen = now
            self.error = None
            config = dict(self.config)
        for event in alerts:
            self._notify(event, config)

    def _watch_adapters(self):
        while not self.stop_event.is_set():
            try:
                self._refresh()
            except Exception:
                with self.lock:
                    self.error = "Não foi possível consultar os adaptadores. Tentando novamente."
            finally:
                self.inventory_ready.set()
            self.stop_event.wait(ADAPTER_INTERVAL)

    def _run(self):
        self.inventory_ready.wait(2)
        # Both targets for all selected interfaces can run together, with a fixed socket cap.
        with ThreadPoolExecutor(max_workers=MAX_INTERFACES * len(TARGETS), thread_name_prefix="network-probe") as pool:
            while not self.stop_event.is_set():
                began = time.monotonic()
                try:
                    with self.lock:
                        config = dict(self.config, excluded=list(self.config["excluded"]), aliases=dict(self.config["aliases"]))
                        pending = [(link, link.generation,
                                    [pool.submit(self.prober, dict(link.adapter), t, .8) for t in TARGETS]
                                    if link.adapter["up"] and link.adapter["ip"] else [])
                                   for link in self._selected()] if config["enabled"] else []
                    for link, generation, futures in pending:
                        try:
                            results = [f.result() for f in futures]
                        except Exception:
                            results = [{"target": t[0], "ms": None, "error": "measurement"} for t in TARGETS]
                        with self.lock:
                            if self.config != config or link.generation != generation:
                                continue
                            link.record(results, time.time(), time.monotonic(), config["threshold"])
                            self._quality_event(link, results, time.time())
                            event = self._event(link)
                        if event:
                            self._notify(event, config)
                except Exception:
                    with self.lock:
                        self.error = "Não foi possível atualizar a medição. Tentando novamente."
                        for link in self.links.values():
                            link.reset()
                            link.state = "unavailable"
                self.stop_event.wait(max(.01, READ_INTERVAL - (time.monotonic() - began)))

    def _notify(self, event, config):
        if event.get("kind") != "connection":
            return
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
                    x.update(state="paused", label=LABELS["paused"], current=None, connected=None, connected_for=0)
            return {"config": dict(self.config), "links": links, "events": [dict(e) for e in self.events],
                    "error": self.error, "now": now, "window": window,
                    "connected": sum(x["selected"] and x["connected"] is True for x in links),
                    "selected": len(selected), "limit": MAX_INTERFACES,
                    "method": "TCP IPv4 · Cloudflare 1.1.1.1:443 e Google 8.8.8.8:443"}
