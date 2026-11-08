#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# LinSpectacles TUI - Resource Monitor
# Copyright (C) 2026 brunonlinespace
# GPL-3.0-or-later

"""Linux-native Windows Resource Monitor inspired TUI.

The approved 0.0.3 layout is retained: the left pane chooses a resource view,
the right pane contains its live data, and there is no Overview page. 0.0.11-exp1
changes only Memory navigation/content so it mirrors the GUI's Processes / Physical
Memory split while preserving the approved CPU, Disk, Network and privilege behavior.

Privilege remains optional. The TUI itself is never elevated; ``P`` starts the
same root-owned, fixed-protocol read-only helper used by the GUI.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import os
import socket
import subprocess
import time

try:
    from ._tui_support import BaseTUIApplet
    from .privilege import PrivilegeClient
except ImportError:
    from _tui_support import BaseTUIApplet
    from privilege import PrivilegeClient

try:
    import psutil
except ImportError:
    psutil = None


class ResourceMonitorTUI(BaseTUIApplet):
    name = "Resource Monitor"
    metadata_title = " Resource Monitor "
    live = True
    export_enabled = False

    # Every row is selectable so this works with the existing LinSpectacles host,
    # which owns Up/Down navigation and has no notion of non-selectable headers.
    # The first child is therefore rendered as "GROUP — child" and siblings are
    # indented. This gives the requested hierarchy without adding dead rows.
    VIEW_ROWS = (
        {"name": "CPU — Processes", "view": "cpu_processes", "group": "CPU", "leaf": "Processes"},
        {"name": "    Services", "view": "cpu_services", "group": "CPU", "leaf": "Services"},
        {"name": "    Associated Handles", "view": "cpu_handles", "group": "CPU", "leaf": "Associated Handles"},
        {"name": "    Associated Modules", "view": "cpu_modules", "group": "CPU", "leaf": "Associated Modules"},
        {"name": "Memory", "view": "memory", "group": "Memory", "leaf": "Processes"},
        {"name": "Disk — Processes with Disk Activity", "view": "disk_processes", "group": "Disk", "leaf": "Processes with Disk Activity"},
        {"name": "    Disk Activity", "view": "disk_activity", "group": "Disk", "leaf": "Disk Activity"},
        {"name": "    Disk Devices", "view": "disk_devices", "group": "Disk", "leaf": "Disk Devices"},
        {"name": "Network — Processes with Network Sockets", "view": "network_processes", "group": "Network", "leaf": "Processes with Network Sockets"},
        {"name": "    Network Activity", "view": "network_activity", "group": "Network", "leaf": "Network Activity"},
        {"name": "    TCP Connections", "view": "network_tcp", "group": "Network", "leaf": "TCP Connections"},
        {"name": "    UDP Endpoints", "view": "network_udp", "group": "Network", "leaf": "UDP Endpoints"},
        {"name": "    Listening / Bound Ports", "view": "network_listen", "group": "Network", "leaf": "Listening / Bound Ports"},
    )

    def __init__(self, applet_dir=None):
        super().__init__(applet_dir)
        self.records = [dict(row) for row in self.VIEW_ROWS]
        self.loaded = True
        self.status = "Resource Monitor ready."
        self._active_view = None
        self._detail_text = {}

        self.proc_cache = {}
        self.prev_proc_io = {}
        self.prev_disk_io = {}
        self.prev_net_io = {}
        self.prev_major_faults = {}
        self.prev_service_cpu = {}
        self.cpu_averages = {}
        self.cpu_average_counts = {}

        self._cpu_rows = []
        self._selected_cpu_pid = None
        self._memory_rows = []
        self._selected_memory_pid = None
        self._memory_detail_cache = {"pid": None, "time": 0.0, "text": ""}
        self._vmstat_previous = {}
        self._vmstat_previous_time = None
        self._disk_active_rows = []
        self._service_cache = []
        self._service_cache_time = 0.0
        self._storage_partitions = []
        self._storage_cache_time = 0.0
        self._net_cache = []
        self._net_cache_time = 0.0

        # Preserve the approved 0.0.3 V behavior, now scoped to the explicit
        # Network Activity subview: Connections <-> Interfaces.
        self.net_activity_mode = "connections"
        self.memory_mode = "processes"
        self.privilege = PrivilegeClient()

    # ------------------------------------------------------------------
    # Lifecycle / host contract
    # ------------------------------------------------------------------
    def on_activate(self):
        self._reset_rate_baselines()
        self._active_view = None
        self.refresh()

    def on_deactivate(self):
        self._reset_rate_baselines()
        self.privilege.stop()

    def _reset_rate_baselines(self):
        self.prev_proc_io.clear()
        self.prev_disk_io.clear()
        self.prev_net_io.clear()
        self.prev_major_faults.clear()
        self.prev_service_cpu.clear()
        self._vmstat_previous = {}
        self._vmstat_previous_time = None
        self._net_cache = []
        self._net_cache_time = 0.0

    def action_label(self):
        return "Refresh"

    def extra_footer(self):
        extras = []
        view = self._selected_view()
        if view in ("cpu_processes", "cpu_handles", "cpu_modules"):
            extras.append("[</>] Select PID")
        if view == "memory":
            if self.memory_mode == "processes":
                extras.append("[</>] Select PID")
            extras.append("[v] Processes/Physical Memory")
        if view == "network_activity":
            extras.append("[v] Connections/Interfaces")
        state = "On" if self.privilege.enabled else (
            "Auth…" if self.privilege.state == "connecting" else
            "Error" if self.privilege.state == "error" else "Off"
        )
        extras.append(f"[p] Privileged: {state}")
        return " | ".join(extras)

    def metadata_heading(self):
        record = self._selected_record()
        if not record:
            return self.metadata_title
        leaf = record.get("leaf", "Resource Monitor")
        if record.get("view") == "memory":
            leaf = "Physical Memory" if self.memory_mode == "physical" else "Processes"
        if record.get("view") == "network_activity":
            suffix = "Interfaces" if self.net_activity_mode == "interfaces" else "Connections"
            leaf = f"{leaf} — {suffix}"
        return f" {record.get('group', '')} — {leaf} "

    def format_row(self, record, width):
        name = record.get("name", "")
        if record.get("view") == "memory":
            suffix = "Physical Memory" if self.memory_mode == "physical" else "Processes"
            name = f"Memory — {suffix}"
        return f" {name}"[:max(0, width)]

    def details(self, record):
        if psutil is None:
            return "psutil is required for Resource Monitor."
        if record is None:
            return self.status
        view = record.get("view", "cpu_processes")
        if view != self._active_view:
            self._active_view = view
            self._sample(view)
        return self._detail_text.get(view, self.status)

    def refresh(self):
        if psutil is None:
            self.status = "psutil is required for Resource Monitor."
            self._detail_text = {row["view"]: self.status for row in self.VIEW_ROWS}
            return
        view = self._selected_view()
        self._active_view = view
        self._sample(view)

    def tick(self):
        self.refresh()

    def handle_key(self, key):
        if key in (ord("p"), ord("P")):
            if self.privilege.enabled:
                self.privilege.stop()
                self.status = "Privileged mode disabled."
            else:
                _ok, msg = self.privilege.start_blocking()
                self.status = msg
            self._net_cache = []
            self._net_cache_time = 0.0
            self.refresh()
            return True

        view = self._selected_view()
        if view == "memory" and key in (ord("v"), ord("V")):
            self.memory_mode = "physical" if self.memory_mode == "processes" else "processes"
            self._vmstat_previous = {}
            self._vmstat_previous_time = None
            self.refresh()
            return True
        if view == "network_activity" and key in (ord("v"), ord("V")):
            self.net_activity_mode = "interfaces" if self.net_activity_mode == "connections" else "connections"
            self.prev_net_io.clear()
            self.refresh()
            return True

        if view == "memory" and self.memory_mode == "processes":
            if key in (ord("["), ord("{"), ord("<")):
                self._move_memory_selection(-1)
                self.refresh()
                return True
            if key in (ord("]"), ord("}"), ord(">")):
                self._move_memory_selection(1)
                self.refresh()
                return True

        if view in ("cpu_processes", "cpu_handles", "cpu_modules"):
            if key in (ord("["), ord("{"), ord("<")):
                self._move_cpu_selection(-1)
                self.refresh()
                return True
            if key in (ord("]"), ord("}"), ord(">")):
                self._move_cpu_selection(1)
                self.refresh()
                return True
        return False

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------
    def _selected_record(self):
        if not self.records:
            return None
        idx = max(0, min(self.current_row, len(self.records) - 1))
        return self.records[idx]

    def _selected_view(self):
        rec = self._selected_record()
        return rec.get("view", "cpu_processes") if rec else "cpu_processes"

    def _sample(self, view):
        dispatch = {
            "cpu_processes": self._sample_cpu_processes,
            "cpu_services": self._sample_cpu_services,
            "cpu_handles": self._sample_cpu_handles,
            "cpu_modules": self._sample_cpu_modules,
            "memory": self._sample_memory,
            "disk_processes": self._sample_disk_processes,
            "disk_activity": self._sample_disk_activity,
            "disk_devices": self._sample_disk_devices,
            "network_processes": self._sample_network_processes,
            "network_activity": self._sample_network_activity,
            "network_tcp": self._sample_tcp_connections,
            "network_udp": self._sample_udp_endpoints,
            "network_listen": self._sample_listening_ports,
        }
        dispatch.get(view, self._sample_cpu_processes)()

    def _active_processes(self):
        try:
            current_pids = set(psutil.pids())
        except (psutil.Error, OSError):
            return []
        for pid in set(self.proc_cache) - current_pids:
            self.proc_cache.pop(pid, None)
            self.prev_proc_io.pop(pid, None)
            self.prev_major_faults.pop(pid, None)
            self.cpu_averages.pop(pid, None)
            self.cpu_average_counts.pop(pid, None)
        active = []
        for pid in current_pids:
            proc = self.proc_cache.get(pid)
            if proc is None:
                try:
                    proc = psutil.Process(pid)
                    proc.cpu_percent()
                    self.proc_cache[pid] = proc
                except (psutil.Error, OSError):
                    continue
            try:
                if proc.is_running():
                    active.append((pid, proc))
            except (psutil.Error, OSError):
                continue
        return active

    @staticmethod
    def _format_bytes(value):
        value = float(value or 0)
        units = ("B", "KiB", "MiB", "GiB", "TiB")
        for unit in units[:-1]:
            if abs(value) < 1024.0:
                return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
            value /= 1024.0
        return f"{value:.2f} {units[-1]}"

    @classmethod
    def _format_rate(cls, value):
        return f"{cls._format_bytes(value)}/s"

    @staticmethod
    def _cell(value, width, right=False):
        text = str(value)
        if len(text) > width:
            text = text[:max(0, width - 1)] + ("…" if width else "")
        return text.rjust(width) if right else text.ljust(width)

    @classmethod
    def _table(cls, headers, rows, widths, right_aligned=()):
        right_aligned = set(right_aligned)
        def render(values):
            return " ".join(cls._cell(value, widths[i], i in right_aligned) for i, value in enumerate(values)).rstrip()
        lines = [render(headers), render(["-" * n for n in widths])]
        lines.extend(render(row) for row in rows)
        return lines

    @staticmethod
    def _endpoint(ip, port):
        if not ip:
            return ""
        ip = str(ip)
        if ":" in ip and not ip.startswith("["):
            return f"[{ip}]:{port}" if port else ip
        return f"{ip}:{port}" if port else ip

    # ------------------------------------------------------------------
    # CPU
    # ------------------------------------------------------------------
    def _collect_cpu_rows(self):
        rows = []
        for pid, proc in self._active_processes():
            try:
                with proc.oneshot():
                    name = proc.name() or "Unknown"
                    cpu = float(proc.cpu_percent())
                    threads = int(proc.num_threads())
                    status = proc.status()
                    try:
                        core = proc.cpu_num()
                    except (psutil.Error, AttributeError):
                        core = "—"
                count = self.cpu_average_counts.get(pid, 0) + 1
                old_avg = self.cpu_averages.get(pid, 0.0)
                avg = old_avg + (cpu - old_avg) / count
                self.cpu_average_counts[pid] = count
                self.cpu_averages[pid] = avg
                rows.append((name, pid, cpu, avg, threads, status, core))
            except (psutil.Error, OSError, AttributeError):
                continue
        rows.sort(key=lambda r: r[2], reverse=True)
        self._cpu_rows = rows
        live_pids = [r[1] for r in rows]
        if self._selected_cpu_pid not in live_pids:
            self._selected_cpu_pid = live_pids[0] if live_pids else None
        return rows

    def _move_cpu_selection(self, delta):
        rows = self._cpu_rows or self._collect_cpu_rows()
        pids = [r[1] for r in rows]
        if not pids:
            self._selected_cpu_pid = None
            return
        try:
            pos = pids.index(self._selected_cpu_pid)
        except ValueError:
            pos = 0
        self._selected_cpu_pid = pids[(pos + delta) % len(pids)]

    def _selected_process_label(self):
        pid = self._selected_cpu_pid
        if not pid:
            return "No process selected"
        try:
            name = self.proc_cache.get(pid).name() if pid in self.proc_cache else psutil.Process(pid).name()
        except (psutil.Error, OSError):
            name = "Unknown"
        return f"{name} (PID {pid})"

    def _sample_cpu_processes(self):
        rows = self._collect_cpu_rows()
        out = []
        for name, pid, cpu, avg, threads, status, core in rows[:120]:
            marker = ">" if pid == self._selected_cpu_pid else " "
            out.append((marker + name, pid, f"{cpu:.1f}%", f"{avg:.1f}%", threads, status, core))
        lines = [
            f"Processes: {len(rows)}  |  Selected: {self._selected_process_label()}",
            "Average CPU is measured since this monitor activation.",
            "",
        ]
        lines += self._table(
            ("Process", "PID", "CPU", "Avg", "Thr", "State", "Core"),
            out, (18, 6, 7, 7, 5, 10, 5), right_aligned=(1, 2, 3, 4, 6),
        )
        self.status = f"{len(rows)} CPU processes."
        self._detail_text["cpu_processes"] = "\n".join(lines)

    def _service_metadata(self):
        now = time.monotonic()
        if self._service_cache and now - self._service_cache_time < 5.0:
            return self._service_cache
        rows = []
        try:
            listed = subprocess.run(
                ["systemctl", "list-units", "--type=service", "--all", "--no-legend", "--no-pager", "--plain"],
                capture_output=True, text=True, timeout=2.5, check=False,
            )
            units = []
            base = {}
            for line in listed.stdout.splitlines():
                parts = line.split(None, 4)
                if len(parts) < 4:
                    continue
                unit, _load, active, sub = parts[:4]
                if not unit.endswith(".service"):
                    continue
                desc = parts[4] if len(parts) > 4 else ""
                units.append(unit)
                base[unit] = {"unit": unit, "active": active, "sub": sub, "desc": desc, "pid": 0, "cgroup": ""}
            units = units[:500]
            if units:
                shown = subprocess.run(
                    ["systemctl", "show", *units, "--property=Id", "--property=MainPID", "--property=ControlGroup", "--no-pager"],
                    capture_output=True, text=True, timeout=4.0, check=False,
                )
                current = None
                for line in shown.stdout.splitlines():
                    if line.startswith("Id="):
                        current = line[3:]
                    elif current and line.startswith("MainPID=") and current in base:
                        try:
                            base[current]["pid"] = int(line[8:] or 0)
                        except ValueError:
                            pass
                    elif current and line.startswith("ControlGroup=") and current in base:
                        base[current]["cgroup"] = line[13:]
            rows = [base[u] for u in units if u in base]
        except (OSError, subprocess.SubprocessError):
            rows = []
        self._service_cache = rows
        self._service_cache_time = now
        return rows

    @staticmethod
    def _cgroup_usage_usec(control_group):
        if not control_group:
            return None
        path = Path("/sys/fs/cgroup") / str(control_group).lstrip("/") / "cpu.stat"
        try:
            for line in path.read_text(errors="replace").splitlines():
                if line.startswith("usage_usec "):
                    return int(line.split()[1])
        except (OSError, ValueError, IndexError):
            return None
        return None

    def _sample_cpu_services(self):
        now = time.monotonic()
        rows = []
        for item in self._service_metadata():
            unit = item["unit"]
            usage = self._cgroup_usage_usec(item.get("cgroup"))
            cpu = 0.0
            if usage is not None:
                old = self.prev_service_cpu.get(unit)
                if old:
                    old_usage, old_t = old
                    dt = now - old_t
                    if dt > 0:
                        cpu = max(0.0, (usage - old_usage) / (dt * 1_000_000.0) * 100.0)
                self.prev_service_cpu[unit] = (usage, now)
            elif item.get("pid"):
                try:
                    cpu = psutil.Process(item["pid"]).cpu_percent(interval=None)
                except (psutil.Error, OSError):
                    pass
            rows.append((unit, item.get("pid") or "", cpu, item.get("active", ""), item.get("sub", ""), item.get("desc", "")))
        rows.sort(key=lambda r: (r[3] != "active", -r[2], r[0].casefold()))
        table_rows = [(u, pid, f"{cpu:.1f}%", active, sub, desc) for u, pid, cpu, active, sub, desc in rows[:160]]
        lines = ["systemd services; CPU is sampled from service cgroups when available.", ""]
        if not rows:
            lines += ["systemd/systemctl service data is unavailable on this system."]
        else:
            lines += self._table(
                ("Service", "PID", "CPU", "Active", "State", "Description"),
                table_rows, (24, 6, 7, 9, 10, 28), right_aligned=(1, 2),
            )
        self.status = f"{len(rows)} services."
        self._detail_text["cpu_services"] = "\n".join(lines)

    @staticmethod
    def _fd_type(target):
        target = str(target)
        if target.startswith("socket:["):
            return "socket"
        if target.startswith("pipe:["):
            return "pipe"
        if target.startswith("anon_inode:"):
            detail = target.split("[", 1)[-1].rstrip("]")
            return detail[:12] or "anon_inode"
        if target.startswith("/"):
            try:
                return "dir" if os.path.isdir(target.replace(" (deleted)", "")) else "file"
            except OSError:
                return "file"
        return "other"

    @staticmethod
    def _fd_flags(pid, fd):
        try:
            for line in Path(f"/proc/{pid}/fdinfo/{fd}").read_text(errors="replace").splitlines():
                if line.startswith("flags:"):
                    return line.split(":", 1)[1].strip()
        except OSError:
            pass
        return ""

    def _read_handles(self, pid):
        rows = None
        if self.privilege.enabled:
            response = self.privilege.request("process_handles", pid=pid, timeout=0.9)
            if response and response.get("ok"):
                rows = [
                    (r.get("fd", ""), r.get("type", "") or self._fd_type(r.get("target", "")), r.get("flags", ""), r.get("target", ""))
                    for r in response.get("rows", [])
                ]
        if rows is None:
            rows = []
            try:
                root = Path(f"/proc/{pid}/fd")
                for item in root.iterdir():
                    try:
                        target = os.readlink(item)
                    except OSError:
                        continue
                    rows.append((item.name, self._fd_type(target), self._fd_flags(pid, item.name), target))
            except OSError:
                return [("—", "", "", "Access denied — enable Privileged for expanded visibility")]
        rows.sort(key=lambda r: int(r[0]) if str(r[0]).isdigit() else 10**9)
        return rows

    def _read_modules(self, pid):
        rows = None
        if self.privilege.enabled:
            response = self.privilege.request("process_modules", pid=pid, timeout=0.9)
            if response and response.get("ok"):
                rows = [(r.get("path", ""), r.get("perms", ""), r.get("address", "")) for r in response.get("rows", [])]
        if rows is None:
            rows = []
            try:
                seen = set()
                for mm in psutil.Process(pid).memory_maps(grouped=False):
                    path = getattr(mm, "path", "")
                    if not path.startswith("/") or path in seen:
                        continue
                    seen.add(path)
                    rows.append((path, getattr(mm, "perms", ""), getattr(mm, "addr", "")))
            except (psutil.Error, OSError):
                return [("Access denied — enable Privileged for expanded visibility", "", "")]
        return rows

    def _sample_cpu_handles(self):
        if not self._selected_cpu_pid:
            self._collect_cpu_rows()
        pid = self._selected_cpu_pid
        if not pid:
            text = "No process is available to inspect."
        else:
            rows = self._read_handles(pid)
            text = "\n".join([
                f"Selected: {self._selected_process_label()}  |  Linux equivalent: open file descriptors",
                "",
                *self._table(("FD", "Type", "Flags", "Target / Path"), rows[:500], (6, 12, 10, 58), right_aligned=(0,)),
            ])
        self.status = f"Handles for PID {pid or '—'}."
        self._detail_text["cpu_handles"] = text

    def _sample_cpu_modules(self):
        if not self._selected_cpu_pid:
            self._collect_cpu_rows()
        pid = self._selected_cpu_pid
        if not pid:
            text = "No process is available to inspect."
        else:
            rows = self._read_modules(pid)
            text = "\n".join([
                f"Selected: {self._selected_process_label()}  |  ELF/shared mapped files",
                "",
                *self._table(("Mapped File", "Perms", "Address"), rows[:500], (55, 7, 19)),
            ])
        self.status = f"Modules for PID {pid or '—'}."
        self._detail_text["cpu_modules"] = text

    # ------------------------------------------------------------------
    # Memory
    # ------------------------------------------------------------------
    @staticmethod
    def _read_major_faults(pid):
        try:
            raw = Path(f"/proc/{pid}/stat").read_text(errors="replace")
            tail = raw[raw.rfind(")") + 2:].split()
            return int(tail[9])
        except (OSError, ValueError, IndexError):
            return None

    @staticmethod
    def _meminfo():
        data = {}
        try:
            for line in Path("/proc/meminfo").read_text(errors="replace").splitlines():
                key, _, rest = line.partition(":")
                parts = rest.strip().split()
                if not parts:
                    continue
                value = int(parts[0])
                if len(parts) > 1 and parts[1].lower() == "kb":
                    value *= 1024
                data[key] = value
        except (OSError, ValueError):
            pass
        return data

    @staticmethod
    def _vmstat():
        data = {}
        try:
            for line in Path("/proc/vmstat").read_text(errors="replace").splitlines():
                parts = line.split()
                if len(parts) == 2:
                    try:
                        data[parts[0]] = int(parts[1])
                    except ValueError:
                        continue
        except OSError:
            pass
        return data

    @staticmethod
    def _smaps_rollup(pid):
        data = {}
        try:
            lines = Path(f"/proc/{pid}/smaps_rollup").read_text(errors="replace").splitlines()[1:]
            for line in lines:
                key, sep, rest = line.partition(":")
                if not sep:
                    continue
                parts = rest.strip().split()
                if not parts:
                    continue
                value = int(parts[0])
                if len(parts) > 1 and parts[1].lower() == "kb":
                    value *= 1024
                data[key] = value
            return data, ""
        except (OSError, ValueError) as exc:
            return {}, str(exc)

    @staticmethod
    def _smaps_mappings(pid):
        mappings = []
        current = None
        try:
            with Path(f"/proc/{pid}/smaps").open("r", errors="replace") as handle:
                for raw in handle:
                    line = raw.rstrip("\n")
                    parts = line.split(None, 5)
                    is_header = len(parts) >= 5 and "-" in parts[0] and len(parts[1]) == 4 and parts[1][0] in "r-"
                    if is_header:
                        if current is not None:
                            mappings.append(current)
                        current = {
                            "address": parts[0], "perms": parts[1],
                            "path": parts[5] if len(parts) > 5 else "[anonymous]",
                            "Rss": 0, "Pss": 0, "Private_Clean": 0, "Private_Dirty": 0,
                            "Private_Hugetlb": 0, "Shared_Clean": 0, "Shared_Dirty": 0,
                            "Shared_Hugetlb": 0, "Swap": 0,
                        }
                        continue
                    if current is None:
                        continue
                    key, sep, rest = line.partition(":")
                    if not sep or key not in current:
                        continue
                    fields = rest.strip().split()
                    if not fields:
                        continue
                    try:
                        value = int(fields[0])
                    except ValueError:
                        continue
                    if len(fields) > 1 and fields[1].lower() == "kb":
                        value *= 1024
                    current[key] = value
            if current is not None:
                mappings.append(current)
            return mappings, ""
        except OSError as exc:
            return [], str(exc)

    def _helper_memory_summary(self, pid):
        if not self.privilege.enabled:
            return {}, "Privileged helper is not active."
        response = self.privilege.request("process_memory_summary", pid=pid, timeout=2.0)
        if response and response.get("ok") and isinstance(response.get("values"), dict):
            return dict(response.get("values", {})), ""
        return {}, self.privilege.message or "Privileged helper could not read selected-process memory summary."

    def _helper_memory_mappings(self, pid):
        if not self.privilege.enabled:
            return [], "Privileged helper is not active."
        response = self.privilege.request("process_memory_map", pid=pid, timeout=3.0)
        if response and response.get("ok") and isinstance(response.get("rows"), list):
            return list(response.get("rows", [])), ""
        return [], self.privilege.message or "Privileged helper could not read selected-process memory map."

    @staticmethod
    def _memory_access_message(error, helper_attempted=False):
        text = str(error or "").strip()
        restricted = "permission denied" in text.casefold() or "errno 13" in text.casefold()
        if restricted:
            return ("Restricted — privileged helper could not expand visibility." if helper_attempted
                    else "Restricted — enable Privileged for expanded visibility.")
        return f"Unavailable: {text}" if text else "Not reported"

    def _sample_memory(self):
        if self.memory_mode == "physical":
            self._sample_physical_memory()
        else:
            self._sample_memory_processes()

    def _collect_memory_rows(self):
        now = time.monotonic()
        basics = []
        for pid, proc in self._active_processes():
            try:
                with proc.oneshot():
                    name = proc.name() or "Unknown"
                    info = proc.memory_info()
                    rss = int(getattr(info, "rss", 0))
                    shared = int(getattr(info, "shared", 0))
                    vms = int(getattr(info, "vms", 0))
                if rss > 0:
                    basics.append((rss, name, pid, shared, vms, proc))
            except (psutil.Error, OSError, AttributeError):
                continue
        basics.sort(reverse=True, key=lambda r: r[0])
        rows = []
        for rss, name, pid, shared, vms, proc in basics[:80]:
            faults = self._read_major_faults(pid)
            rate = 0.0
            if faults is not None:
                old = self.prev_major_faults.get(pid)
                if old:
                    old_faults, old_t = old
                    dt = now - old_t
                    if dt > 0:
                        rate = max(0.0, (faults - old_faults) / dt)
                self.prev_major_faults[pid] = (faults, now)
            rows.append((name, pid, rate, rss, shared, vms))
        self._memory_rows = rows
        live_pids = [row[1] for row in rows]
        if self._selected_memory_pid not in live_pids:
            self._selected_memory_pid = live_pids[0] if live_pids else None
        return rows

    def _move_memory_selection(self, delta):
        rows = self._memory_rows or self._collect_memory_rows()
        pids = [row[1] for row in rows]
        if not pids:
            self._selected_memory_pid = None
            return
        try:
            pos = pids.index(self._selected_memory_pid)
        except ValueError:
            pos = 0
        self._selected_memory_pid = pids[(pos + delta) % len(pids)]
        self._memory_detail_cache = {"pid": None, "time": 0.0, "text": ""}

    def _selected_memory_detail(self):
        pid = self._selected_memory_pid
        if not pid:
            return "No process is available to inspect."
        now = time.monotonic()
        cache = self._memory_detail_cache
        if cache.get("pid") == pid and now - float(cache.get("time", 0.0)) < 5.0:
            return str(cache.get("text", ""))

        basic_rss = basic_shared = vms = 0
        selected_row = next((row for row in self._memory_rows if row[1] == pid), None)
        if selected_row is not None:
            _name, _pid, _maj, basic_rss, basic_shared, vms = selected_row
        try:
            proc = self.proc_cache.get(pid) or psutil.Process(pid)
            with proc.oneshot():
                name = proc.name() or "Unknown"
                info = proc.memory_info()
                vms = int(getattr(info, "vms", vms) or vms)
                basic_rss = int(getattr(info, "rss", basic_rss) or basic_rss)
                basic_shared = int(getattr(info, "shared", basic_shared) or basic_shared)
        except (psutil.Error, OSError, AttributeError):
            name = selected_row[0] if selected_row is not None else "Process"

        rollup, rollup_error = self._smaps_rollup(pid)
        mappings, mapping_error = self._smaps_mappings(pid)
        rollup_privileged = False
        mappings_privileged = False
        helper_attempted_rollup = False
        helper_attempted_mappings = False
        if rollup_error and self.privilege.enabled:
            helper_attempted_rollup = True
            helper_rollup, helper_error = self._helper_memory_summary(pid)
            if helper_rollup:
                rollup, rollup_error, rollup_privileged = helper_rollup, "", True
            elif helper_error:
                rollup_error = helper_error
        if mapping_error and self.privilege.enabled:
            helper_attempted_mappings = True
            helper_mappings, helper_error = self._helper_memory_mappings(pid)
            if helper_mappings:
                mappings, mapping_error, mappings_privileged = helper_mappings, "", True
            elif helper_error:
                mapping_error = helper_error
        rss = int(rollup.get("Rss", 0)) or basic_rss
        pss = int(rollup.get("Pss", 0))
        private = int(rollup.get("Private_Clean", 0)) + int(rollup.get("Private_Dirty", 0)) + int(rollup.get("Private_Hugetlb", 0))
        shared = int(rollup.get("Shared_Clean", 0)) + int(rollup.get("Shared_Dirty", 0)) + int(rollup.get("Shared_Hugetlb", 0))
        if not shared:
            shared = basic_shared
        anonymous = int(rollup.get("Anonymous", 0))
        swap = int(rollup.get("Swap", 0))
        if not rollup:
            try:
                full = (self.proc_cache.get(pid) or psutil.Process(pid)).memory_full_info()
                rss = int(getattr(full, "rss", 0) or 0)
                pss = int(getattr(full, "pss", 0) or 0)
                private = int(getattr(full, "uss", 0) or 0)
                shared = int(getattr(full, "shared", 0) or 0)
                swap = int(getattr(full, "swap", 0) or 0)
            except (psutil.Error, OSError, AttributeError):
                pass

        pss_reported = "Pss" in rollup or bool(pss)
        private_reported = any(key in rollup for key in ("Private_Clean", "Private_Dirty", "Private_Hugetlb")) or bool(private)
        shared_reported = any(key in rollup for key in ("Shared_Clean", "Shared_Dirty", "Shared_Hugetlb")) or bool(shared)
        anonymous_reported = "Anonymous" in rollup or bool(anonymous)
        swap_reported = "Swap" in rollup or not rollup_error
        lines = [
            "", f"Selected Process Memory: {name} (PID {pid})",
            "Detailed /proc/<pid>/smaps is read lazily for this selected process only.", "",
            f"Virtual Memory : {self._format_bytes(vms)}",
            f"RSS            : {self._format_bytes(rss)}",
            f"PSS            : {self._format_bytes(pss) if pss_reported else 'Not reported'}",
            f"Private / USS  : {self._format_bytes(private) if private_reported else 'Not reported'}",
            f"Shared         : {self._format_bytes(shared) if shared_reported else 'Not reported'}",
            f"Anonymous      : {self._format_bytes(anonymous) if anonymous_reported else 'Not reported'}",
            f"Swap           : {self._format_bytes(swap) if swap_reported else 'Not reported'}",
        ]
        if rollup_privileged:
            lines.append("Source         : Privileged helper (expanded read-only visibility)")
        if rollup_error:
            lines.append(f"smaps_rollup   : {self._memory_access_message(rollup_error, helper_attempted_rollup)}")
        lines += ["", "Memory Map" + (" [privileged helper]" if mappings_privileged else ""), "----------"]
        if mappings:
            map_rows = []
            for item in mappings:
                private_b = int(item.get("Private_Clean", 0)) + int(item.get("Private_Dirty", 0)) + int(item.get("Private_Hugetlb", 0))
                shared_b = int(item.get("Shared_Clean", 0)) + int(item.get("Shared_Dirty", 0)) + int(item.get("Shared_Hugetlb", 0))
                map_rows.append((
                    item.get("address", ""), item.get("perms", ""),
                    self._format_bytes(item.get("Rss", 0)), self._format_bytes(item.get("Pss", 0)),
                    self._format_bytes(private_b), self._format_bytes(shared_b),
                    self._format_bytes(item.get("Swap", 0)), item.get("path", "[anonymous]") or "[anonymous]",
                ))
            lines += self._table(("Address", "Perm", "RSS", "PSS", "Priv", "Shr", "Swap", "Mapping"), map_rows,
                                 (18, 4, 9, 9, 9, 9, 8, 32), right_aligned=(2, 3, 4, 5, 6))
        else:
            lines.append(self._memory_access_message(mapping_error, helper_attempted_mappings) if mapping_error else "No mappings reported")
        text = "\n".join(lines)
        self._memory_detail_cache = {"pid": pid, "time": now, "text": text}
        return text

    def _sample_memory_processes(self):
        rows = self._collect_memory_rows()
        table_rows = []
        for name, pid, maj, rss, shared, vms in rows:
            marker = ">" if pid == self._selected_memory_pid else " "
            table_rows.append((marker + name, pid, f"{maj:.1f}", self._format_bytes(rss), self._format_bytes(shared), self._format_bytes(vms)))
        lines = [
            f"Processes: {len(rows)}  |  Selected PID: {self._selected_memory_pid or '—'}",
            "Major Faults/s is the Linux hard-fault analogue; selected-process smaps details are lazy.", "",
        ]
        lines += self._table(("Process", "PID", "MajF/s", "RSS", "Shared", "VMS"), table_rows,
                             (18, 6, 7, 10, 10, 10), right_aligned=(1, 2, 3, 4, 5))
        lines.append(self._selected_memory_detail())
        self.status = f"{len(rows)} memory processes shown."
        self._detail_text["memory"] = "\n".join(lines)

    def _sample_physical_memory(self):
        m = self._meminfo()
        total = int(m.get("MemTotal", 0) or 0)
        available = int(m.get("MemAvailable", m.get("MemFree", 0)) or 0)
        used = max(0, total - available)
        swap_total = int(m.get("SwapTotal", 0) or 0)
        swap_used = max(0, swap_total - int(m.get("SwapFree", 0) or 0))
        divisor = total or 1

        lines = ["Physical Memory — Linux-native RAM composition and VM activity", ""]
        summary = [
            ("Total RAM", self._format_bytes(total), "100.0%" if total else "—"),
            ("In use (derived)", self._format_bytes(used), f"{used / divisor * 100:.1f}%" if total else "—"),
            ("Available", self._format_bytes(available), f"{available / divisor * 100:.1f}%" if total else "—"),
            ("Free", self._format_bytes(m.get("MemFree", 0)), f"{int(m.get('MemFree', 0) or 0) / divisor * 100:.1f}%" if total else "—"),
            ("Swap used", self._format_bytes(swap_used), f"{(swap_used / swap_total * 100):.1f}% swap" if swap_total else "—"),
            ("Swap total", self._format_bytes(swap_total), ""),
        ]
        lines += self._table(("Metric", "Value", "% / Note"), summary, (20, 14, 13))
        lines += ["", "Linux Memory Classes", "These kernel-reported counters may overlap; they are not expected to sum to Total RAM.", ""]
        class_defs = [
            ("Anonymous", "AnonPages"), ("Page Cache / Cached", "Cached"), ("Buffers", "Buffers"),
            ("Slab Reclaimable", "SReclaimable"), ("Slab Unreclaimable", "SUnreclaim"),
            ("Page Tables", "PageTables"), ("Kernel Stack", "KernelStack"), ("Shared Memory", "Shmem"),
            ("Dirty", "Dirty"), ("Writeback", "Writeback"), ("HugeTLB", "Hugetlb"),
        ]
        class_rows = []
        for label, key in class_defs:
            value = int(m.get(key, 0) or 0)
            class_rows.append((label, self._format_bytes(value), f"{value / divisor * 100:.2f}%" if total else "—"))
        lines += self._table(("Memory Class", "Amount", "% RAM"), class_rows, (22, 14, 9), right_aligned=(1, 2))

        now = time.monotonic()
        vm = self._vmstat()
        previous = self._vmstat_previous
        previous_time = self._vmstat_previous_time
        dt = (now - previous_time) if previous_time is not None else 0.0
        def total_for(data, prefix):
            return sum(int(value) for key, value in data.items() if key.startswith(prefix))
        metrics = [
            ("Page Faults", int(vm.get("pgfault", 0)), int(previous.get("pgfault", 0)), "events"),
            ("Major Faults", int(vm.get("pgmajfault", 0)), int(previous.get("pgmajfault", 0)), "events"),
            ("Swap In", int(vm.get("pswpin", 0)), int(previous.get("pswpin", 0)), "pages"),
            ("Swap Out", int(vm.get("pswpout", 0)), int(previous.get("pswpout", 0)), "pages"),
            ("Pages Scanned", total_for(vm, "pgscan_"), total_for(previous, "pgscan_"), "pages"),
            ("Pages Reclaimed", total_for(vm, "pgsteal_"), total_for(previous, "pgsteal_"), "pages"),
            ("OOM Kills", int(vm.get("oom_kill", 0)), int(previous.get("oom_kill", 0)), "events"),
        ]
        activity_rows = []
        for label, counter, old_counter, unit in metrics:
            rate = max(0.0, (counter - old_counter) / dt) if dt > 0 and previous else None
            activity_rows.append((label, f"{counter:,}", f"{rate:.1f} {unit}/s" if rate is not None else "baseline"))
        lines += ["", "Virtual Memory Activity", "Rates are derived from successive /proc/vmstat counters.", ""]
        lines += self._table(("Metric", "Counter", "Rate"), activity_rows, (20, 16, 18), right_aligned=(1,))
        self._vmstat_previous = vm
        self._vmstat_previous_time = now
        self.status = "Physical memory sampled."
        self._detail_text["memory"] = "\n".join(lines)

    # ------------------------------------------------------------------
    # Disk
    # ------------------------------------------------------------------
    def _collect_process_disk_rates(self):
        now = time.monotonic()
        rows = []
        for pid, proc in self._active_processes():
            try:
                io = proc.io_counters()
                read_b = int(getattr(io, "read_bytes", 0))
                write_b = int(getattr(io, "write_bytes", 0))
                rr = wr = 0.0
                old = self.prev_proc_io.get(pid)
                if old:
                    old_r, old_w, old_t = old
                    dt = now - old_t
                    if dt > 0:
                        rr = max(0.0, (read_b - old_r) / dt)
                        wr = max(0.0, (write_b - old_w) / dt)
                self.prev_proc_io[pid] = (read_b, write_b, now)
                total = rr + wr
                if total > 0:
                    rows.append((proc.name() or "Unknown", pid, rr, wr, total))
            except (psutil.Error, OSError, AttributeError):
                continue
        rows.sort(key=lambda r: r[4], reverse=True)
        self._disk_active_rows = rows
        return rows

    def _sample_disk_processes(self):
        rows = self._collect_process_disk_rates()
        table_rows = [(n, pid, self._format_rate(rr), self._format_rate(wr), self._format_rate(total)) for n, pid, rr, wr, total in rows]
        lines = [f"Processes with disk activity: {len(rows)}", ""]
        lines += self._table(
            ("Process", "PID", "Read/s", "Write/s", "Total I/O/s"),
            table_rows, (18, 6, 13, 13, 14), right_aligned=(1, 2, 3, 4),
        )
        if not rows:
            lines += ["", "No disk I/O delta was measured in this sample (or counters are warming up)."]
        self.status = f"{len(rows)} disk-active processes."
        self._detail_text["disk_processes"] = "\n".join(lines)

    def _associated_files_for_pid(self, pid, limit=5):
        paths = []
        seen = set()
        for _fd, _kind, _flags, target in self._read_handles(pid):
            target = str(target)
            clean = target.replace(" (deleted)", "")
            if not clean.startswith("/") or clean in seen:
                continue
            seen.add(clean)
            paths.append(target)
            if len(paths) >= limit:
                return paths
        # Mapped files are also useful associations (e.g. mmap-backed databases
        # and libraries). They are not claimed to be the source of the sampled I/O.
        for path, _perms, _addr in self._read_modules(pid):
            path = str(path)
            clean = path.replace(" (deleted)", "")
            if not clean.startswith("/") or clean in seen:
                continue
            seen.add(clean)
            paths.append(path)
            if len(paths) >= limit:
                break
        return paths

    def _sample_disk_activity(self):
        active = self._collect_process_disk_rates()
        rows = []
        for name, pid, _rr, _wr, total in active[:20]:
            paths = self._associated_files_for_pid(pid, limit=4)
            if not paths:
                rows.append((name, pid, "<no visible file descriptor>", self._format_rate(total)))
            else:
                for path in paths:
                    rows.append((name, pid, path, self._format_rate(total)))
        lines = [
            "Files associated with processes currently generating disk I/O.",
            "Important: I/O/s is the PROCESS aggregate, not a per-file byte rate.",
            "Linux procfs does not expose Windows-style per-file I/O rates without tracing/eBPF.", "",
        ]
        if rows:
            lines += self._table(("Process", "PID", "Open / Mapped File", "Proc I/O/s"), rows[:200], (16, 6, 52, 14), right_aligned=(1, 3))
        else:
            lines += ["No disk-active process/file associations are visible in this sample."]
        self.status = f"{len(rows)} associated file rows."
        self._detail_text["disk_activity"] = "\n".join(lines)

    @staticmethod
    def _sysfs_inflight(device):
        try:
            real = os.path.realpath(device)
            name = os.path.basename(real)
            fields = Path(f"/sys/class/block/{name}/stat").read_text().split()
            return int(fields[8]) if len(fields) > 8 else 0
        except (OSError, ValueError, IndexError):
            return 0

    def _device_rates(self):
        now = time.monotonic()
        out = {}
        try:
            counters = psutil.disk_io_counters(perdisk=True) or {}
        except (psutil.Error, OSError):
            counters = {}
        for dev, io in counters.items():
            read_b = int(getattr(io, "read_bytes", 0))
            write_b = int(getattr(io, "write_bytes", 0))
            read_c = int(getattr(io, "read_count", 0))
            write_c = int(getattr(io, "write_count", 0))
            busy = int(getattr(io, "busy_time", 0) or 0)
            rr = wr = iops = busy_pct = 0.0
            old = self.prev_disk_io.get(dev)
            if old:
                or_b, ow_b, or_c, ow_c, obusy, ot = old
                dt = now - ot
                if dt > 0:
                    rr = max(0.0, (read_b - or_b) / dt)
                    wr = max(0.0, (write_b - ow_b) / dt)
                    iops = max(0.0, ((read_c - or_c) + (write_c - ow_c)) / dt)
                    busy_pct = max(0.0, min(100.0, (busy - obusy) / (dt * 10.0)))
            self.prev_disk_io[dev] = (read_b, write_b, read_c, write_c, busy, now)
            out[dev] = (rr, wr, iops, busy_pct)
        return out

    def _partitions(self):
        now = time.monotonic()
        if self._storage_partitions and now - self._storage_cache_time < 10.0:
            return self._storage_partitions
        try:
            parts = list(psutil.disk_partitions(all=False))
        except (psutil.Error, OSError):
            parts = []
        self._storage_partitions = parts
        self._storage_cache_time = now
        return parts

    def _sample_disk_devices(self):
        rates = self._device_rates()
        rows = []
        for part in self._partitions():
            try:
                usage = psutil.disk_usage(part.mountpoint)
            except (psutil.Error, OSError):
                continue
            real = os.path.realpath(part.device)
            devname = os.path.basename(real)
            rr, wr, iops, busy = rates.get(devname, rates.get(os.path.basename(part.device), (0.0, 0.0, 0.0, 0.0)))
            rows.append((
                part.device, part.mountpoint, part.fstype,
                self._format_rate(rr), self._format_rate(wr), f"{iops:.1f}", f"{busy:.1f}%",
                self._sysfs_inflight(part.device), f"{usage.percent:.1f}%",
            ))
        lines = ["Mounted disk devices with kernel I/O deltas and filesystem space.", ""]
        lines += self._table(
            ("Device", "Mount", "FS", "Read/s", "Write/s", "IOPS", "Busy", "InFl", "Space"),
            rows, (16, 18, 8, 12, 12, 7, 7, 5, 7), right_aligned=(3, 4, 5, 6, 7, 8),
        )
        self.status = f"{len(rows)} disk-device rows."
        self._detail_text["disk_devices"] = "\n".join(lines)

    # ------------------------------------------------------------------
    # Network
    # ------------------------------------------------------------------
    def _conn_record(self, conn, pid):
        name = "System/Kernel"
        if pid:
            try:
                name = (self.proc_cache.get(pid) or psutil.Process(pid)).name()
            except (psutil.Error, OSError):
                name = "Access Denied"
        proto = "TCP" if getattr(conn, "type", None) == socket.SOCK_STREAM else "UDP"
        laddr = getattr(conn, "laddr", None)
        raddr = getattr(conn, "raddr", None)
        lip = getattr(laddr, "ip", "") if laddr else ""
        lport = getattr(laddr, "port", 0) if laddr else 0
        rip = getattr(raddr, "ip", "") if raddr else ""
        rport = getattr(raddr, "port", 0) if raddr else 0
        if isinstance(laddr, (tuple, list)) and len(laddr) >= 2:
            lip, lport = laddr[0], laddr[1]
        if isinstance(raddr, (tuple, list)) and len(raddr) >= 2:
            rip, rport = raddr[0], raddr[1]
        return {
            "pid": int(pid or 0), "name": name,
            "local_ip": lip, "local_port": int(lport or 0),
            "remote_ip": rip, "remote_port": int(rport or 0),
            "status": getattr(conn, "status", "NONE") or "NONE", "protocol": proto,
        }

    def _unprivileged_connections(self):
        rows = []
        try:
            conns = psutil.net_connections(kind="inet")
        except psutil.AccessDenied:
            conns = None
        except (psutil.Error, OSError):
            conns = []
        if conns is not None:
            for conn in conns:
                rows.append(self._conn_record(conn, getattr(conn, "pid", None) or 0))
            return rows
        for pid, proc in self._active_processes():
            try:
                getter = getattr(proc, "net_connections", None)
                items = getter(kind="inet") if getter else proc.connections(kind="inet")
                rows.extend(self._conn_record(conn, pid) for conn in items)
            except (psutil.Error, OSError):
                continue
        return rows

    @staticmethod
    def _normalise_remote(ip, port):
        ip = str(ip or "")
        port = int(port or 0)
        if port == 0 and ip in ("", "0.0.0.0", "::"):
            return "", 0
        return ip, port

    @classmethod
    def _connection_semantic_key(cls, row):
        remote_ip, remote_port = cls._normalise_remote(
            row.get("remote_ip"), row.get("remote_port")
        )
        return (
            str(row.get("protocol") or "").upper(),
            str(row.get("local_ip") or ""),
            int(row.get("local_port") or 0),
            remote_ip,
            remote_port,
            str(row.get("status") or "NONE").upper(),
        )

    @classmethod
    def _merge_connection_rows(cls, ordinary_rows, helper_rows):
        merged = []
        helper_buckets = defaultdict(list)
        for helper_row in helper_rows:
            row = dict(helper_row)
            row["_socket_inode"] = str(row.get("inode") or "")
            helper_buckets[cls._connection_semantic_key(row)].append(row)

        for ordinary_row in ordinary_rows:
            row = dict(ordinary_row)
            key = cls._connection_semantic_key(row)
            candidates = helper_buckets.get(key, [])
            ordinary_pid = int(row.get("pid") or 0)
            match_index = None
            for index, candidate in enumerate(candidates):
                helper_pid = int(candidate.get("pid") or 0)
                if ordinary_pid == helper_pid or not ordinary_pid or not helper_pid:
                    match_index = index
                    break
            if match_index is not None:
                helper_row = candidates.pop(match_index)
                if not candidates:
                    helper_buckets.pop(key, None)
                helper_pid = int(helper_row.get("pid") or 0)
                helper_name = str(helper_row.get("name") or "")
                ordinary_name = str(row.get("name") or "")
                if not ordinary_pid and helper_pid:
                    row["pid"] = helper_pid
                if helper_name and helper_name not in {"", "Unknown", "System/Kernel", "Access Denied"} and ordinary_name in {"", "Unknown", "System/Kernel", "Access Denied"}:
                    row["name"] = helper_name
                row["_socket_inode"] = str(helper_row.get("_socket_inode") or "")
            merged.append(row)

        for candidates in helper_buckets.values():
            merged.extend(candidates)
        return merged

    def _get_connections(self):
        now = time.monotonic()
        if self._net_cache and now - self._net_cache_time < 2.0:
            return list(self._net_cache)

        ordinary_rows = self._unprivileged_connections()
        rows = list(ordinary_rows)
        if self.privilege.enabled:
            response = self.privilege.request("net_connections", timeout=1.0)
            if response and response.get("ok"):
                rows = self._merge_connection_rows(ordinary_rows, list(response.get("rows", [])))

        self._net_cache = list(rows)
        self._net_cache_time = now
        return list(rows)

    def _sample_network_processes(self):
        connections = self._get_connections()
        grouped = defaultdict(lambda: {"name": "", "tcp": 0, "udp": 0, "remote": set(), "count": 0})
        for row in connections:
            pid = int(row.get("pid") or 0)
            if not pid:
                continue
            g = grouped[pid]
            g["name"] = row.get("name") or "Unknown"
            proto = str(row.get("protocol") or "").upper()
            g["tcp"] += int(proto == "TCP")
            g["udp"] += int(proto == "UDP")
            rip, rport = row.get("remote_ip") or "", int(row.get("remote_port") or 0)
            if rip and (rip not in ("0.0.0.0", "::") or rport):
                g["remote"].add((rip, rport))
            g["count"] += 1
        rows = [(g["name"], pid, g["tcp"], g["udp"], len(g["remote"]), g["count"]) for pid, g in grouped.items()]
        rows.sort(key=lambda r: (r[0].casefold(), r[1]))
        lines = [
            "Observed TCP/UDP socket ownership by process.",
            "Linux has no universal unprivileged per-process network byte counter; rates are not faked.", "",
        ]
        lines += self._table(("Process", "PID", "TCP", "UDP", "Remote", "Sockets"), rows, (20, 6, 6, 6, 8, 8), right_aligned=(1, 2, 3, 4, 5))
        self.status = f"{len(rows)} processes with network sockets."
        self._detail_text["network_processes"] = "\n".join(lines)

    def _sample_network_interfaces(self):
        now = time.monotonic()
        rows = []
        try:
            counters = psutil.net_io_counters(pernic=True) or {}
            for nic, io in counters.items():
                sent, recv = int(io.bytes_sent), int(io.bytes_recv)
                up = down = 0.0
                old = self.prev_net_io.get(nic)
                if old:
                    osent, orecv, ot = old
                    dt = now - ot
                    if dt > 0:
                        up = max(0.0, (sent - osent) / dt)
                        down = max(0.0, (recv - orecv) / dt)
                self.prev_net_io[nic] = (sent, recv, now)
                rows.append((nic, up, down, sent, recv))
        except (psutil.Error, OSError):
            pass
        rows.sort(key=lambda r: r[1] + r[2], reverse=True)
        table_rows = [(n, self._format_rate(up), self._format_rate(down), self._format_bytes(sent), self._format_bytes(recv)) for n, up, down, sent, recv in rows]
        lines = ["Linux interface counters (exact byte-rate deltas). Press V for connection activity.", ""]
        lines += self._table(("Interface", "Upload/s", "Download/s", "Uploaded", "Downloaded"), table_rows, (16, 13, 13, 13, 13), right_aligned=(1, 2, 3, 4))
        self.status = f"{len(rows)} network interfaces."
        self._detail_text["network_activity"] = "\n".join(lines)

    def _sample_network_activity(self):
        if self.net_activity_mode == "interfaces":
            self._sample_network_interfaces()
            return
        rows = []
        for row in self._get_connections():
            rip, rport = self._normalise_remote(
                row.get("remote_ip"), row.get("remote_port")
            )
            if not rip and not rport:
                continue
            rows.append((
                row.get("name") or "Unknown", int(row.get("pid") or 0),
                self._endpoint(row.get("local_ip") or "", int(row.get("local_port") or 0)),
                self._endpoint(rip, rport), row.get("protocol") or "", row.get("status") or "NONE",
            ))
        rows.sort(key=lambda r: (r[0].casefold(), r[1], r[2]))
        lines = ["Endpoint activity. Press V for the preserved Linux interface-rate view.", ""]
        lines += self._table(("Process", "PID", "Local", "Remote", "Proto", "State"), rows, (17, 6, 24, 24, 6, 12), right_aligned=(1,))
        self.status = f"{len(rows)} active endpoint rows."
        self._detail_text["network_activity"] = "\n".join(lines)

    def _sample_tcp_connections(self):
        rows = []
        for row in self._get_connections():
            if str(row.get("protocol") or "").upper() != "TCP":
                continue
            status = str(row.get("status") or "NONE")
            remote_ip, remote_port = self._normalise_remote(
                row.get("remote_ip"), row.get("remote_port")
            )
            remote = self._endpoint(remote_ip, remote_port)
            if status == "LISTEN" or not remote:
                continue
            rows.append((
                row.get("name") or "Unknown", int(row.get("pid") or 0),
                self._endpoint(row.get("local_ip") or "", int(row.get("local_port") or 0)),
                remote, status,
            ))
        rows.sort(key=lambda r: (r[0].casefold(), r[1], r[2]))
        lines = ["TCP connections with process ownership where Linux permissions allow it.", ""]
        lines += self._table(("Process", "PID", "Local Address", "Remote Address", "State"), rows, (18, 6, 25, 25, 13), right_aligned=(1,))
        self.status = f"{len(rows)} TCP connections."
        self._detail_text["network_tcp"] = "\n".join(lines)

    def _sample_udp_endpoints(self):
        rows = []
        for row in self._get_connections():
            if str(row.get("protocol") or "").upper() != "UDP":
                continue
            remote_ip, remote_port = self._normalise_remote(
                row.get("remote_ip"), row.get("remote_port")
            )
            remote = self._endpoint(remote_ip, remote_port)
            if not remote:
                continue
            rows.append((
                row.get("name") or "Unknown",
                int(row.get("pid") or 0),
                self._endpoint(row.get("local_ip") or "", int(row.get("local_port") or 0)),
                remote,
            ))
        rows.sort(key=lambda r: (r[0].casefold(), r[1], r[2], r[3]))
        lines = ["UDP sockets with a reported remote/default peer endpoint; UDP remains connectionless.", ""]
        lines += self._table(("Process", "PID", "Local Address", "Remote Endpoint"), rows, (18, 6, 28, 28), right_aligned=(1,))
        self.status = f"{len(rows)} UDP endpoint rows."
        self._detail_text["network_udp"] = "\n".join(lines)

    def _sample_listening_ports(self):
        rows = []
        for row in self._get_connections():
            proto = str(row.get("protocol") or "").upper()
            status = str(row.get("status") or "NONE")
            remote_ip, remote_port = self._normalise_remote(
                row.get("remote_ip"), row.get("remote_port")
            )
            remote = self._endpoint(remote_ip, remote_port)
            is_listener = status == "LISTEN" or (proto == "UDP" and not remote)
            if not is_listener:
                continue
            pid = int(row.get("pid") or 0)
            user = ""
            if pid:
                try:
                    user = (self.proc_cache.get(pid) or psutil.Process(pid)).username()
                except (psutil.Error, OSError):
                    user = "Access denied"
            rows.append((
                row.get("name") or "Unknown", pid,
                self._endpoint(row.get("local_ip") or "", int(row.get("local_port") or 0)),
                proto, status, user,
            ))
        rows.sort(key=lambda r: (r[0].casefold(), r[1], r[2]))
        lines = [
            "TCP listening ports plus locally bound/unconnected UDP sockets.",
            "No misleading yes/no firewall-status column is invented for nftables/firewalld policy.", "",
        ]
        lines += self._table(("Process", "PID", "Bind Address", "Proto", "State", "User"), rows, (18, 6, 28, 6, 11, 18), right_aligned=(1,))
        self.status = f"{len(rows)} listening/bound ports."
        self._detail_text["network_listen"] = "\n".join(lines)


def create_tui_applet(applet_dir=None):
    return ResourceMonitorTUI(applet_dir)
