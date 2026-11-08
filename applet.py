#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# LinSpectacles - Linux Inspection Suite / standalone Resource Monitor
# Copyright (C) 2026 brunonlinespace
# GPL-3.0-or-later

"""Resource Monitor GUI.

1.0.0 keeps the GUI process sampling/lifecycle semantics from the known-good
0.0.11-exp2-r7 Resource Monitor baseline and its movable-card Overview. Detailed
resource tabs remain user-movable with persistent order. Memory again has two
explicit views: Processes and Physical Memory. Processes gains lazy selected-process
Linux memory attribution/mappings, while Physical Memory gains deeper Linux-native
RAM composition and VM-activity reporting. Privileged mode remains in-place and
read-only: the active control and rows actually sourced through the trusted helper
use a distinctive amber provenance accent.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

try:
    import psutil
except ImportError:
    psutil = None

from PyQt6.QtCore import QEvent, QItemSelectionModel, QTimer, Qt, QUrl
from PyQt6.QtGui import QBrush, QColor, QFont, QFontDatabase, QKeySequence, QPixmap, QShortcut, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

try:
    from .privilege import (
        PrivilegeClient,
        HELPER_PATH,
        helper_status,
        helper_status_details,
        install_or_update_helper,
        remove_helper,
    )
except ImportError:  # standalone.py imports this module through the package root
    from privilege import (
        PrivilegeClient,
        HELPER_PATH,
        helper_status,
        helper_status_details,
        install_or_update_helper,
        remove_helper,
    )

APPLET_ID = "linspectacles-linux-resmon"
APPLET_NAME = "Resource Monitor"
APPLET_VERSION = "1.0.2"
APPLET_AUTHOR = "brunonlinespace"
APPLET_EDITOR = "brunonlinespace"
APPLET_PUBLISHER = "brunonlinespace"
APPLET_ORGANIZATION_ID = "linspectacles"
APPLET_ORGANIZATION_URL = "https://github.com/linspectacles/"
APPLET_REPOSITORY = "https://github.com/linspectacles/linux-resmon"

# Keep Resource Monitor's in-place privilege provenance aligned with the
# established SELinux privileged palette. The top-level active button uses the
# same QSS as SELinux Inspector; helper-derived data uses its amber value tone.
PRIVILEGED_ACCENT = "#d6a23d"
PRIVILEGED_ACCENT_LIGHT = "#f2d18b"
PRIVILEGED_DATA = "#e5bd70"
PRIVILEGED_DEEP = "#6a4b0c"
PRIVILEGE_ACTIVE_QSS = (
    "QPushButton { background: #6a4b0c; color: #fff4d2; "
    "border: 1px solid #d6a23d; border-radius: 4px; padding: 5px 10px; font-weight: 600; } "
    "QPushButton:hover { border-color: #f2c96d; }"
)


SOURCES_TEXT = """Resource Monitor is read-only. It combines psutil with fixed Linux interfaces and fixed systemd queries; it does not write to the inspected interfaces.

CPU / Processes
  psutil process inventory and process CPU counters.
  /proc/<pid>/fd for ordinary-user process handle visibility.
  psutil process memory maps for ordinary-user mapped module/file visibility.

CPU / Services
  systemctl list-units --type=service --all --no-legend --no-pager --plain
  systemctl show <units> --property=Id --property=MainPID --property=ControlGroup --no-pager
  /sys/fs/cgroup/<ControlGroup>/cpu.stat for whole-service usage_usec CPU deltas when reported.
  psutil process information for service MainPID fallback rows when cgroup CPU data is unavailable.

Memory / Processes
  psutil process memory information for the live process inventory.
  /proc/<pid>/smaps_rollup for selected-process RSS/PSS/private/shared/anonymous/swap attribution when readable.
  /proc/<pid>/smaps for the selected process memory-map inventory only; Resource Monitor does not scan smaps for every process.

Memory / Physical Memory
  /proc/meminfo for RAM/swap summary and Linux kernel memory classes.
  /proc/vmstat for cumulative VM activity counters and derived per-second deltas between Resource Monitor samples.
  Memory classes are Linux-native reported counters and may overlap; they are not presented as a partition that must sum to total RAM.

Disk
  psutil process I/O counters.
  psutil.disk_io_counters(perdisk=True)
  psutil.disk_partitions(all=False)
  psutil.disk_usage(<mount point>)
  /sys/class/block/<device>/stat for current in-flight I/O where reported.

Network
  psutil.net_io_counters(pernic=True)
  psutil.net_connections(kind="inet") for ordinary-user TCP/UDP socket visibility.

Optional privileged visibility
  /usr/libexec/linspectacles-linux-resmon-helper is a separately installed, root-owned helper.
  The GUI/TUI process itself is never elevated.
  The helper has only five fixed read-only operations: process file-descriptor targets, process mapped module/file paths, selected-process smaps_rollup, selected-process smaps, and system socket data.
  The memory operations accept only one validated PID and expose no arbitrary-file-read API.
  Network helper data comes from /proc/net/tcp, /proc/net/tcp6, /proc/net/udp, /proc/net/udp6 plus /proc/<pid>/fd socket-inode ownership.
  Network privilege is additive: ordinary-visible sockets remain visible; helper-only or ownership-enriched rows receive amber provenance.
  Installed helper integrity is checked against the packaged helper hash before it can be used.

Rate values
  Interval measurements are derived from successive counters. They describe activity observed between Resource Monitor refreshes rather than permanent device/process properties.
"""


# Overview Provider Architecture.
#
# The Overview never recalculates resource records itself. Each selectable
# Overview lens points to the canonical full-tab table + refresh path, then
# copies the resulting rows into an independent Overview presentation table.
# This keeps data semantics/fixes authoritative in one place while preserving
# independent Overview sorting, filtering, selection, scrolling and widths.
OVERVIEW_PROVIDER_OPTIONS = {
    "cpu": (
        {
            "id": "cpu_processes",
            "title": "CPU Processes",
            "source_table": "cpu_process_table",
            "refresh": "_refresh_cpu",
            "identity_columns": (1,),
        },
        {
            "id": "cpu_services",
            "title": "CPU Services",
            "source_table": "service_table",
            "refresh": "_refresh_services",
            "identity_columns": (0,),
        },
    ),
    "memory": (
        {
            "id": "memory_processes",
            "title": "Memory Processes",
            "source_table": "mem_process_table",
            "refresh": "_refresh_memory_processes",
            "identity_columns": (1,),
        },
        {
            "id": "physical_memory",
            "title": "Physical Memory",
            "source_table": "physical_summary_table",
            "refresh": "_refresh_physical_memory",
            "identity_columns": (0,),
        },
    ),
    "disk": (
        {
            "id": "disk_processes",
            "title": "Processes with Disk Activity",
            "source_table": "disk_process_table",
            "refresh": "_refresh_disk",
            "identity_columns": (1,),
        },
        {
            "id": "disk_activity",
            "title": "Disk Activity",
            "source_table": "disk_activity_table",
            "refresh": "_refresh_disk",
            "identity_columns": (1, 2),
        },
        {
            "id": "disk_devices",
            "title": "Disk Devices",
            "source_table": "disk_devices_table",
            "refresh": "_refresh_disk",
            "identity_columns": (0,),
        },
    ),
    "network": (
        {
            "id": "network_processes",
            "title": "Processes with Network Sockets",
            "source_table": "net_process_table",
            "refresh": "_refresh_network",
            "identity_columns": (1,),
        },
        {
            "id": "network_activity",
            "title": "Network Activity",
            "source_table": "net_activity_table",
            "refresh": "_refresh_network",
            "identity_columns": (0,),
        },
        {
            "id": "tcp_connections",
            "title": "TCP Connections",
            "source_table": "tcp_table",
            "refresh": "_refresh_network",
            "identity_columns": (1, 2, 3, 4, 5),
        },
        {
            "id": "udp_endpoints",
            "title": "UDP Endpoints",
            "source_table": "udp_table",
            "refresh": "_refresh_network",
            "identity_columns": (1, 2, 3),
        },
        {
            "id": "listening_bound_ports",
            "title": "Listening / Bound Ports",
            "source_table": "listen_table",
            "refresh": "_refresh_network",
            "identity_columns": (1, 2, 3, 4),
        },
    ),
}

OVERVIEW_PROVIDER_DEFAULTS = {
    "cpu": "cpu_processes",
    "disk": "disk_activity",
    "network": "tcp_connections",
    "memory": "memory_processes",
}


class NumericItem(QTableWidgetItem):
    def __init__(self, text: str, raw=0):
        super().__init__(text)
        self.raw = raw

    def __lt__(self, other):
        if isinstance(other, NumericItem):
            try:
                return self.raw < other.raw
            except Exception:
                pass
        return super().__lt__(other)


def format_bytes(value) -> str:
    value = float(value or 0)
    units = ("B", "KB", "MB", "GB", "TB", "PB")
    for unit in units:
        if abs(value) < 1024.0 or unit == units[-1]:
            if unit == "B":
                return f"{value:.0f} {unit}"
            if unit in ("KB", "MB"):
                return f"{value:.1f} {unit}"
            return f"{value:.2f} {unit}"
        value /= 1024.0
    return f"{value:.2f} PB"


def format_rate(value) -> str:
    return f"{format_bytes(value)}/s"


def parse_bytes_text(text) -> float:
    try:
        number, unit = str(text).strip().split()[:2]
        factor = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4, "PB": 1024**5}.get(unit.upper(), 1)
        return float(number) * factor
    except Exception:
        return 0.0


def format_addr(addr) -> str:
    if not addr:
        return ""
    try:
        if hasattr(addr, "ip") and hasattr(addr, "port"):
            return f"{addr.ip}:{addr.port}"
        if isinstance(addr, (tuple, list)) and len(addr) >= 2:
            return f"{addr[0]}:{addr[1]}"
    except Exception:
        pass
    return str(addr)


def _table(headers) -> QTableWidget:
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setAlternatingRowColors(False)
    table.setWordWrap(False)
    table.setTextElideMode(Qt.TextElideMode.ElideRight)
    table.setSortingEnabled(True)
    table.verticalHeader().setVisible(False)
    table.horizontalHeader().setStretchLastSection(True)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    return table


def _fill_table(
    table: QTableWidget,
    rows,
    numeric_cols=None,
    select_key_col=None,
    select_key=None,
    privileged_rows=None,
):
    numeric_cols = numeric_cols or {}
    privileged_rows = set(privileged_rows or ())
    table.setSortingEnabled(False)
    table.setRowCount(len(rows))
    privileged_brush = QBrush(QColor(PRIVILEGED_DATA)) if privileged_rows else None
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            if c in numeric_cols:
                raw = numeric_cols[c](value) if callable(numeric_cols[c]) else value
                item = NumericItem(str(value), raw)
            else:
                item = QTableWidgetItem(str(value))
            if privileged_brush is not None and r in privileged_rows:
                item.setForeground(privileged_brush)
                item.setToolTip("Visible through the active privileged read-only collector")
            table.setItem(r, c, item)
    # Apply provenance before re-enabling sorting so the decorated item objects
    # move with their rows instead of relying on post-sort row numbers.
    table.setSortingEnabled(True)
    if select_key_col is not None and select_key is not None:
        for r in range(table.rowCount()):
            item = table.item(r, select_key_col)
            if item and item.text() == str(select_key):
                table.selectRow(r)
                break


def _bind_filter(edit: QLineEdit, table: QTableWidget):
    def apply_filter(text=""):
        needle = str(text).strip().casefold()
        for row in range(table.rowCount()):
            match = not needle
            if needle:
                for col in range(table.columnCount()):
                    item = table.item(row, col)
                    if item and needle in item.text().casefold():
                        match = True
                        break
            table.setRowHidden(row, not match)
    edit.textChanged.connect(apply_filter)
    return apply_filter


def _panel(title: str, table: QTableWidget, filter_placeholder: str | None = None):
    box = QGroupBox(title)
    layout = QVBoxLayout(box)
    layout.setContentsMargins(8, 12, 8, 8)
    filt = None
    if filter_placeholder:
        filt = QLineEdit()
        filt.setPlaceholderText(filter_placeholder)
        layout.addWidget(filt)
        _bind_filter(filt, table)
    layout.addWidget(table, 1)
    return box, filt


def _options_metadata_font(serialized: str = "") -> QFont:
    if serialized:
        font = QFont()
        if font.fromString(str(serialized)):
            return font
    return QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)


def _font_qss(font: QFont) -> str:
    # Exact Journal Inspector metadata_font_qss implementation.
    family = font.family().replace("\\", "\\\\").replace('"', '\"')
    size = font.pointSizeF() if font.pointSizeF() > 0 else 10.0
    try:
        raw_weight = font.weight()
        weight = int(getattr(raw_weight, "value", raw_weight))
    except Exception:
        weight = 400
    style = "italic" if font.italic() else "normal"
    return (
        f'font-family: "{family}"; font-size: {size:g}pt; '
        f'font-weight: {weight}; font-style: {style};'
    )


class ResMonOptionsDialog(QDialog):
    """Focused LinSpectacles Options surface for Resource Monitor."""

    def __init__(self, owner, initial_tab=0):
        super().__init__(owner)
        self.owner = owner
        self.setWindowTitle("Options — Resource Monitor")
        self.resize(980, 720)

        root = QVBoxLayout(self)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)

        # Appearance — Resource Monitor-specific layout controls. Overview
        # presentation and both Overview-card / main-tab ordering persist in
        # the applet settings file. Lock Layout is deliberately off by default.
        appearance_page = QWidget()
        appearance_layout = QVBoxLayout(appearance_page)
        appearance_layout.setContentsMargins(12, 12, 12, 12)
        appearance_layout.setSpacing(10)

        appearance_heading = QLabel("Layout")
        appearance_heading_font = appearance_heading.font()
        appearance_heading_font.setBold(True)
        appearance_heading_font.setPointSize(max(appearance_heading_font.pointSize(), 11))
        appearance_heading.setFont(appearance_heading_font)
        appearance_layout.addWidget(appearance_heading)

        overview_row = QHBoxLayout()
        overview_label = QLabel("Overview layout:")
        self.overview_layout_combo = QComboBox()
        self.overview_layout_combo.addItems(["Quadrants", "Stripes"])
        self.overview_layout_combo.setCurrentText(
            "Quadrants" if owner._overview_layout_mode == "quadrants" else "Stripes"
        )
        overview_row.addWidget(overview_label)
        overview_row.addWidget(self.overview_layout_combo)
        overview_row.addStretch(1)
        appearance_layout.addLayout(overview_row)

        overview_content_heading = QLabel("Overview Content")
        overview_content_heading_font = overview_content_heading.font()
        overview_content_heading_font.setBold(True)
        appearance_layout.addWidget(overview_content_heading)

        overview_content_note = QLabel(
            "Choose the one self-contained full-tab view mirrored by each Overview card. "
            "Dependent detail panes are intentionally excluded. Card titles follow these selections."
        )
        overview_content_note.setWordWrap(True)
        appearance_layout.addWidget(overview_content_note)

        self.overview_content_combos = {}
        for resource, label in (
            ("cpu", "CPU card:"),
            ("disk", "Disk card:"),
            ("network", "Network card:"),
            ("memory", "Memory card:"),
        ):
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            combo = QComboBox()
            specs = OVERVIEW_PROVIDER_OPTIONS[resource]
            combo.addItems([spec["title"] for spec in specs])
            current_id = owner._overview_content.get(resource, OVERVIEW_PROVIDER_DEFAULTS[resource])
            current_title = next(
                (spec["title"] for spec in specs if spec["id"] == current_id),
                specs[0]["title"],
            )
            combo.setCurrentText(current_title)
            combo.currentTextChanged.connect(
                lambda selected, resource=resource:
                    self._overview_content_changed(resource, selected)
            )
            row.addWidget(combo)
            row.addStretch(1)
            appearance_layout.addLayout(row)
            self.overview_content_combos[resource] = combo

        self.lock_layout_checkbox = QCheckBox("Lock Layout")
        self.lock_layout_checkbox.setChecked(bool(owner._layout_locked))
        appearance_layout.addWidget(self.lock_layout_checkbox)

        appearance_note = QLabel(
            "When layout is unlocked, the Overview cards can be repositioned with their movement "
            "controls and the main Overview / CPU / Memory / Disk / Network tabs can be dragged into "
            "a new order. Both arrangements are saved automatically. In Quadrants mode, Left / Right "
            "controls are also available. Lock Layout freezes both the Overview arrangement and the "
            "main tab positions."
        )
        appearance_note.setWordWrap(True)
        appearance_layout.addWidget(appearance_note)
        appearance_layout.addStretch(1)
        self.tabs.addTab(appearance_page, "Appearance")

        self.overview_layout_combo.currentTextChanged.connect(self._overview_layout_changed)
        self.lock_layout_checkbox.toggled.connect(self._lock_layout_changed)
        self._sync_appearance_controls()

        # Helper — fixed helper management remains the second tab. Resource
        # Monitor keeps privileged data in-place; this page manages only the
        # fixed optional helper itself.
        helper_page = QWidget()
        helper_layout = QVBoxLayout(helper_page)
        helper_layout.setContentsMargins(12, 12, 12, 12)
        helper_layout.setSpacing(10)

        helper_heading = QLabel("Privileged Helper")
        helper_heading_font = helper_heading.font()
        helper_heading_font.setBold(True)
        helper_heading_font.setPointSize(max(helper_heading_font.pointSize(), 11))
        helper_heading.setFont(helper_heading_font)
        helper_layout.addWidget(helper_heading)

        helper_note = QLabel(
            "Resource Monitor is fully usable without privileged access. The optional helper is a "
            "separately installed, root-owned, read-only collector; Resource Monitor itself is never elevated. "
            "Install/update/repair and removal use PolicyKit only for the fixed helper path."
        )
        helper_note.setWordWrap(True)
        helper_layout.addWidget(helper_note)

        self.helper_status_label = QLabel()
        self.helper_status_label.setWordWrap(True)
        self.helper_status_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        helper_layout.addWidget(self.helper_status_label)

        self.helper_path_label = QLabel(f"System location: {HELPER_PATH}")
        self.helper_path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        helper_layout.addWidget(self.helper_path_label)

        self.helper_access_label = QLabel()
        self.helper_access_label.setWordWrap(True)
        helper_layout.addWidget(self.helper_access_label)

        helper_actions = QHBoxLayout()
        self.install_helper_button = QPushButton("Install or Update/Repair Helper...")
        self.install_helper_button.clicked.connect(self._install_or_update_helper)
        helper_actions.addWidget(self.install_helper_button)
        self.remove_helper_button = QPushButton("Remove Helper...")
        self.remove_helper_button.clicked.connect(self._remove_helper)
        helper_actions.addWidget(self.remove_helper_button)
        helper_actions.addStretch(1)
        helper_layout.addLayout(helper_actions)
        helper_layout.addStretch(1)
        self.tabs.addTab(helper_page, "Helper")

        sources_page = QWidget()
        sl = QVBoxLayout(sources_page)
        sl.setContentsMargins(12, 12, 12, 12); sl.setSpacing(10)
        h = QLabel("Data Sources")
        f = h.font(); f.setBold(True); f.setPointSize(max(f.pointSize(), 11)); h.setFont(f); sl.addWidget(h)
        n = QLabel("Commands and system interfaces used by this read-only Resource Monitor.")
        n.setWordWrap(True); sl.addWidget(n)
        t = QTextEdit(); t.setReadOnly(True)
        chosen = _options_metadata_font(getattr(owner, "_serialized_metadata_font", "")); font_rule = ""
        if chosen is not None:
            t.setFont(chosen); t.document().setDefaultFont(chosen); t.setCurrentFont(chosen)
            font_rule = _font_qss(chosen)
        t.setStyleSheet(
            "QTextEdit { "
            + font_rule
            + " background-color: #151719; color: #dcdcdc; "
              "border: 1px solid #333333; }"
        )

        source_key_format = QTextCharFormat()
        source_key_format.setForeground(QColor("#9cdcfe"))
        source_key_format.setFontWeight(600)
        source_value_format = QTextCharFormat()
        source_value_format.setForeground(QColor("#dcdcdc"))

        cursor = t.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        for line in SOURCES_TEXT.splitlines():
            if line and not line[:1].isspace():
                cursor.insertText(line + "\n", source_key_format)
            else:
                cursor.insertText(line + "\n", source_value_format)
        t.setTextCursor(cursor)
        t.moveCursor(QTextCursor.MoveOperation.Start)
        sl.addWidget(t, 1)
        self.tabs.addTab(sources_page, "Sources")

        # About — standard LinSpectacles applet composition.
        about_page = QWidget()
        about_layout = QVBoxLayout(about_page)
        about_layout.setContentsMargins(24, 20, 24, 18)
        about_layout.setSpacing(8)

        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setFixedSize(112, 112)
        icon_path = Path(__file__).resolve().parent / "icon.png"
        if icon_path.is_file():
            pixmap = QPixmap(str(icon_path))
            if not pixmap.isNull():
                icon_label.setPixmap(
                    pixmap.scaled(
                        112,
                        112,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
        about_layout.addWidget(icon_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        name = QLabel("<h2 style='margin:0'>Resource Monitor</h2>")
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        about_layout.addWidget(name)

        version = QLabel(f"Version {APPLET_VERSION}")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        about_layout.addWidget(version)

        slogan = QLabel("<b>Expose. Explore. Explain.</b>")
        slogan.setAlignment(Qt.AlignmentFlag.AlignCenter)
        about_layout.addWidget(slogan)

        description = QLabel(
            "A read-only live LinSpectacles resource monitor for CPU, memory, disk and network activity, "
            "with optional narrowly-scoped privileged visibility kept inside the same monitor."
        )
        description.setWordWrap(True)
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        about_layout.addWidget(description)

        details = QLabel(
            "<b>Build:</b> Standalone LinSpectacles applet<br>"
            "<b>Organisation ID:</b> "
            f"<a href='{APPLET_ORGANIZATION_URL}'>{APPLET_ORGANIZATION_ID}</a><br>"
            f"<b>Applet ID:</b> {APPLET_ID}"
        )
        details.setWordWrap(True)
        details.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        details.setAlignment(Qt.AlignmentFlag.AlignCenter)
        about_layout.addWidget(details)

        copyright_label = QLabel(
            "Copyright © 2026 "
            "<a href='https://github.com/brunonlinespace'>brunonlinespace</a>"
        )
        copyright_label.setOpenExternalLinks(True)
        copyright_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        about_layout.addWidget(copyright_label)

        license_label = QLabel("Licensed under GNU GPLv3 or later.")
        license_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        about_layout.addWidget(license_label)

        license_url = QUrl.fromLocalFile(str(Path(__file__).resolve().parent / "LICENSE")).toString()
        links = QLabel(
            f"<a href='{APPLET_REPOSITORY}'>GitHub Repository</a> "
            "&nbsp;·&nbsp; "
            f"<a href='{license_url}'>License</a>"
        )
        links.setOpenExternalLinks(True)
        links.setAlignment(Qt.AlignmentFlag.AlignCenter)
        about_layout.addWidget(links)
        about_layout.addStretch(1)
        self.tabs.addTab(about_page, "About")

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self.tabs.setCurrentIndex(max(0, min(int(initial_tab), self.tabs.count() - 1)))
        self._refresh_helper_ui()

    def _sync_appearance_controls(self):
        locked = bool(self.owner._layout_locked)
        self.overview_layout_combo.setEnabled(not locked)

    def _overview_layout_changed(self, text):
        # User-facing names are Quadrants / Stripes. The existing internal
        # values remain "quadrants" / "lines" for backward-compatible settings.
        mode = "quadrants" if str(text).strip().casefold() == "quadrants" else "lines"
        self.owner.set_overview_layout_mode(mode)

    def _overview_content_changed(self, resource, title):
        specs = OVERVIEW_PROVIDER_OPTIONS.get(resource, ())
        provider_id = next(
            (spec["id"] for spec in specs if spec["title"] == str(title)),
            None,
        )
        if provider_id:
            self.owner.set_overview_content(resource, provider_id)

    def _lock_layout_changed(self, checked):
        self.owner.set_layout_locked(bool(checked))
        self._sync_appearance_controls()

    def _refresh_helper_ui(self):
        details = helper_status_details()
        state = str(details.get("state") or "unknown")
        state_text = {
            "ready": "Installed and ready",
            "not_installed": "Not installed",
            "outdated": "Update or repair required",
            "invalid": "Installed helper is not trusted/usable",
        }.get(state, state.replace("_", " ").title())
        self.helper_status_label.setText(
            f"Status: {state_text}\n{details.get('message', '')}\n"
            f"Required helper version: {details.get('required_version', 'unknown')}"
        )

        active = bool(self.owner.privilege.enabled or self.owner.privilege.state == "connecting")
        self.install_helper_button.setEnabled(not active)
        self.remove_helper_button.setEnabled(bool(details.get("installed")) and not active)

        if self.owner.privilege.enabled:
            self.helper_access_label.setText("Privileged session: Active — helper management is disabled until the session ends.")
        elif self.owner.privilege.state == "connecting":
            self.helper_access_label.setText("Privileged session: Authorizing… — helper management is temporarily disabled.")
        else:
            available, why = self.owner.privilege.availability()
            self.helper_access_label.setText(
                "Privileged access: Ready" if available else f"Privileged access: Unavailable — {why}"
            )

    def _install_or_update_helper(self):
        answer = QMessageBox.question(
            self,
            "Resource Monitor Privileged Helper",
            "Install, update, or repair the optional root-owned Resource Monitor helper?\n\n"
            "PolicyKit will request administrator authorization. The helper exposes only fixed read-only "
            "process-handle, mapped-module/file, selected-process memory, and system-socket queries; Resource Monitor itself is not elevated.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.install_helper_button.setEnabled(False)
        QApplication.processEvents()
        ok, message = install_or_update_helper()
        (QMessageBox.information if ok else QMessageBox.warning)(
            self, "Resource Monitor Privileged Helper", message
        )
        self.owner._update_privilege_ui()
        self._refresh_helper_ui()

    def _remove_helper(self):
        answer = QMessageBox.question(
            self,
            "Remove Resource Monitor Privileged Helper",
            "Remove the optional root-owned Resource Monitor helper?\n\n"
            "Resource Monitor will continue to work with ordinary-user visibility. PolicyKit will request "
            "administrator authorization for removal.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        ok, message = remove_helper()
        (QMessageBox.information if ok else QMessageBox.warning)(
            self, "Resource Monitor Privileged Helper", message
        )
        self.owner._update_privilege_ui()
        self._refresh_helper_ui()


class ResMonWidget(QWidget):
    """Embedded/standalone GUI Resource Monitor."""

    def __init__(self, parent=None, start_active=False):
        super().__init__(parent)
        self.proc_cache = {}
        self.prev_proc_io = {}
        self.prev_disk_io = {}
        self.prev_net_io = {}
        self.prev_service_cpu = {}
        self.privilege = PrivilegeClient()
        self._last_priv_state = self.privilege.state
        self._serialized_metadata_font = ""
        self._service_cache = []
        self._service_cache_time = 0.0
        self._net_cache = []
        self._net_cache_time = 0.0
        self._selected_cpu_pid = None
        self._selected_service_unit = None
        self._selected_disk_device = None
        self._selected_memory_pid = None
        self._selected_network_interface = None
        self._selected_network_process_pid = None
        self._selected_tcp_socket = None
        self._selected_udp_socket = None
        self._selected_listen_socket = None
        self._memory_detail_pid = None
        self._memory_detail_time = 0.0
        self._vmstat_previous = {}
        self._vmstat_previous_time = None

        settings = self._load_settings()
        self._layout_locked = bool(settings.get("lock_layout", False))
        self._overview_layout_mode = (
            "quadrants" if str(settings.get("overview_layout", "lines")).casefold() == "quadrants" else "lines"
        )
        default_overview_order = ["cpu", "disk", "network", "memory"]
        saved_overview_order = settings.get("overview_order", [])
        if isinstance(saved_overview_order, list):
            overview_order = [key for key in saved_overview_order if key in default_overview_order]
        else:
            overview_order = []
        overview_order.extend(key for key in default_overview_order if key not in overview_order)
        self._overview_order = overview_order

        saved_overview_content = settings.get("overview_content", {})
        if not isinstance(saved_overview_content, dict):
            saved_overview_content = {}
        self._overview_content = {}
        for resource, default_id in OVERVIEW_PROVIDER_DEFAULTS.items():
            valid_ids = {spec["id"] for spec in OVERVIEW_PROVIDER_OPTIONS[resource]}
            saved_id = str(saved_overview_content.get(resource, default_id))
            self._overview_content[resource] = saved_id if saved_id in valid_ids else default_id

        self.ov_move_buttons = {}

        saved_column_widths = settings.get("column_widths", {})
        self._column_widths = saved_column_widths if isinstance(saved_column_widths, dict) else {}
        saved_table_sorts = settings.get("table_sorts", {})
        self._table_sorts = saved_table_sorts if isinstance(saved_table_sorts, dict) else {}
        saved_splitter_sizes = settings.get("splitter_sizes", {})
        self._splitter_sizes = saved_splitter_sizes if isinstance(saved_splitter_sizes, dict) else {}
        self._restoring_presentation_state = False
        self._auto_filling_last_column = False
        self._last_column_fill_viewports = {}
        self._splitter_persistence_ready = False
        self._presentation_state_save_timer = QTimer(self)
        self._presentation_state_save_timer.setSingleShot(True)
        self._presentation_state_save_timer.setInterval(350)
        self._presentation_state_save_timer.timeout.connect(self._flush_presentation_state)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        top = QHBoxLayout()
        title = QLabel("Resource Monitor")
        font = title.font()
        font.setBold(True)
        font.setPointSize(max(11, font.pointSize()))
        title.setFont(font)
        top.addWidget(title)
        top.addStretch(1)
        self.priv_button = QPushButton("Privileged: Off")
        self.priv_button.setCheckable(False)
        self.priv_button.clicked.connect(self.toggle_privileged)
        top.addWidget(self.priv_button)
        self.options_button = QPushButton("Options...")
        self.options_button.clicked.connect(self.show_options)
        top.addWidget(self.options_button)
        root.addLayout(top)

        self.tabs = QTabWidget()
        self.tabs.setMovable(not self._layout_locked)
        root.addWidget(self.tabs, 1)

        # Kernel Ring Buffer authority: privilege/lifecycle prose belongs in a
        # plain bottom status surface, not beside the top-right controls.
        self.priv_status = QLabel("Normal user visibility")
        status_font = self.priv_status.font()
        status_font.setItalic(True)
        self.priv_status.setFont(status_font)
        self.priv_status.setContentsMargins(4, 4, 4, 4)
        self.priv_status.setToolTip(
            "Resource Monitor remains read-only. Privileged mode only expands visibility where Linux permissions restrict it."
        )
        root.addWidget(self.priv_status)

        self._setup_navigation()
        self._setup_cpu_tab()
        self._setup_memory_tab()
        self._setup_disk_tab()
        self._setup_network_tab()
        self._setup_overview_tab()
        self._apply_stabilization_default_sorts()
        self._setup_table_state_persistence()
        self._setup_splitter_size_persistence()
        self._setup_keyboard_navigation_stabilization()
        self._restore_tab_order()
        self.tabs.tabBar().tabMoved.connect(self._tab_moved)
        self.tabs.currentChanged.connect(self._tab_changed)
        self._sync_view_combo()
        self._setup_shortcuts()

        if psutil is None:
            self.priv_button.setEnabled(False)
            self.priv_status.setText("psutil is required")
        else:
            self._active_processes()  # prime per-process CPU counters

        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.refresh_data)
        if start_active:
            self.set_monitoring_active(True)
        else:
            self._update_privilege_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _setup_navigation(self):
        self._view_options = {
            "cpu": ["Processes", "Services"],
            "memory": ["Processes", "Physical Memory"],
            "disk": ["Processes with Disk Activity", "Disk Activity", "Disk Devices"],
            "network": ["Processes with Network Sockets", "Network Activity", "TCP Connections", "UDP Endpoints", "Listening / Bound Ports"],
        }
        self._view_index = {"cpu": 0, "memory": 0, "disk": 0, "network": 0}

        self.view_corner = QWidget()
        corner_layout = QHBoxLayout(self.view_corner)
        corner_layout.setContentsMargins(6, 0, 0, 0)
        corner_layout.setSpacing(6)
        self.view_label = QLabel("View:")
        self.view_combo = QComboBox()
        self.view_combo.setMinimumContentsLength(22)
        corner_layout.addWidget(self.view_label)
        corner_layout.addWidget(self.view_combo)
        self.tabs.setCornerWidget(self.view_corner, Qt.Corner.TopRightCorner)
        self.view_combo.currentIndexChanged.connect(self._view_changed)

    def _tab_key_at(self, index=None):
        if index is None:
            index = self.tabs.currentIndex()
        page = self.tabs.widget(index) if 0 <= index < self.tabs.count() else None
        return page.property("linux_resmon_tab_key") if page is not None else None

    def _add_resource_tab(self, page, label, key):
        page.setProperty("linux_resmon_tab_key", key)
        self.tabs.addTab(page, label)

    @staticmethod
    def _settings_path():
        root = Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config"))
        return root / "brunonlinespace" / "linspectacles" / "linux_resmon.json"

    def _load_settings(self):
        path = self._settings_path()
        if not path.is_file():
            root = Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config"))
            legacy = root / "brunonlinespace" / "linspector" / "linux_resmon.json"
            if legacy.is_file():
                path = legacy
        try:
            import json
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError, TypeError):
            return {}

    def _write_settings(self, updates):
        path = self._settings_path()
        try:
            import json
            data = self._load_settings()
            data["schema"] = 6
            data.update(dict(updates or {}))
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            os.replace(tmp, path)
        except OSError:
            pass

    def _save_tab_order(self):
        self._write_settings({
            "tab_order": [self._tab_key_at(i) for i in range(self.tabs.count())],
        })

    def _save_overview_settings(self):
        self._write_settings({
            "overview_layout": self._overview_layout_mode,
            "overview_order": list(self._overview_order),
            "overview_content": dict(self._overview_content),
            "lock_layout": bool(self._layout_locked),
            "splitter_sizes": dict(self._splitter_sizes),
        })

    def _table_persistence_map(self):
        """Stable presentation-state keys for every current GUI table."""
        names = (
            "cpu_process_table", "service_table", "handle_table", "module_table",
            "mem_process_table", "memory_summary_table", "memory_map_table",
            "physical_summary_table", "memory_class_table", "vm_activity_table",
            "disk_process_table", "disk_activity_table", "disk_devices_table",
            "net_process_table", "net_activity_table", "tcp_table", "udp_table",
            "listen_table",
        )
        result = {
            name: getattr(self, name)
            for name in names
            if hasattr(self, name) and isinstance(getattr(self, name), QTableWidget)
        }
        for resource, tables in getattr(self, "ov_tables", {}).items():
            for provider_id, table in tables.items():
                if isinstance(table, QTableWidget):
                    result[f"overview_{resource}_{provider_id}"] = table
        return result

    @staticmethod
    def _last_visible_logical_section(table):
        """Return the logical index of the right-most visible header section."""
        header = table.horizontalHeader()
        visible = [
            logical for logical in range(table.columnCount())
            if not header.isSectionHidden(logical)
        ]
        if not visible:
            return None
        return max(visible, key=lambda logical: header.visualIndex(logical))

    def _preferred_widths_for_table(self, key, table):
        widths = self._column_widths.get(key)
        if not isinstance(widths, list) or len(widths) < table.columnCount():
            widths = [
                max(40, int(table.columnWidth(logical)))
                for logical in range(table.columnCount())
            ]
            self._column_widths[key] = list(widths)
        else:
            cleaned = []
            for logical in range(table.columnCount()):
                try:
                    width = int(widths[logical])
                except (TypeError, ValueError, IndexError):
                    width = int(table.columnWidth(logical))
                cleaned.append(max(40, width))
            widths = cleaned
            self._column_widths[key] = list(widths)
        return list(widths)

    def _apply_last_visible_column_fill(self, key, table):
        """Keep preferred widths, expanding only the last visible column into spare space."""
        if self._restoring_presentation_state or self._auto_filling_last_column:
            return
        if table.columnCount() <= 0:
            return

        header = table.horizontalHeader()
        last = self._last_visible_logical_section(table)
        if last is None:
            return
        preferred = self._preferred_widths_for_table(key, table)
        visible = [
            logical for logical in range(table.columnCount())
            if not header.isSectionHidden(logical)
        ]
        available = max(0, int(table.viewport().width()))

        # First-use Overview authority: when the user has no saved widths for
        # this particular Overview provider, start with equal preferred widths.
        # Wait until the table is actually visible so its viewport width is
        # meaningful. These become ordinary persisted preferred widths and are
        # freely user-resizable afterwards.
        pending = getattr(self, "_overview_equal_width_pending", set())
        if (
            key in pending
            and table.isVisible()
            and available > 0
            and visible
        ):
            equal_width = max(40, available // len(visible))
            for logical in visible:
                preferred[logical] = equal_width
            self._column_widths[key] = list(preferred)
            pending.discard(key)
            self._presentation_state_save_timer.start()

        other_total = sum(preferred[logical] for logical in visible if logical != last)
        desired_last = max(preferred[last], available - other_total)

        self._auto_filling_last_column = True
        try:
            # Reset every visible section to its persisted preferred width first.
            # This matters if a formerly-last section was auto-expanded and later
            # ceases to be the right-most visible section.
            for logical in visible:
                desired = desired_last if logical == last else preferred[logical]
                if int(table.columnWidth(logical)) != int(desired):
                    table.setColumnWidth(logical, int(desired))
        finally:
            self._auto_filling_last_column = False

    def _schedule_last_visible_column_fill(self, key, table):
        QTimer.singleShot(0, lambda key=key, table=table: self._apply_last_visible_column_fill(key, table))

    def _setup_table_state_persistence(self):
        """Restore/persist preferred widths + sort state for every table."""
        self._overview_equal_width_pending = set()
        self._restoring_presentation_state = True
        try:
            for key, table in self._table_persistence_map().items():
                header = table.horizontalHeader()

                # Every section remains Interactive. Persisted widths are the
                # user's preferred widths; automatic fill never overwrites them.
                existing_widths = [
                    max(40, int(table.columnWidth(section)))
                    for section in range(table.columnCount())
                ]
                header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
                header.setStretchLastSection(False)

                saved_widths = self._column_widths.get(key)
                restored_widths = (
                    isinstance(saved_widths, list)
                    and len(saved_widths) >= table.columnCount()
                )
                if key.startswith("overview_") and not restored_widths:
                    self._overview_equal_width_pending.add(key)
                if restored_widths:
                    preferred = []
                    for section, saved in enumerate(saved_widths[:table.columnCount()]):
                        try:
                            width = int(saved)
                        except (TypeError, ValueError):
                            width = existing_widths[section]
                        preferred.append(max(40, width))
                else:
                    preferred = list(existing_widths)
                self._column_widths[key] = list(preferred)
                for section, width in enumerate(preferred):
                    table.setColumnWidth(section, width)

                saved_sort = self._table_sorts.get(key)
                if isinstance(saved_sort, dict):
                    try:
                        column = int(saved_sort.get("column", -1))
                    except (TypeError, ValueError):
                        column = -1
                    order_text = str(saved_sort.get("order", "asc")).casefold()
                    if 0 <= column < table.columnCount():
                        order = (
                            Qt.SortOrder.DescendingOrder
                            if order_text == "desc"
                            else Qt.SortOrder.AscendingOrder
                        )
                        table.sortItems(column, order)

                header.sectionResized.connect(
                    lambda logical, _old, new, key=key, table=table:
                        self._table_column_size_changed(key, table, logical, new)
                )
                header.sectionMoved.connect(
                    lambda _logical, _old_visual, _new_visual, key=key, table=table:
                        self._schedule_last_visible_column_fill(key, table)
                )
                header.sortIndicatorChanged.connect(
                    lambda logical, order, key=key:
                        self._table_sort_changed(key, logical, order)
                )

                viewport = table.viewport()
                self._last_column_fill_viewports[viewport] = (key, table)
                viewport.installEventFilter(self)
        finally:
            self._restoring_presentation_state = False

        for key, table in self._table_persistence_map().items():
            self._schedule_last_visible_column_fill(key, table)

    def _table_column_size_changed(self, key, table, logical, new_width):
        if self._restoring_presentation_state or self._auto_filling_last_column:
            return
        preferred = self._preferred_widths_for_table(key, table)
        if 0 <= int(logical) < len(preferred):
            preferred[int(logical)] = max(40, int(new_width))
            self._column_widths[key] = preferred
        self._presentation_state_save_timer.start()
        self._schedule_last_visible_column_fill(key, table)

    def _table_sort_changed(self, key, logical, order):
        if self._restoring_presentation_state:
            return
        self._table_sorts[key] = {
            "column": int(logical),
            "order": (
                "desc"
                if order == Qt.SortOrder.DescendingOrder
                else "asc"
            ),
        }
        self._presentation_state_save_timer.start()

    def _splitter_persistence_map(self):
        splitters = {
            "cpu_process": getattr(self, "cpu_process_splitter", None),
            "cpu_associated": getattr(self, "cpu_associated_splitter", None),
            "memory_process": getattr(self, "memory_process_splitter", None),
            "memory_detail": getattr(self, "memory_detail_splitter", None),
            "physical_memory": getattr(self, "physical_memory_splitter", None),
            "physical_detail": getattr(self, "physical_detail_splitter", None),
        }
        if getattr(self, "overview_splitter", None) is not None:
            splitters["overview_strips"] = self.overview_splitter
        return {
            key: splitter
            for key, splitter in splitters.items()
            if isinstance(splitter, QSplitter)
        }

    def _register_splitter_persistence(self, key, splitter):
        if splitter.property("linux_resmon_persistence_key"):
            return
        saved = self._splitter_sizes.get(key)
        if isinstance(saved, list) and len(saved) == splitter.count():
            try:
                sizes = [max(0, int(value)) for value in saved]
            except (TypeError, ValueError):
                sizes = []
            if sizes and any(sizes):
                splitter.setSizes(sizes)
        splitter.setProperty("linux_resmon_persistence_key", key)
        splitter.splitterMoved.connect(
            lambda _pos, _index, key=key, splitter=splitter:
                self._splitter_size_changed(key, splitter)
        )

    def _setup_splitter_size_persistence(self):
        self._restoring_presentation_state = True
        try:
            for key, splitter in self._splitter_persistence_map().items():
                self._register_splitter_persistence(key, splitter)
        finally:
            self._restoring_presentation_state = False
        self._splitter_persistence_ready = True

    def _splitter_size_changed(self, key, splitter):
        if self._restoring_presentation_state:
            return
        self._splitter_sizes[key] = [int(value) for value in splitter.sizes()]
        self._presentation_state_save_timer.start()

    def _capture_splitter_sizes(self):
        for key, splitter in self._splitter_persistence_map().items():
            self._splitter_sizes[key] = [int(value) for value in splitter.sizes()]

    def _flush_presentation_state(self):
        self._capture_splitter_sizes()
        self._write_settings({
            "column_widths": dict(self._column_widths),
            "table_sorts": dict(self._table_sorts),
            "splitter_sizes": dict(self._splitter_sizes),
        })

    def _apply_stabilization_default_sorts(self):
        # Inventory-oriented tables default deterministically A → Z. Saved
        # per-table sort choices are restored afterwards.
        overview_tables = [
            table
            for tables in getattr(self, "ov_tables", {}).values()
            for table in tables.values()
        ]
        for table in (
            *overview_tables,
            self.mem_process_table,
            self.net_process_table,
            self.net_activity_table,
            self.service_table,
            self.disk_devices_table,
            self.tcp_table,
            self.udp_table,
            self.listen_table,
        ):
            table.sortItems(0, Qt.SortOrder.AscendingOrder)

    def _setup_keyboard_navigation_stabilization(self):
        """Give Up/Down a stable selected-row anchor after live refresh.

        The three tables already known to behave correctly retain their native
        key handling unchanged.
        """
        protected_native = {
            self.cpu_process_table,
            self.disk_process_table,
            self.disk_activity_table,
        }
        targets = []
        for table in self._table_persistence_map().values():
            if table in protected_native:
                continue
            if table.selectionMode() == QAbstractItemView.SelectionMode.NoSelection:
                continue
            targets.append(table)

        self._keyboard_navigation_targets = {}
        for table in targets:
            self._keyboard_navigation_targets[table] = table
            self._keyboard_navigation_targets[table.viewport()] = table
            table.installEventFilter(self)
            table.viewport().installEventFilter(self)

    def eventFilter(self, watched, event):
        fill_target = getattr(self, "_last_column_fill_viewports", {}).get(watched)
        if fill_target is not None and event.type() == QEvent.Type.Resize:
            key, fill_table = fill_target
            self._schedule_last_visible_column_fill(key, fill_table)

        table = getattr(self, "_keyboard_navigation_targets", {}).get(watched)
        if table is not None and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down):
                blocked_modifiers = (
                    Qt.KeyboardModifier.ControlModifier
                    | Qt.KeyboardModifier.AltModifier
                    | Qt.KeyboardModifier.MetaModifier
                )
                if not (event.modifiers() & blocked_modifiers):
                    visible_rows = [
                        row for row in range(table.rowCount())
                        if not table.isRowHidden(row)
                    ]
                    if visible_rows:
                        model = table.selectionModel()
                        selected = model.selectedRows(0) if model is not None else []
                        anchor_row = selected[0].row() if selected else table.currentRow()

                        if anchor_row in visible_rows:
                            position = visible_rows.index(anchor_row)
                            position += -1 if event.key() == Qt.Key.Key_Up else 1
                            position = max(0, min(position, len(visible_rows) - 1))
                            target_row = visible_rows[position]
                        else:
                            target_row = (
                                visible_rows[-1]
                                if event.key() == Qt.Key.Key_Up
                                else visible_rows[0]
                            )

                        column = table.currentColumn()
                        if column < 0 or column >= table.columnCount():
                            column = 0
                        index = table.model().index(target_row, column)
                        if model is not None and index.isValid():
                            model.setCurrentIndex(
                                index,
                                QItemSelectionModel.SelectionFlag.ClearAndSelect
                                | QItemSelectionModel.SelectionFlag.Rows,
                            )
                            table.scrollTo(
                                index,
                                QAbstractItemView.ScrollHint.EnsureVisible,
                            )
                            event.accept()
                            return True
        return super().eventFilter(watched, event)

    def _overview_spec(self, resource, provider_id=None):
        provider_id = provider_id or self._overview_content.get(resource)
        for spec in OVERVIEW_PROVIDER_OPTIONS.get(resource, ()):
            if spec["id"] == provider_id:
                return spec
        return OVERVIEW_PROVIDER_OPTIONS.get(resource, ({},))[0]

    def set_overview_content(self, resource, provider_id):
        if resource not in OVERVIEW_PROVIDER_OPTIONS:
            return
        valid_ids = {spec["id"] for spec in OVERVIEW_PROVIDER_OPTIONS[resource]}
        if provider_id not in valid_ids:
            return
        if self._overview_content.get(resource) == provider_id:
            return

        self._overview_content[resource] = provider_id
        spec = self._overview_spec(resource, provider_id)

        label = getattr(self, "ov_title_labels", {}).get(resource)
        if label is not None:
            label.setText(f"<b>{spec['title']}</b>")

        stack = getattr(self, "ov_stacks", {}).get(resource)
        table = getattr(self, "ov_tables", {}).get(resource, {}).get(provider_id)
        if stack is not None and table is not None:
            stack.setCurrentWidget(table)
            self._schedule_last_visible_column_fill(
                f"overview_{resource}_{provider_id}",
                table,
            )

        edit = getattr(self, "ov_filters", {}).get(resource)
        if edit is not None:
            edit.setPlaceholderText(f"Filter {spec['title']}…")
            self._apply_overview_filter(resource, edit.text())

        self._save_overview_settings()
        if self._tab_key_at() == "overview":
            self._refresh_overview_resource(resource)

    def set_layout_locked(self, locked):
        self._layout_locked = bool(locked)
        self.tabs.setMovable(not self._layout_locked)
        self._save_overview_settings()
        self._update_overview_move_controls()

    def set_overview_layout_mode(self, mode):
        mode = "quadrants" if str(mode).casefold() == "quadrants" else "lines"
        if self._layout_locked or mode == self._overview_layout_mode:
            return
        self._overview_layout_mode = mode
        self._apply_overview_layout()
        self._save_overview_settings()

    def toggle_overview_layout(self):
        if self._layout_locked:
            return
        target = "lines" if self._overview_layout_mode == "quadrants" else "quadrants"
        self.set_overview_layout_mode(target)

    def toggle_layout_lock(self):
        self.set_layout_locked(not self._layout_locked)

    def _setup_shortcuts(self):
        self._shortcut_options = QShortcut(QKeySequence("Ctrl+/"), self)
        self._shortcut_options.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._shortcut_options.activated.connect(self.show_options)

        self._shortcut_layout = QShortcut(QKeySequence("Ctrl+L"), self)
        self._shortcut_layout.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._shortcut_layout.activated.connect(self.toggle_overview_layout)

        self._shortcut_layout_lock = QShortcut(QKeySequence("Ctrl+Shift+L"), self)
        self._shortcut_layout_lock.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._shortcut_layout_lock.activated.connect(self.toggle_layout_lock)

    def _restore_tab_order(self):
        saved = self._load_settings().get("tab_order", [])
        expected = ["overview", "cpu", "memory", "disk", "network"]
        if not isinstance(saved, list):
            return
        order = [key for key in saved if key in expected]
        order.extend(key for key in expected if key not in order)
        bar = self.tabs.tabBar()
        for target, key in enumerate(order):
            current = next((i for i in range(self.tabs.count()) if self._tab_key_at(i) == key), -1)
            if current >= 0 and current != target:
                bar.moveTab(current, target)

    def _tab_moved(self, _from, _to):
        if not self._layout_locked:
            self._save_tab_order()

    def _sync_view_combo(self):
        key = self._tab_key_at()
        options = self._view_options.get(key, [])
        if key == "overview" or not options:
            self.view_corner.setVisible(False)
            return
        self.view_corner.setVisible(True)
        wanted = self._view_index.get(key, 0)
        self.view_combo.blockSignals(True)
        self.view_combo.clear()
        self.view_combo.addItems(options)
        if options:
            self.view_combo.setCurrentIndex(max(0, min(wanted, len(options) - 1)))
        self.view_combo.blockSignals(False)
        stack = self._stack_for_tab(key)
        if stack is not None and options:
            stack.setCurrentIndex(self.view_combo.currentIndex())

    def _stack_for_tab(self, key):
        return {
            "cpu": getattr(self, "cpu_stack", None),
            "memory": getattr(self, "memory_stack", None),
            "disk": getattr(self, "disk_stack", None),
            "network": getattr(self, "network_stack", None),
        }.get(key)

    def _tab_changed(self, _index):
        self._sync_view_combo()
        self.refresh_data()

    def _view_changed(self, index):
        key = self._tab_key_at()
        if key not in self._view_options:
            return
        self._view_index[key] = max(0, index)
        if key == "memory" and index == 1:
            self._vmstat_previous = {}
            self._vmstat_previous_time = None
        stack = self._stack_for_tab(key)
        if stack is not None and 0 <= index < stack.count():
            stack.setCurrentIndex(index)
        self.refresh_data()

    def _overview_table(self, headers, selection_mode=None):
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(
            selection_mode
            if selection_mode is not None
            else QAbstractItemView.SelectionMode.SingleSelection
        )
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setWordWrap(False)
        table.setTextElideMode(Qt.TextElideMode.ElideRight)
        table.setSortingEnabled(True)
        table.verticalHeader().setVisible(False)
        return table

    @staticmethod
    def _table_header_texts(table):
        return [
            table.horizontalHeaderItem(column).text()
            if table.horizontalHeaderItem(column) is not None
            else f"Column {column + 1}"
            for column in range(table.columnCount())
        ]

    def _overview_header(self, title, key):
        header = QHBoxLayout()
        header.setContentsMargins(5, 2, 5, 2)
        label = QLabel(f"<b>{title}</b>")
        header.addWidget(label)
        header.addStretch(1)
        self.ov_title_labels[key] = label

        buttons = {}
        for name, direction in (("Up", "up"), ("Down", "down"), ("Left", "left"), ("Right", "right")):
            button = QPushButton(name)
            button.setFixedWidth(60)
            button.setStyleSheet(
                "QPushButton:disabled { "
                "color: #777777; background-color: #252525; border: 1px solid #3f3f3f; "
                "}"
            )
            button.clicked.connect(lambda _checked=False, k=key, d=direction: self._move_overview_card(k, d))
            header.addWidget(button)
            buttons[direction] = button
        self.ov_move_buttons[key] = buttons
        return header

    def _overview_card(self, key):
        spec = self._overview_spec(key)
        box = QGroupBox()
        layout = QVBoxLayout(box)
        layout.addLayout(self._overview_header(spec["title"], key))

        flt = QLineEdit()
        flt.setPlaceholderText(f"Filter {spec['title']}…")
        flt.textChanged.connect(
            lambda text="", resource=key: self._apply_overview_filter(resource, text)
        )
        layout.addWidget(flt)
        self.ov_filters[key] = flt

        stack = QStackedWidget()
        tables = {}
        for option in OVERVIEW_PROVIDER_OPTIONS[key]:
            source = getattr(self, option["source_table"])
            table = self._overview_table(
                self._table_header_texts(source),
                source.selectionMode(),
            )
            stack.addWidget(table)
            tables[option["id"]] = table
        self.ov_tables[key] = tables
        self.ov_stacks[key] = stack
        stack.setCurrentWidget(tables[spec["id"]])
        layout.addWidget(stack, 1)
        return box

    def _clear_overview_host(self):
        # Detach the four persistent cards first so deleting an old layout host
        # can never destroy their tables/filters.
        for box in self.ov_boxes.values():
            box.setParent(None)
        while self.overview_host_layout.count():
            item = self.overview_host_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def _apply_overview_layout(self):
        if not hasattr(self, "overview_host_layout"):
            return
        if getattr(self, "overview_splitter", None) is not None:
            self._splitter_sizes["overview_strips"] = [
                int(value) for value in self.overview_splitter.sizes()
            ]
            if getattr(self, "_splitter_persistence_ready", False):
                self._presentation_state_save_timer.start()
        self._clear_overview_host()
        ordered_boxes = [self.ov_boxes[key] for key in self._overview_order]

        if self._overview_layout_mode == "quadrants":
            host = QWidget()
            grid = QGridLayout(host)
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setSpacing(6)
            for index, box in enumerate(ordered_boxes):
                grid.addWidget(box, index // 2, index % 2)
            grid.setRowStretch(0, 1)
            grid.setRowStretch(1, 1)
            grid.setColumnStretch(0, 1)
            grid.setColumnStretch(1, 1)
            self.overview_layout_widget = host
            self.overview_splitter = None
        else:
            splitter = QSplitter(Qt.Orientation.Vertical)
            for box in ordered_boxes:
                splitter.addWidget(box)
            splitter.setChildrenCollapsible(False)
            splitter.setSizes([200, 200, 200, 200])
            self.overview_layout_widget = splitter
            self.overview_splitter = splitter
            if getattr(self, "_splitter_persistence_ready", False):
                self._register_splitter_persistence("overview_strips", splitter)

        self.overview_host_layout.addWidget(self.overview_layout_widget, 1)
        self._update_overview_move_controls()

    def _move_overview_card(self, key, direction):
        if self._layout_locked or key not in self._overview_order:
            return
        index = self._overview_order.index(key)
        target = None
        if self._overview_layout_mode == "quadrants":
            row, col = divmod(index, 2)
            if direction == "up" and row > 0:
                target = index - 2
            elif direction == "down" and row < 1:
                target = index + 2
            elif direction == "left" and col > 0:
                target = index - 1
            elif direction == "right" and col < 1:
                target = index + 1
        else:
            if direction == "up" and index > 0:
                target = index - 1
            elif direction == "down" and index < len(self._overview_order) - 1:
                target = index + 1

        if target is None or not (0 <= target < len(self._overview_order)):
            self._update_overview_move_controls()
            return
        self._overview_order[index], self._overview_order[target] = (
            self._overview_order[target], self._overview_order[index]
        )
        self._apply_overview_layout()
        self._save_overview_settings()

    def _update_overview_move_controls(self):
        quadrants = self._overview_layout_mode == "quadrants"
        unlocked = not self._layout_locked
        for key, buttons in self.ov_move_buttons.items():
            if key not in self._overview_order:
                continue

            # Lock Layout removes positioning chrome from the cards entirely.
            # Unlocking restores the controls appropriate to the active layout.
            buttons["up"].setVisible(unlocked)
            buttons["down"].setVisible(unlocked)
            buttons["left"].setVisible(unlocked and quadrants)
            buttons["right"].setVisible(unlocked and quadrants)
            if not unlocked:
                continue

            index = self._overview_order.index(key)
            row, col = divmod(index, 2)
            if quadrants:
                buttons["up"].setEnabled(row > 0)
                buttons["down"].setEnabled(row < 1)
                buttons["left"].setEnabled(col > 0)
                buttons["right"].setEnabled(col < 1)
            else:
                buttons["up"].setEnabled(index > 0)
                buttons["down"].setEnabled(index < len(self._overview_order) - 1)
                buttons["left"].setEnabled(False)
                buttons["right"].setEnabled(False)

    def _setup_overview_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 6, 0, 0)

        self.overview_host = QWidget()
        self.overview_host_layout = QVBoxLayout(self.overview_host)
        self.overview_host_layout.setContentsMargins(0, 0, 0, 0)
        self.overview_host_layout.setSpacing(0)

        self.ov_boxes = {}
        self.ov_title_labels = {}
        self.ov_filters = {}
        self.ov_tables = {}
        self.ov_stacks = {}

        for resource in ("cpu", "memory", "disk", "network"):
            self.ov_boxes[resource] = self._overview_card(resource)

        self._apply_overview_layout()
        layout.addWidget(self.overview_host, 1)

        # Canonical resource tabs are constructed first so their real tables can
        # act as Overview providers. Insert Overview at the traditional leading
        # position afterwards.
        page.setProperty("linux_resmon_tab_key", "overview")
        index = self.tabs.insertTab(0, page, "Overview")
        self.tabs.setCurrentIndex(index)

    def _single_view_page(self, title, table, placeholder=None, context_label=None):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 6, 0, 0)
        if context_label is not None:
            layout.addWidget(context_label)
        box, flt = _panel(title, table, placeholder)
        layout.addWidget(box, 1)
        return page, flt

    def _setup_cpu_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        self.cpu_stack = QStackedWidget()

        # Processes remains the known-good exp6/v23 CPU table and sampler.
        # Handles and Modules are contextual details of the selected process, so
        # they deliberately live on this same screen rather than in the View
        # dropdown.
        process_page = QWidget()
        process_layout = QVBoxLayout(process_page)
        process_layout.setContentsMargins(0, 6, 0, 0)
        self.cpu_process_splitter = QSplitter(Qt.Orientation.Vertical)

        self.cpu_process_table = _table(["Process Name", "PID", "CPU %", "Threads", "Status"])
        self.cpu_process_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        process_box, self.cpu_filter = _panel(
            "Processes", self.cpu_process_table, "Filter CPU by Process Name or PID..."
        )
        self.cpu_process_table.itemSelectionChanged.connect(self._cpu_selection_changed)
        self.cpu_process_splitter.addWidget(process_box)

        associated = QWidget()
        associated_layout = QVBoxLayout(associated)
        associated_layout.setContentsMargins(0, 0, 0, 0)
        associated_layout.setSpacing(6)
        self.associated_context = QLabel("Select a process above to inspect its associated handles and modules.")
        associated_layout.addWidget(self.associated_context)

        self.cpu_associated_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.handle_table = _table(["FD", "Handle / Target"])
        handle_box, self.handle_filter = _panel(
            "Associated Handles", self.handle_table, "Filter handles for the selected process…"
        )
        self.cpu_associated_splitter.addWidget(handle_box)

        self.module_table = _table(["Mapped Module / File", "Permissions", "Address"])
        module_box, self.module_filter = _panel(
            "Associated Modules", self.module_table, "Filter modules for the selected process…"
        )
        self.cpu_associated_splitter.addWidget(module_box)
        self.cpu_associated_splitter.setSizes([1, 1])
        associated_layout.addWidget(self.cpu_associated_splitter, 1)

        self.cpu_process_splitter.addWidget(associated)
        self.cpu_process_splitter.setSizes([420, 260])
        process_layout.addWidget(self.cpu_process_splitter, 1)
        self.cpu_stack.addWidget(process_page)

        self.service_table = _table(["Service", "PID", "CPU %", "Load", "Active", "Sub", "Description"])
        self.service_table.itemSelectionChanged.connect(self._service_selection_changed)
        service_page, self.service_filter = self._single_view_page(
            "Services", self.service_table, "Filter systemd services…"
        )
        self.cpu_stack.addWidget(service_page)

        layout.addWidget(self.cpu_stack, 1)
        self._add_resource_tab(page, "CPU", "cpu")

    def _setup_memory_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        self.memory_stack = QStackedWidget()

        # Processes — live inventory plus lazy details for one selected process.
        process_page = QWidget()
        process_layout = QVBoxLayout(process_page)
        process_layout.setContentsMargins(0, 6, 0, 0)
        process_layout.setSpacing(6)
        self.memory_process_splitter = QSplitter(Qt.Orientation.Vertical)

        self.mem_process_table = _table(["Process Name", "PID", "RSS (RAM)", "RAM %", "Shared", "Virtual Memory"])
        process_box, self.mem_filter = _panel(
            "Processes", self.mem_process_table, "Filter processes by name or PID…"
        )
        self.memory_process_splitter.addWidget(process_box)

        selected_box = QGroupBox("Selected Process Memory")
        selected_layout = QVBoxLayout(selected_box)
        selected_layout.setContentsMargins(8, 12, 8, 8)
        selected_layout.setSpacing(6)
        self.memory_context = QLabel("Select a process above to inspect its Linux memory attribution and mappings.")
        self.memory_context.setWordWrap(True)
        selected_layout.addWidget(self.memory_context)

        self.memory_detail_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.memory_summary_table = _table(["Metric", "Value"])
        self.memory_summary_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        summary_box, _ = _panel("Memory Summary", self.memory_summary_table)
        self.memory_detail_splitter.addWidget(summary_box)

        self.memory_map_table = _table([
            "Address Range", "Permissions", "RSS", "PSS", "Private", "Shared", "Swap", "Mapping"
        ])
        mappings_box, self.memory_map_filter = _panel(
            "Memory Map", self.memory_map_table, "Filter mappings by address, permissions or path…"
        )
        self.memory_detail_splitter.addWidget(mappings_box)
        self.memory_detail_splitter.setSizes([300, 700])
        selected_layout.addWidget(self.memory_detail_splitter, 1)
        self.memory_process_splitter.addWidget(selected_box)
        self.memory_process_splitter.setSizes([360, 320])
        process_layout.addWidget(self.memory_process_splitter, 1)
        self.memory_stack.addWidget(process_page)
        self.mem_process_table.itemSelectionChanged.connect(self._memory_selection_changed)
        self.mem_filter.textChanged.connect(self._memory_filter_changed)

        # Physical Memory — Linux RAM composition + VM activity; no NUMA/topology
        # material is duplicated here because that belongs to Hardware Inspector.
        physical_page = QWidget()
        physical_layout = QVBoxLayout(physical_page)
        physical_layout.setContentsMargins(0, 6, 0, 0)
        physical_layout.setSpacing(6)

        self.physical_summary_table = _table(["Metric", "Value", "% of RAM"])
        self.physical_summary_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.physical_summary_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        summary_panel, _ = _panel("Physical Memory Summary", self.physical_summary_table)

        # The summary and the two deep physical-memory panels are separated by a
        # real vertical splitter so the user can choose how much height each
        # part receives instead of being constrained by a fixed summary height.
        self.physical_memory_splitter = QSplitter(Qt.Orientation.Vertical)
        self.physical_memory_splitter.setChildrenCollapsible(False)
        self.physical_memory_splitter.addWidget(summary_panel)

        self.physical_detail_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.physical_detail_splitter.setChildrenCollapsible(False)
        self.memory_class_table = _table(["Memory Class", "Amount", "% of RAM", "Kind"])
        self.memory_class_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        class_panel, _ = _panel("Linux Memory Classes", self.memory_class_table)
        self.physical_detail_splitter.addWidget(class_panel)

        self.vm_activity_table = _table(["VM Activity", "Counter", "Rate / s"])
        self.vm_activity_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        vm_panel, _ = _panel("Virtual Memory Activity", self.vm_activity_table)
        self.physical_detail_splitter.addWidget(vm_panel)
        self.physical_detail_splitter.setSizes([1, 1])
        self.physical_memory_splitter.addWidget(self.physical_detail_splitter)
        self.physical_memory_splitter.setStretchFactor(0, 0)
        self.physical_memory_splitter.setStretchFactor(1, 1)
        self.physical_memory_splitter.setSizes([220, 520])
        physical_layout.addWidget(self.physical_memory_splitter, 1)
        self.memory_stack.addWidget(physical_page)

        layout.addWidget(self.memory_stack, 1)
        self._add_resource_tab(page, "Memory", "memory")

    def _setup_disk_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        self.disk_stack = QStackedWidget()

        self.disk_process_table = _table(["Process Name", "PID", "Read Rate", "Write Rate", "Total I/O Rate"])
        process_page, self.disk_filter = self._single_view_page(
            "Processes with Disk Activity", self.disk_process_table, "Filter processes by name or PID…"
        )
        self.disk_stack.addWidget(process_page)

        self.disk_activity_table = _table(["Process Name", "PID", "Open / Mapped File", "Process I/O Rate"])
        activity_page, self.disk_activity_filter = self._single_view_page(
            "Disk Activity", self.disk_activity_table, "Filter disk activity by process, PID or file…"
        )
        self.disk_stack.addWidget(activity_page)

        self.disk_devices_table = _table(["Device", "Mount Point", "File System", "Read Rate", "Write Rate", "IOPS", "Busy %", "In Flight", "Space Used"])
        self.disk_devices_table.itemSelectionChanged.connect(self._disk_device_selection_changed)
        devices_page, self.disk_devices_filter = self._single_view_page(
            "Disk Devices", self.disk_devices_table, "Filter disk devices by device or mount point…"
        )
        self.disk_stack.addWidget(devices_page)

        layout.addWidget(self.disk_stack, 1)
        self._add_resource_tab(page, "Disk", "disk")

    def _setup_network_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        self.network_stack = QStackedWidget()

        self.net_process_table = _table(["Process Name", "PID", "TCP", "UDP", "Remote Endpoints", "Sockets"])
        self.net_process_table.itemSelectionChanged.connect(self._network_process_selection_changed)
        process_page, self.net_process_filter = self._single_view_page(
            "Processes with Network Sockets", self.net_process_table, "Filter processes by name or PID…"
        )
        self.network_stack.addWidget(process_page)

        self.net_activity_table = _table(["Interface", "Upload Rate", "Download Rate", "Total Uploaded", "Total Downloaded"])
        self.net_activity_table.itemSelectionChanged.connect(self._network_activity_selection_changed)
        activity_page, _ = self._single_view_page("Network Activity", self.net_activity_table)
        self.network_stack.addWidget(activity_page)

        self.tcp_table = _table(["Process Name", "PID", "Local Address", "Remote Address", "State", "Protocol"])
        self.tcp_table.itemSelectionChanged.connect(lambda: self._network_socket_selection_changed("tcp"))
        tcp_page, self.tcp_filter = self._single_view_page("TCP Connections", self.tcp_table, "Filter TCP connections…")
        self.network_stack.addWidget(tcp_page)

        self.udp_table = _table(["Process Name", "PID", "Local Address", "Remote Endpoint"])
        self.udp_table.itemSelectionChanged.connect(lambda: self._network_socket_selection_changed("udp"))
        udp_page, self.udp_filter = self._single_view_page("UDP Endpoints", self.udp_table, "Filter UDP endpoints…")
        self.network_stack.addWidget(udp_page)

        self.listen_table = _table(["Process Name", "PID", "Local Address", "Protocol", "State"])
        self.listen_table.itemSelectionChanged.connect(lambda: self._network_socket_selection_changed("listen"))
        listen_page, self.listen_filter = self._single_view_page(
            "Listening / Bound Ports", self.listen_table, "Filter listening or bound ports…"
        )
        self.network_stack.addWidget(listen_page)

        layout.addWidget(self.network_stack, 1)
        self._add_resource_tab(page, "Network", "network")

    def set_monitoring_active(self, active: bool):
        """Run the one-second sampler only while Resource Monitor is active.

        This keeps the known-good exp6/v23 rate-counter lifecycle. Hosted
        deactivation additionally ends any optional privileged session so no
        invisible root helper remains alive after the user leaves the applet.
        """
        active = bool(active)
        if not active:
            if hasattr(self, "_presentation_state_save_timer"):
                if self._presentation_state_save_timer.isActive():
                    self._presentation_state_save_timer.stop()
                self._flush_presentation_state()
            if hasattr(self, "timer") and self.timer.isActive():
                self.timer.stop()
            if self.privilege.state != "off" or self.privilege.process is not None:
                self.privilege.stop()
            self._net_cache = []
            self._net_cache_time = 0.0
            self.prev_service_cpu.clear()
            self._vmstat_previous = {}
            self._vmstat_previous_time = None
            self._last_priv_state = self.privilege.state
            self._update_privilege_ui()
            return

        if psutil is None:
            return
        if not self.timer.isActive():
            self.prev_proc_io.clear()
            self.prev_disk_io.clear()
            self.prev_net_io.clear()
            self.prev_service_cpu.clear()
            self._vmstat_previous = {}
            self._vmstat_previous_time = None
            self._active_processes()
            self.timer.start()
        self.refresh_data()

    def show_options(self, initial_tab=0):
        dialog = ResMonOptionsDialog(self, initial_tab=initial_tab)
        dialog.exec()
        self._update_privilege_ui()

    def toggle_privileged(self):
        if self.privilege.state == "on":
            self.privilege.stop()
            self._net_cache = []
            self._net_cache_time = 0.0
            self._update_privilege_ui()
            self.refresh_data()
            return
        if self.privilege.state == "connecting":
            return
        ok, why = self.privilege.availability()
        if not ok:
            self._update_privilege_ui()
            # Helper management lives in Options; privilege itself remains
            # in-place and does not create a separate elevated monitor window.
            dialog = ResMonOptionsDialog(self, initial_tab=1)
            dialog.helper_access_label.setText(f"Privileged access: Unavailable — {why}")
            dialog.exec()
            self._update_privilege_ui()
            return
        self.privilege.start_async()
        self._update_privilege_ui()

    def _update_privilege_ui(self):
        state = self.privilege.state
        normal_status_qss = "background: transparent; color: #dcdcdc;"
        privileged_status_qss = "background: #3a2d13; color: #f2d18b;"

        # Kernel Ring Buffer authority: the button is the top-row privilege
        # control; prose/status is a plain italic bottom status surface.
        if state == "on" and self.privilege.enabled:
            self.priv_button.setText("Privileged: On")
            self.priv_button.setEnabled(True)
            self.priv_button.setStyleSheet(PRIVILEGE_ACTIVE_QSS)
            self.priv_status.setText("Expanded read-only visibility · amber data = privileged source")
            self.priv_status.setStyleSheet(privileged_status_qss)
        elif state == "connecting":
            self.priv_button.setText("Privileged: Authorizing…")
            self.priv_button.setEnabled(False)
            self.priv_button.setStyleSheet("")
            self.priv_status.setText("Waiting for polkit authorization")
            self.priv_status.setStyleSheet(normal_status_qss)
        elif state == "error":
            self.priv_button.setText("Privileged: Off")
            self.priv_button.setEnabled(True)
            self.priv_button.setStyleSheet("")
            self.priv_status.setText(self.privilege.message)
            self.priv_status.setStyleSheet(normal_status_qss)
        else:
            self.priv_button.setText("Privileged: Off")
            self.priv_button.setEnabled(True)
            self.priv_button.setStyleSheet("")
            details = helper_status_details()
            suffix = ""
            if details.get("ready"):
                suffix = " · helper installed"
            elif details.get("installed"):
                suffix = " · helper needs repair"
            self.priv_status.setText("Normal user visibility" + suffix)
            self.priv_status.setStyleSheet(normal_status_qss)

    def shutdown(self):
        """Idempotently stop live sampling and the optional helper."""
        if self.timer.isActive():
            self.timer.stop()
        if self._presentation_state_save_timer.isActive():
            self._presentation_state_save_timer.stop()
        self._flush_presentation_state()
        self.privilege.stop()

    # ------------------------------------------------------------------
    # Process / system helpers
    # ------------------------------------------------------------------
    def _active_processes(self):
        """Return cached psutil.Process objects using the exp6/v23 sampling model.

        Keeping one Process instance per live PID is important: psutil's
        non-blocking cpu_percent() is an interval measurement between calls on
        that object. New processes are primed once; dead/stale entries are
        retired rather than continually recreating Process objects.
        """
        if psutil is None:
            return []
        try:
            current_pids = set(psutil.pids())
        except (psutil.Error, OSError):
            return []

        dead_pids = set(self.proc_cache) - current_pids
        for pid in dead_pids:
            self.proc_cache.pop(pid, None)
            self.prev_proc_io.pop(pid, None)

        active_procs = []
        for pid in current_pids:
            proc = self.proc_cache.get(pid)
            if proc is None:
                try:
                    proc = psutil.Process(pid)
                    # First non-blocking call establishes the baseline; do not
                    # recreate/re-prime this object on each refresh.
                    proc.cpu_percent()
                    self.proc_cache[pid] = proc
                except (psutil.Error, OSError):
                    continue
            else:
                try:
                    if not proc.is_running():
                        self.proc_cache.pop(pid, None)
                        self.prev_proc_io.pop(pid, None)
                        continue
                except (psutil.Error, OSError):
                    self.proc_cache.pop(pid, None)
                    self.prev_proc_io.pop(pid, None)
                    continue
            active_procs.append((pid, proc))
        return active_procs

    def _current_selected_pid(self):
        row = self.cpu_process_table.currentRow()
        if row < 0:
            return None
        item = self.cpu_process_table.item(row, 1)
        if not item:
            return None
        try:
            return int(item.text())
        except ValueError:
            return None

    def _cpu_selection_changed(self):
        pid = self._current_selected_pid()
        if pid != self._selected_cpu_pid:
            self._selected_cpu_pid = pid
            self._refresh_associated(pid)

    def _refresh_associated(self, pid):
        if not pid:
            self.associated_context.setText("Select a process above to inspect its associated handles and modules.")
            _fill_table(self.handle_table, [])
            _fill_table(self.module_table, [])
            return
        try:
            proc_name = self.proc_cache.get(pid).name() if self.proc_cache.get(pid) is not None else psutil.Process(pid).name()
        except (psutil.Error, OSError, AttributeError):
            proc_name = "Process"
        context = f"Selected process: {proc_name} (PID {pid})"
        self.associated_context.setText(context)
        handle_rows = None
        module_rows = None
        handles_privileged = False
        modules_privileged = False
        if self.privilege.enabled:
            response = self.privilege.request("process_handles", pid=pid)
            if response and response.get("ok"):
                handle_rows = [(r.get("fd", ""), r.get("target", "")) for r in response.get("rows", [])]
                handles_privileged = True
            response = self.privilege.request("process_modules", pid=pid)
            if response and response.get("ok"):
                module_rows = [(r.get("path", ""), r.get("perms", ""), r.get("address", "")) for r in response.get("rows", [])]
                modules_privileged = True

        if handle_rows is None:
            handle_rows = []
            try:
                fdroot = Path(f"/proc/{pid}/fd")
                for fd in fdroot.iterdir():
                    try:
                        target = os.readlink(fd)
                    except OSError:
                        continue
                    handle_rows.append((fd.name, target))
                handle_rows.sort(key=lambda r: int(r[0]) if str(r[0]).isdigit() else 10**9)
            except OSError:
                handle_rows = [("—", "Access denied — enable Privileged for expanded visibility")]

        if module_rows is None:
            module_rows = []
            try:
                proc = psutil.Process(pid)
                seen = set()
                for mm in proc.memory_maps(grouped=False):
                    path = getattr(mm, "path", "")
                    if not path or not path.startswith("/") or path in seen:
                        continue
                    seen.add(path)
                    perms = getattr(mm, "perms", "")
                    addr = getattr(mm, "addr", "")
                    module_rows.append((path, perms, addr))
            except (psutil.Error, OSError):
                module_rows = [("Access denied — enable Privileged for expanded visibility", "", "")]

        _fill_table(
            self.handle_table,
            handle_rows,
            numeric_cols={0: lambda v: int(v) if str(v).isdigit() else -1},
            privileged_rows=range(len(handle_rows)) if handles_privileged else (),
        )
        _fill_table(
            self.module_table,
            module_rows,
            privileged_rows=range(len(module_rows)) if modules_privileged else (),
        )
        if self.handle_filter:
            self.handle_filter.textChanged.emit(self.handle_filter.text())
        if self.module_filter:
            self.module_filter.textChanged.emit(self.module_filter.text())

    # ------------------------------------------------------------------
    # Overview Provider Architecture
    # ------------------------------------------------------------------
    @staticmethod
    def _clone_overview_item(item):
        if item is None:
            return QTableWidgetItem("")
        if isinstance(item, NumericItem):
            clone = NumericItem(item.text(), getattr(item, "raw", 0))
        else:
            clone = QTableWidgetItem(item.text())
        clone.setFlags(item.flags())
        clone.setFont(item.font())
        clone.setForeground(item.foreground())
        clone.setBackground(item.background())
        clone.setTextAlignment(Qt.AlignmentFlag(item.textAlignment()))
        clone.setToolTip(item.toolTip())
        clone.setStatusTip(item.statusTip())
        clone.setWhatsThis(item.whatsThis())
        clone.setIcon(item.icon())
        return clone

    def _overview_row_identity(self, spec, source, row):
        first = source.item(row, 0)
        if first is not None:
            identity = first.data(Qt.ItemDataRole.UserRole)
            if identity is not None:
                return identity
        values = []
        for column in spec.get("identity_columns", (0,)):
            item = source.item(row, int(column))
            values.append(item.text() if item is not None else "")
        return tuple(values)

    def _selected_overview_identity(self, table):
        model = table.selectionModel()
        if model is not None:
            selected = model.selectedRows(0)
            if selected:
                item = table.item(selected[0].row(), 0)
                if item is not None:
                    return item.data(Qt.ItemDataRole.UserRole)
        return None

    def _copy_provider_table_to_overview(self, resource, spec):
        source = getattr(self, spec["source_table"])
        target = self.ov_tables[resource][spec["id"]]

        selected_identity = self._selected_overview_identity(target)
        v_scroll = target.verticalScrollBar().value()
        h_scroll = target.horizontalScrollBar().value()
        was_sorting = target.isSortingEnabled()

        target.blockSignals(True)
        try:
            model = target.selectionModel()
            if model is not None:
                model.clearSelection()
                model.clearCurrentIndex()

            target.setSortingEnabled(False)
            target.setRowCount(source.rowCount())
            for row in range(source.rowCount()):
                identity = self._overview_row_identity(spec, source, row)
                for column in range(source.columnCount()):
                    item = self._clone_overview_item(source.item(row, column))
                    if column == 0:
                        item.setData(Qt.ItemDataRole.UserRole, identity)
                    target.setItem(row, column, item)

            target.setSortingEnabled(was_sorting)

            if selected_identity is not None and model is not None:
                for row in range(target.rowCount()):
                    item = target.item(row, 0)
                    if item is not None and item.data(Qt.ItemDataRole.UserRole) == selected_identity:
                        index = target.model().index(row, 0)
                        model.select(
                            index,
                            QItemSelectionModel.SelectionFlag.Select
                            | QItemSelectionModel.SelectionFlag.Rows,
                        )
                        break

            target.verticalScrollBar().setValue(v_scroll)
            target.horizontalScrollBar().setValue(h_scroll)
        finally:
            target.blockSignals(False)

        edit = self.ov_filters.get(resource)
        self._apply_overview_filter(resource, edit.text() if edit is not None else "")

    def _apply_overview_filter(self, resource, text=""):
        spec = self._overview_spec(resource)
        table = self.ov_tables.get(resource, {}).get(spec["id"])
        if table is None:
            return
        needle = str(text).strip().casefold()
        for row in range(table.rowCount()):
            match = not needle
            if needle:
                for column in range(table.columnCount()):
                    item = table.item(row, column)
                    if item is not None and needle in item.text().casefold():
                        match = True
                        break
            table.setRowHidden(row, not match)

    def _refresh_overview_resource(self, resource):
        spec = self._overview_spec(resource)

        # CPU Processes is the only canonical full-tab path whose input filter
        # changes which records are collected (it can reveal a matching idle
        # process). Overview uses the canonical unfiltered process inventory and
        # applies its own independent filter afterwards.
        cpu_filter_text = None
        cpu_filter_blocked = None
        if spec["id"] == "cpu_processes":
            cpu_filter_text = self.cpu_filter.text()
            cpu_filter_blocked = self.cpu_filter.blockSignals(True)
            self.cpu_filter.setText("")

        try:
            getattr(self, spec["refresh"])()
        finally:
            if spec["id"] == "cpu_processes":
                self.cpu_filter.setText(cpu_filter_text)
                self.cpu_filter.blockSignals(cpu_filter_blocked)

        self._copy_provider_table_to_overview(resource, spec)
        target = self.ov_tables[resource][spec["id"]]
        self._schedule_last_visible_column_fill(
            f"overview_{resource}_{spec['id']}",
            target,
        )

    def _refresh_overview(self):
        # Four independent presentation cards, but no duplicate measurement
        # implementations: each card refreshes its selected canonical full-tab
        # provider then mirrors those exact rows.
        for resource in ("cpu", "memory", "disk", "network"):
            self._refresh_overview_resource(resource)

    # ------------------------------------------------------------------
    # Refresh dispatch
    # ------------------------------------------------------------------
    def refresh_data(self, *_):
        if psutil is None:
            return
        if self.privilege.state != self._last_priv_state or (self.privilege.state == "on" and not self.privilege.enabled):
            self._last_priv_state = self.privilege.state
            self._update_privilege_ui()
            # Flush helper-derived provenance on every privilege transition,
            # including cancellation/error/off, so amber rows can never linger.
            self._net_cache = []
            self._net_cache_time = 0.0
            self._refresh_associated(self._selected_cpu_pid)
        else:
            self._update_privilege_ui()

        key = self._tab_key_at()
        if key == "overview":
            self._refresh_overview()
        elif key == "cpu":
            if self.cpu_stack.currentIndex() == 0:
                self._refresh_cpu()
                self._refresh_associated(self._selected_cpu_pid)
            else:
                self._refresh_services()
        elif key == "memory":
            if self.memory_stack.currentIndex() == 0:
                self._refresh_memory_processes()
            else:
                self._refresh_physical_memory()
        elif key == "disk":
            self._refresh_disk()
        elif key == "network":
            self._refresh_network()

    # ------------------------------------------------------------------
    # CPU
    # ------------------------------------------------------------------
    def _refresh_cpu(self):
        table = self.cpu_process_table
        flt = self.cpu_filter
        selected = self._selected_cpu_pid
        v_scroll = table.verticalScrollBar().value()
        was_sorting = table.isSortingEnabled()
        table.setSortingEnabled(False)
        filter_text = flt.text().strip().lower()
        rows = []

        # This is intentionally the last-known-working exp6/v23 CPU sampling
        # pattern. Idle processes stay out of the unfiltered view; typing a
        # process name/PID can still reveal a matching idle process.
        for pid, proc in self._active_processes():
            try:
                name = proc.name() or "Unknown"
                cpu_pct = proc.cpu_percent()
                threads = proc.num_threads()
                status = proc.status()
                matches = filter_text in name.lower() or filter_text in str(pid)
                # Keep an explicitly selected process visible at 0% so its
                # Handles/Modules context does not disappear between samples.
                if cpu_pct > 0 or pid == selected or (filter_text and matches):
                    if not filter_text or matches:
                        rows.append((name, pid, cpu_pct, threads, status))
            except (psutil.Error, AttributeError, OSError):
                continue

        signals_were_blocked = table.blockSignals(True)
        table.setRowCount(len(rows))
        selected_row = None
        for row, (name, pid, cpu_pct, threads, status) in enumerate(rows):
            self._update_cpu_cell(table, row, 0, name)
            self._update_cpu_cell(table, row, 1, str(pid), pid)
            self._update_cpu_cell(table, row, 2, f"{cpu_pct:.1f}%", cpu_pct)
            self._update_cpu_cell(table, row, 3, str(threads), threads)
            self._update_cpu_cell(table, row, 4, status)
            if selected is not None and pid == selected:
                selected_row = row

        table.setSortingEnabled(was_sorting)
        table.verticalScrollBar().setValue(v_scroll)
        table.blockSignals(signals_were_blocked)

        # Keep the CPU->Handles/Modules relationship without forcing selection
        # to jump around on every one-second refresh.
        visible_pids = {pid for _, pid, _, _, _ in rows}
        if selected is not None and selected not in self.proc_cache:
            self._selected_cpu_pid = None
            selected = None
            self._refresh_associated(None)
        if selected is not None and selected in visible_pids:
            # Sorting can move the row, so locate by PID after re-enabling it.
            for row in range(table.rowCount()):
                item = table.item(row, 1)
                if item and item.text() == str(selected):
                    table.selectRow(row)
                    break


    @staticmethod
    def _update_cpu_cell(table, row, column, text, raw_val=None):
        """exp6-style in-place cell update to avoid needless table churn."""
        item = table.item(row, column)
        if raw_val is not None:
            if isinstance(item, NumericItem):
                item.setText(str(text))
                item.raw = raw_val
            else:
                table.setItem(row, column, NumericItem(str(text), raw_val))
        else:
            if item is not None:
                item.setText(str(text))
            else:
                table.setItem(row, column, QTableWidgetItem(str(text)))

    def _current_selected_service_unit(self):
        table = self.service_table
        model = table.selectionModel()
        if model is not None:
            selected_rows = model.selectedRows(0)
            if selected_rows:
                item = table.item(selected_rows[0].row(), 0)
                if item:
                    return item.text()
        row = table.currentRow()
        if row >= 0:
            item = table.item(row, 0)
            if item:
                return item.text()
        return None

    def _service_selection_changed(self):
        self._selected_service_unit = self._current_selected_service_unit()

    @staticmethod
    def _cgroup_usage_usec(control_group):
        """Read cumulative service CPU usage from cgroup v2 cpu.stat."""
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

    def _service_metadata(self):
        """Cached systemd service identity/state including ControlGroup."""
        now = time.monotonic()
        if self._service_cache and now - self._service_cache_time < 5.0:
            return self._service_cache

        rows = []
        try:
            listed = subprocess.run(
                ["systemctl", "list-units", "--type=service", "--all", "--no-legend", "--no-pager", "--plain"],
                capture_output=True,
                text=True,
                timeout=2.5,
                check=False,
            )
            units = []
            base = {}
            for line in listed.stdout.splitlines():
                parts = line.split(None, 4)
                if len(parts) < 4:
                    continue
                unit, load, active, sub = parts[:4]
                if not unit.endswith(".service"):
                    continue
                desc = parts[4] if len(parts) > 4 else ""
                units.append(unit)
                base[unit] = {
                    "unit": unit,
                    "load": load,
                    "active": active,
                    "sub": sub,
                    "desc": desc,
                    "pid": 0,
                    "cgroup": "",
                }

            units = units[:500]
            if units:
                shown = subprocess.run(
                    [
                        "systemctl", "show", *units,
                        "--property=Id",
                        "--property=MainPID",
                        "--property=ControlGroup",
                        "--no-pager",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=4.0,
                    check=False,
                )
                current = None
                for line in shown.stdout.splitlines():
                    if line.startswith("Id="):
                        current = line[3:]
                    elif current and line.startswith("MainPID=") and current in base:
                        try:
                            base[current]["pid"] = int(line[8:] or 0)
                        except ValueError:
                            base[current]["pid"] = 0
                    elif current and line.startswith("ControlGroup=") and current in base:
                        base[current]["cgroup"] = line[13:]

            rows = [base[unit] for unit in units if unit in base]
        except (OSError, subprocess.SubprocessError):
            rows = []

        self._service_cache = rows
        self._service_cache_time = now
        return rows

    def _fill_service_inventory(self, rows):
        """Refresh Services without allowing selection to own the viewport."""
        table = self.service_table
        selected = self._selected_service_unit
        v_scroll = table.verticalScrollBar().value()
        h_scroll = table.horizontalScrollBar().value()

        signals_were_blocked = table.blockSignals(True)
        try:
            model = table.selectionModel()
            if model is not None:
                model.clearSelection()
                model.clearCurrentIndex()

            _fill_table(
                table,
                rows,
                numeric_cols={
                    1: lambda v: int(v) if str(v).isdigit() else -1,
                    2: lambda v: float(str(v).rstrip("%")),
                },
            )
            self.service_filter.textChanged.emit(self.service_filter.text())

            selected_row = -1
            if selected:
                for row in range(table.rowCount()):
                    if table.isRowHidden(row):
                        continue
                    item = table.item(row, 0)
                    if item and item.text() == selected:
                        selected_row = row
                        break

            if selected_row >= 0 and model is not None:
                index = table.model().index(selected_row, 0)
                model.select(
                    index,
                    QItemSelectionModel.SelectionFlag.Select
                    | QItemSelectionModel.SelectionFlag.Rows,
                )
                current_unit = selected
            else:
                current_unit = None

            table.verticalScrollBar().setValue(v_scroll)
            table.horizontalScrollBar().setValue(h_scroll)
        finally:
            table.blockSignals(signals_were_blocked)

        self._selected_service_unit = current_unit

    def _refresh_services(self):
        now = time.monotonic()
        rows = []
        metadata = self._service_metadata()

        if not metadata:
            self._fill_service_inventory(
                [("systemd unavailable", "", "0.0%", "", "", "", "Could not query systemctl")]
            )
            return

        for item in metadata:
            unit = item["unit"]
            pid = int(item.get("pid") or 0)
            cpu = 0.0

            # Existing ResMon TUI authority: a service is its ControlGroup,
            # not merely MainPID.
            usage = self._cgroup_usage_usec(item.get("cgroup"))
            if usage is not None:
                old = self.prev_service_cpu.get(unit)
                if old:
                    old_usage, old_t = old
                    dt = now - old_t
                    if dt > 0:
                        cpu = max(
                            0.0,
                            (usage - old_usage) / (dt * 1_000_000.0) * 100.0,
                        )
                self.prev_service_cpu[unit] = (usage, now)
            elif pid:
                # Fallback only when cgroup CPU is unavailable.
                try:
                    proc = self.proc_cache.get(pid)
                    if proc is None:
                        proc = psutil.Process(pid)
                        proc.cpu_percent()
                        self.proc_cache[pid] = proc
                    else:
                        cpu = max(0.0, float(proc.cpu_percent()))
                except (psutil.Error, OSError, AttributeError):
                    cpu = 0.0

            rows.append((
                unit,
                pid or "",
                f"{cpu:.1f}%",
                item.get("load", ""),
                item.get("active", ""),
                item.get("sub", ""),
                item.get("desc", ""),
            ))

        rows.sort(key=lambda row: str(row[0]).casefold())
        self._fill_service_inventory(rows)

    @staticmethod
    def _read_meminfo():
        data = {}
        try:
            for line in Path("/proc/meminfo").read_text(errors="replace").splitlines():
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
        except (OSError, ValueError):
            pass
        return data

    @staticmethod
    def _read_vmstat():
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
    def _read_smaps_rollup(pid):
        values = {}
        path = Path(f"/proc/{pid}/smaps_rollup")
        try:
            for line in path.read_text(errors="replace").splitlines()[1:]:
                key, sep, rest = line.partition(":")
                if not sep:
                    continue
                parts = rest.strip().split()
                if not parts:
                    continue
                try:
                    value = int(parts[0])
                except ValueError:
                    continue
                if len(parts) > 1 and parts[1].lower() == "kb":
                    value *= 1024
                values[key] = value
            return values, ""
        except OSError as exc:
            return {}, str(exc)

    @staticmethod
    def _read_smaps_mappings(pid):
        mappings = []
        current = None
        try:
            with Path(f"/proc/{pid}/smaps").open("r", errors="replace") as handle:
                for raw in handle:
                    line = raw.rstrip("\n")
                    parts = line.split(None, 5)
                    is_header = (
                        len(parts) >= 5
                        and "-" in parts[0]
                        and len(parts[1]) == 4
                        and parts[1][0] in "r-"
                    )
                    if is_header:
                        if current is not None:
                            mappings.append(current)
                        current = {
                            "address": parts[0],
                            "perms": parts[1],
                            "path": parts[5] if len(parts) > 5 else "[anonymous]",
                            "Rss": 0,
                            "Pss": 0,
                            "Private_Clean": 0,
                            "Private_Dirty": 0,
                            "Private_Hugetlb": 0,
                            "Shared_Clean": 0,
                            "Shared_Dirty": 0,
                            "Shared_Hugetlb": 0,
                            "Swap": 0,
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
        if response and response.get("ok"):
            values = response.get("values", {})
            return (dict(values), "") if isinstance(values, dict) else ({}, "Privileged helper returned invalid memory summary data.")
        return {}, self.privilege.message or "Privileged helper could not read this process memory summary."

    def _helper_memory_mappings(self, pid):
        if not self.privilege.enabled:
            return [], "Privileged helper is not active."
        response = self.privilege.request("process_memory_map", pid=pid, timeout=3.0)
        if response and response.get("ok"):
            rows = response.get("rows", [])
            return (list(rows), "") if isinstance(rows, list) else ([], "Privileged helper returned invalid memory-map data.")
        return [], self.privilege.message or "Privileged helper could not read this process memory map."

    def _memory_access_message(self, error, helper_attempted=False):
        text = str(error or "").strip()
        restricted = "permission denied" in text.casefold() or "errno 13" in text.casefold()
        if restricted:
            if helper_attempted:
                return "Restricted — privileged helper could not expand visibility for this process."
            return "Restricted — enable Privileged for expanded visibility."
        return f"Unavailable: {text}" if text else "Not reported"

    def _current_selected_memory_pid(self):
        # Periodic refresh restores the selected PID through the selection
        # model without assigning a current index. Prefer selectedRows() so a
        # visibly selected process does not have to own the viewport.
        model = self.mem_process_table.selectionModel()
        if model is not None:
            selected_rows = model.selectedRows(1)
            if selected_rows:
                item = self.mem_process_table.item(selected_rows[0].row(), 1)
                if item:
                    try:
                        return int(item.text())
                    except ValueError:
                        pass

        row = self.mem_process_table.currentRow()
        if row < 0:
            return None
        item = self.mem_process_table.item(row, 1)
        if not item:
            return None
        try:
            return int(item.text())
        except ValueError:
            return None

    def _memory_select_row_without_scrolling(self, row):
        """Select a Memory process row without making Qt navigate to it."""
        table = self.mem_process_table
        model = table.selectionModel()
        if model is None or row < 0 or row >= table.rowCount():
            return False
        model.clearSelection()
        model.clearCurrentIndex()
        index = table.model().index(row, 0)
        model.select(
            index,
            QItemSelectionModel.SelectionFlag.Select
            | QItemSelectionModel.SelectionFlag.Rows,
        )
        return True

    def _memory_find_visible_pid_row(self, pid):
        if pid is None:
            return -1
        for row in range(self.mem_process_table.rowCount()):
            if self.mem_process_table.isRowHidden(row):
                continue
            item = self.mem_process_table.item(row, 1)
            if item and item.text() == str(pid):
                return row
        return -1

    def _memory_first_visible_row(self):
        for row in range(self.mem_process_table.rowCount()):
            if not self.mem_process_table.isRowHidden(row):
                return row
        return -1

    def _memory_selection_changed(self):
        pid = self._current_selected_memory_pid()
        if pid != self._selected_memory_pid:
            self._selected_memory_pid = pid
            self._refresh_selected_memory(pid, force=True)

    def _memory_filter_changed(self, *_):
        if getattr(self, "_memory_refresh_in_progress", False):
            return

        selected_pid = self._current_selected_memory_pid()
        if self._memory_find_visible_pid_row(selected_pid) >= 0:
            return

        row = self._memory_first_visible_row()
        if row >= 0:
            self.mem_process_table.blockSignals(True)
            self._memory_select_row_without_scrolling(row)
            self.mem_process_table.blockSignals(False)
            pid = self._current_selected_memory_pid()
            self._selected_memory_pid = pid
            self._refresh_selected_memory(pid, force=True)
            return

        self.mem_process_table.clearSelection()
        model = self.mem_process_table.selectionModel()
        if model is not None:
            model.clearCurrentIndex()
        self._selected_memory_pid = None
        self._refresh_selected_memory(None, force=True)

    def _refresh_memory_processes(self):
        selected = self._selected_memory_pid
        table = self.mem_process_table

        # Selection and viewport are separate state. Preserve the selected PID,
        # but never let the one-second refresh navigate back to it after the
        # user has scrolled elsewhere.
        v_scroll = table.verticalScrollBar().value()
        h_scroll = table.horizontalScrollBar().value()

        rows = []
        for pid, proc in self._active_processes():
            try:
                with proc.oneshot():
                    name = proc.name() or "Unknown"
                    info = proc.memory_info()
                    rss = int(getattr(info, "rss", 0) or 0)
                    vms = int(getattr(info, "vms", 0) or 0)
                    shared = int(getattr(info, "shared", 0) or 0)
                    pct = float(proc.memory_percent())
                if rss <= 0:
                    continue
                rows.append((name, pid, format_bytes(rss), f"{pct:.2f}%", format_bytes(shared), format_bytes(vms), rss))
            except (psutil.Error, OSError, AttributeError):
                continue
        rows.sort(key=lambda r: r[6], reverse=True)

        table.blockSignals(True)
        self._memory_refresh_in_progress = True
        try:
            # Memory bypasses _fill_table's select_key path because that path
            # uses QTableWidget.selectRow(), which can make the selected process
            # the view's current navigation target.
            _fill_table(
                table,
                [r[:6] for r in rows],
                numeric_cols={
                    1: lambda v: int(v),
                    2: parse_bytes_text,
                    3: lambda v: float(str(v).rstrip("%")),
                    4: parse_bytes_text,
                    5: parse_bytes_text,
                },
            )
            self.mem_filter.textChanged.emit(self.mem_filter.text())

            selected_row = self._memory_find_visible_pid_row(selected)
            if selected_row < 0:
                selected_row = self._memory_first_visible_row()

            if selected_row >= 0:
                self._memory_select_row_without_scrolling(selected_row)
                current_pid = self._current_selected_memory_pid()
            else:
                table.clearSelection()
                model = table.selectionModel()
                if model is not None:
                    model.clearCurrentIndex()
                current_pid = None

            # Viewport restoration happens after selection restoration.
            table.verticalScrollBar().setValue(v_scroll)
            table.horizontalScrollBar().setValue(h_scroll)
        finally:
            self._memory_refresh_in_progress = False
            table.blockSignals(False)

        self._selected_memory_pid = current_pid
        self._refresh_selected_memory(current_pid, force=False)

    def _refresh_selected_memory(self, pid, force=False):
        if not pid:
            self._memory_detail_pid = None
            self.memory_context.setText("Select a process above to inspect its Linux memory attribution and mappings.")
            _fill_table(self.memory_summary_table, [])
            _fill_table(self.memory_map_table, [])
            return

        now = time.monotonic()
        if not force and pid == self._memory_detail_pid and now - self._memory_detail_time < 5.0:
            return

        try:
            proc = self.proc_cache.get(pid) or psutil.Process(pid)
            with proc.oneshot():
                name = proc.name() or "Unknown"
                info = proc.memory_info()
                vms = int(getattr(info, "vms", 0) or 0)
                basic_rss = int(getattr(info, "rss", 0) or 0)
                basic_shared = int(getattr(info, "shared", 0) or 0)
        except (psutil.Error, OSError, AttributeError):
            name = "Process"
            vms = 0
            basic_rss = 0
            basic_shared = 0

        rollup, rollup_error = self._read_smaps_rollup(pid)
        mappings, mapping_error = self._read_smaps_mappings(pid)
        rollup_privileged = False
        mappings_privileged = False
        helper_attempted_rollup = False
        helper_attempted_mappings = False

        # Ordinary /proc visibility is always attempted first. Privilege is a
        # fallback only for the selected process and only for the two fixed
        # smaps operations declared by the helper contract.
        if rollup_error and self.privilege.enabled:
            helper_attempted_rollup = True
            helper_rollup, helper_error = self._helper_memory_summary(pid)
            if helper_rollup:
                rollup = helper_rollup
                rollup_error = ""
                rollup_privileged = True
            elif helper_error:
                rollup_error = helper_error

        if mapping_error and self.privilege.enabled:
            helper_attempted_mappings = True
            helper_mappings, helper_error = self._helper_memory_mappings(pid)
            if helper_mappings:
                mappings = helper_mappings
                mapping_error = ""
                mappings_privileged = True
            elif helper_error:
                mapping_error = helper_error

        provenance = " — amber rows are helper-sourced." if (rollup_privileged or mappings_privileged) else ""
        self.memory_context.setText(
            f"Selected process: {name} (PID {pid}) — detailed smaps data is read lazily for this process only{provenance}"
        )

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
        summary_rows = [
            ("Process", name),
            ("PID", str(pid)),
            ("Virtual Memory", format_bytes(vms)),
            ("RSS", format_bytes(rss)),
            ("PSS", format_bytes(pss) if pss_reported else "Not reported"),
            ("Private / USS", format_bytes(private) if private_reported else "Not reported"),
            ("Shared", format_bytes(shared) if shared_reported else "Not reported"),
            ("Anonymous", format_bytes(anonymous) if anonymous_reported else "Not reported"),
            ("Swap", format_bytes(swap) if swap_reported else "Not reported"),
        ]
        if rollup_error:
            summary_rows.append(("smaps_rollup", self._memory_access_message(rollup_error, helper_attempted_rollup)))
        summary_privileged_rows = set(range(3, 9)) if rollup_privileged else set()
        _fill_table(self.memory_summary_table, summary_rows, privileged_rows=summary_privileged_rows)

        mapping_rows = []
        for item in mappings:
            private_bytes = int(item.get("Private_Clean", 0)) + int(item.get("Private_Dirty", 0)) + int(item.get("Private_Hugetlb", 0))
            shared_bytes = int(item.get("Shared_Clean", 0)) + int(item.get("Shared_Dirty", 0)) + int(item.get("Shared_Hugetlb", 0))
            mapping_rows.append((
                item.get("address", ""),
                item.get("perms", ""),
                format_bytes(item.get("Rss", 0)),
                format_bytes(item.get("Pss", 0)),
                format_bytes(private_bytes),
                format_bytes(shared_bytes),
                format_bytes(item.get("Swap", 0)),
                item.get("path", "[anonymous]") or "[anonymous]",
            ))
        if not mapping_rows and mapping_error:
            mapping_rows = [("—", "", "", "", "", "", "", self._memory_access_message(mapping_error, helper_attempted_mappings))]
        privileged_map_rows = set(range(len(mapping_rows))) if mappings_privileged else set()
        _fill_table(
            self.memory_map_table,
            mapping_rows,
            numeric_cols={2: parse_bytes_text, 3: parse_bytes_text, 4: parse_bytes_text, 5: parse_bytes_text, 6: parse_bytes_text},
            privileged_rows=privileged_map_rows,
        )
        self.memory_map_filter.textChanged.emit(self.memory_map_filter.text())
        self._memory_detail_pid = pid
        self._memory_detail_time = now

    def _refresh_physical_memory(self):
        m = self._read_meminfo()
        total = int(m.get("MemTotal", 0) or 0)
        available = int(m.get("MemAvailable", m.get("MemFree", 0)) or 0)
        used = max(0, total - available)
        swap_total = int(m.get("SwapTotal", 0) or 0)
        swap_used = max(0, swap_total - int(m.get("SwapFree", 0) or 0))
        divisor = total or 1

        summary = [
            ("Total RAM", format_bytes(total), "100.0%" if total else "—"),
            ("In use (derived)", format_bytes(used), f"{used / divisor * 100:.1f}%" if total else "—"),
            ("Available", format_bytes(available), f"{available / divisor * 100:.1f}%" if total else "—"),
            ("Free", format_bytes(m.get("MemFree", 0)), f"{int(m.get('MemFree', 0) or 0) / divisor * 100:.1f}%" if total else "—"),
            ("Swap used", format_bytes(swap_used), f"{(swap_used / swap_total * 100):.1f}% of swap" if swap_total else "—"),
            ("Swap total", format_bytes(swap_total), ""),
        ]
        _fill_table(self.physical_summary_table, summary)

        class_defs = [
            ("Anonymous", "AnonPages", "Kernel reported"),
            ("Page Cache / Cached", "Cached", "Kernel reported"),
            ("Buffers", "Buffers", "Kernel reported"),
            ("Slab — Reclaimable", "SReclaimable", "Kernel reported"),
            ("Slab — Unreclaimable", "SUnreclaim", "Kernel reported"),
            ("Page Tables", "PageTables", "Kernel reported"),
            ("Kernel Stack", "KernelStack", "Kernel reported"),
            ("Shared Memory", "Shmem", "Kernel reported"),
            ("Dirty", "Dirty", "Kernel reported"),
            ("Writeback", "Writeback", "Kernel reported"),
            ("HugeTLB", "Hugetlb", "Kernel reported"),
        ]
        classes = []
        for label, key, kind in class_defs:
            value = int(m.get(key, 0) or 0)
            classes.append((label, format_bytes(value), f"{value / divisor * 100:.2f}%" if total else "—", kind))
        _fill_table(self.memory_class_table, classes, numeric_cols={1: parse_bytes_text, 2: lambda v: float(str(v).rstrip("%")) if str(v).endswith("%") else -1})

        now = time.monotonic()
        vm = self._read_vmstat()
        previous = self._vmstat_previous
        previous_time = self._vmstat_previous_time
        dt = (now - previous_time) if previous_time is not None else 0.0

        def total_for(prefix):
            return sum(int(value) for key, value in vm.items() if key.startswith(prefix))

        metrics = [
            ("Page Faults", int(vm.get("pgfault", 0)), "events"),
            ("Major Faults", int(vm.get("pgmajfault", 0)), "events"),
            ("Swap In", int(vm.get("pswpin", 0)), "pages"),
            ("Swap Out", int(vm.get("pswpout", 0)), "pages"),
            ("Pages Scanned", total_for("pgscan_"), "pages"),
            ("Pages Reclaimed", total_for("pgsteal_"), "pages"),
            ("OOM Kills", int(vm.get("oom_kill", 0)), "events"),
        ]
        previous_totals = {
            "Page Faults": int(previous.get("pgfault", 0)),
            "Major Faults": int(previous.get("pgmajfault", 0)),
            "Swap In": int(previous.get("pswpin", 0)),
            "Swap Out": int(previous.get("pswpout", 0)),
            "Pages Scanned": sum(int(value) for key, value in previous.items() if key.startswith("pgscan_")),
            "Pages Reclaimed": sum(int(value) for key, value in previous.items() if key.startswith("pgsteal_")),
            "OOM Kills": int(previous.get("oom_kill", 0)),
        }
        activity_rows = []
        for label, counter, unit in metrics:
            rate = None
            if dt > 0 and previous:
                rate = max(0.0, (counter - previous_totals.get(label, counter)) / dt)
            activity_rows.append((label, f"{counter:,} {unit}", f"{rate:.1f} {unit}/s" if rate is not None else "Establishing baseline"))
        _fill_table(self.vm_activity_table, activity_rows)
        self._vmstat_previous = vm
        self._vmstat_previous_time = now

    # ------------------------------------------------------------------
    # Disk
    # ------------------------------------------------------------------
    def _associated_files_for_pid(self, pid, limit=4):
        # Return (path, privileged_source) so Disk Activity can show provenance
        # without implying that its process-wide I/O rate is a privileged value.
        paths = []
        seen = set()

        handle_rows = None
        module_rows = None
        handles_privileged = False
        modules_privileged = False
        if self.privilege.enabled:
            response = self.privilege.request("process_handles", pid=pid)
            if response and response.get("ok"):
                handle_rows = [(r.get("fd", ""), r.get("target", "")) for r in response.get("rows", [])]
                handles_privileged = True
            response = self.privilege.request("process_modules", pid=pid)
            if response and response.get("ok"):
                module_rows = [(r.get("path", ""), r.get("perms", ""), r.get("address", "")) for r in response.get("rows", [])]
                modules_privileged = True

        if handle_rows is None:
            handle_rows = []
            try:
                for fd in Path(f"/proc/{pid}/fd").iterdir():
                    try:
                        handle_rows.append((fd.name, os.readlink(fd)))
                    except OSError:
                        continue
            except OSError:
                pass

        for _fd, target in handle_rows:
            target = str(target)
            clean = target.replace(" (deleted)", "")
            if not clean.startswith("/") or clean in seen:
                continue
            seen.add(clean)
            paths.append((target, handles_privileged))
            if len(paths) >= limit:
                return paths

        if module_rows is None:
            module_rows = []
            try:
                for mm in psutil.Process(pid).memory_maps(grouped=False):
                    module_rows.append((getattr(mm, "path", ""), getattr(mm, "perms", ""), getattr(mm, "addr", "")))
            except (psutil.Error, OSError):
                pass

        for path, _perms, _addr in module_rows:
            path = str(path)
            clean = path.replace(" (deleted)", "")
            if not clean.startswith("/") or clean in seen:
                continue
            seen.add(clean)
            paths.append((path, modules_privileged))
            if len(paths) >= limit:
                break
        return paths

    @staticmethod
    def _sysfs_inflight(device):
        try:
            real = os.path.realpath(device)
            name = os.path.basename(real)
            fields = Path(f"/sys/class/block/{name}/stat").read_text().split()
            return int(fields[8]) if len(fields) > 8 else 0
        except (OSError, ValueError, IndexError):
            return 0

    def _current_selected_disk_device(self):
        table = self.disk_devices_table
        model = table.selectionModel()
        if model is not None:
            selected_rows = model.selectedRows(0)
            if selected_rows:
                item = table.item(selected_rows[0].row(), 0)
                if item:
                    return item.text()
        row = table.currentRow()
        if row >= 0:
            item = table.item(row, 0)
            if item:
                return item.text()
        return None

    def _disk_device_selection_changed(self):
        self._selected_disk_device = self._current_selected_disk_device()

    def _fill_disk_devices_inventory(self, rows):
        """Presentation-only Disk Devices refresh with stable device identity."""
        table = self.disk_devices_table
        selected = self._selected_disk_device
        v_scroll = table.verticalScrollBar().value()
        h_scroll = table.horizontalScrollBar().value()

        signals_were_blocked = table.blockSignals(True)
        try:
            model = table.selectionModel()
            if model is not None:
                model.clearSelection()
                model.clearCurrentIndex()

            _fill_table(
                table,
                rows,
                numeric_cols={
                    3: parse_bytes_text,
                    4: parse_bytes_text,
                    5: float,
                    6: lambda v: float(str(v).rstrip("%")),
                    7: int,
                    8: lambda v: float(str(v).rstrip("%")),
                },
            )
            self.disk_devices_filter.textChanged.emit(self.disk_devices_filter.text())

            selected_row = -1
            if selected:
                for row in range(table.rowCount()):
                    if table.isRowHidden(row):
                        continue
                    item = table.item(row, 0)
                    if item and item.text() == selected:
                        selected_row = row
                        break

            if selected_row >= 0 and model is not None:
                index = table.model().index(selected_row, 0)
                model.select(
                    index,
                    QItemSelectionModel.SelectionFlag.Select
                    | QItemSelectionModel.SelectionFlag.Rows,
                )
                current_device = selected
            else:
                current_device = None

            table.verticalScrollBar().setValue(v_scroll)
            table.horizontalScrollBar().setValue(h_scroll)
        finally:
            table.blockSignals(signals_were_blocked)

        self._selected_disk_device = current_device

    def _refresh_disk(self):
        now = time.monotonic()
        process_rows = []
        for pid, proc in self._active_processes():
            try:
                io = proc.io_counters()
                read_b = getattr(io, "read_bytes", 0)
                write_b = getattr(io, "write_bytes", 0)
                read_rate = write_rate = 0.0
                old = self.prev_proc_io.get(pid)
                if old:
                    old_r, old_w, old_t = old
                    dt = now - old_t
                    if dt > 0:
                        read_rate = max(0.0, (read_b - old_r) / dt)
                        write_rate = max(0.0, (write_b - old_w) / dt)
                self.prev_proc_io[pid] = (read_b, write_b, now)
                total_rate = read_rate + write_rate
                if total_rate > 0:
                    process_rows.append((proc.name() or "Unknown", pid, read_rate, write_rate, total_rate))
            except (psutil.Error, OSError, AttributeError):
                continue
        process_rows.sort(key=lambda r: r[4], reverse=True)
        _fill_table(
            self.disk_process_table,
            [(name, pid, format_rate(rr), format_rate(wr), format_rate(total)) for name, pid, rr, wr, total in process_rows],
            numeric_cols={1: int, 2: parse_bytes_text, 3: parse_bytes_text, 4: parse_bytes_text},
        )
        self.disk_filter.textChanged.emit(self.disk_filter.text())

        # Linux procfs provides process-wide I/O counters and visible file
        # associations, but not trustworthy per-file byte rates. Keep this
        # view explicit about that limitation instead of inventing attribution.
        file_rows = []
        privileged_file_rows = []
        for name, pid, _rr, _wr, total in process_rows[:20]:
            paths = self._associated_files_for_pid(pid, limit=4)
            if not paths:
                file_rows.append((name, pid, "<no visible file descriptor>", format_rate(total)))
            else:
                for path, privileged_source in paths:
                    row_index = len(file_rows)
                    file_rows.append((name, pid, path, format_rate(total)))
                    if privileged_source:
                        privileged_file_rows.append(row_index)
        _fill_table(
            self.disk_activity_table,
            file_rows,
            numeric_cols={1: int, 3: parse_bytes_text},
            privileged_rows=privileged_file_rows,
        )
        self.disk_activity_filter.textChanged.emit(self.disk_activity_filter.text())

        device_rates = {}
        try:
            counters = psutil.disk_io_counters(perdisk=True) or {}
            for dev, io in counters.items():
                read_b = getattr(io, "read_bytes", 0)
                write_b = getattr(io, "write_bytes", 0)
                read_c = getattr(io, "read_count", 0)
                write_c = getattr(io, "write_count", 0)
                busy = getattr(io, "busy_time", 0)
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
                device_rates[dev] = (rr, wr, iops, busy_pct)
        except (psutil.Error, OSError):
            pass

        device_rows = []
        try:
            partitions = psutil.disk_partitions(all=False)
        except (psutil.Error, OSError):
            partitions = []
        for part in partitions:
            try:
                usage = psutil.disk_usage(part.mountpoint)
            except (psutil.Error, OSError):
                continue
            real = os.path.realpath(part.device)
            devname = os.path.basename(real)
            fallback = os.path.basename(part.device)
            rr, wr, iops, busy = device_rates.get(devname, device_rates.get(fallback, (0.0, 0.0, 0.0, 0.0)))
            device_rows.append((
                part.device,
                part.mountpoint,
                part.fstype,
                format_rate(rr),
                format_rate(wr),
                f"{iops:.1f}",
                f"{busy:.1f}%",
                self._sysfs_inflight(part.device),
                f"{usage.percent:.1f}%",
            ))
        self._fill_disk_devices_inventory(device_rows)

    # ------------------------------------------------------------------
    # Network
    # ------------------------------------------------------------------
    def _unprivileged_connections(self):
        rows = []
        try:
            conns = psutil.net_connections(kind="inet")
        except psutil.AccessDenied:
            conns = []
            for pid, proc in self._active_processes():
                try:
                    getter = getattr(proc, "net_connections", None)
                    items = getter(kind="inet") if getter else proc.connections(kind="inet")
                    for conn in items:
                        rows.append(self._conn_record(conn, pid))
                except (psutil.Error, OSError):
                    continue
            return rows
        except (psutil.Error, OSError):
            return rows
        for conn in conns:
            rows.append(self._conn_record(conn, getattr(conn, "pid", None) or 0))
        return rows

    def _conn_record(self, conn, pid):
        name = "System/Kernel"
        if pid:
            proc = self.proc_cache.get(pid)
            try:
                name = (proc or psutil.Process(pid)).name()
            except (psutil.Error, OSError):
                name = "Access Denied"
        protocol = "TCP" if getattr(conn, "type", None) == socket.SOCK_STREAM else "UDP"
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
            "pid": int(pid or 0), "name": name, "local_ip": lip, "local_port": int(lport or 0),
            "remote_ip": rip, "remote_port": int(rport or 0),
            "status": getattr(conn, "status", "NONE") or "NONE", "protocol": protocol,
        }

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
        """Add helper visibility without ever subtracting ordinary truth."""
        merged = []
        helper_buckets = defaultdict(list)
        for helper_row in helper_rows:
            row = dict(helper_row)
            row["_privileged_source"] = True
            row["_helper_only"] = True
            row["_socket_inode"] = str(row.get("inode") or row.get("_socket_inode") or "")
            helper_buckets[cls._connection_semantic_key(row)].append(row)

        for ordinary_row in ordinary_rows:
            row = dict(ordinary_row)
            row["_privileged_source"] = False
            row["_helper_only"] = False
            row["_socket_inode"] = str(row.get("_socket_inode") or "")
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
                enriched = False

                if not ordinary_pid and helper_pid:
                    row["pid"] = helper_pid
                    ordinary_pid = helper_pid
                    enriched = True

                generic_names = {"", "Unknown", "System/Kernel", "Access Denied"}
                if helper_name and helper_name not in generic_names and ordinary_name in generic_names:
                    row["name"] = helper_name
                    enriched = True

                row["_socket_inode"] = str(helper_row.get("_socket_inode") or "")
                row["_helper_confirmed"] = True
                row["_privileged_source"] = enriched
                row["_helper_only"] = False

            merged.append(row)

        # Any helper row not matched to an ordinary observation is genuinely
        # additional privileged visibility and remains amber.
        for candidates in helper_buckets.values():
            for row in candidates:
                row["_privileged_source"] = True
                row["_helper_only"] = True
                merged.append(row)

        return merged

    def _get_connections(self):
        now = time.monotonic()
        # Socket ownership enumeration can be comparatively expensive; keep the
        # interface-rate sampler at 1 s while refreshing connection ownership at
        # most every 2 s.
        if self._net_cache and now - self._net_cache_time < 2.0:
            return list(self._net_cache)

        ordinary_rows = [
            dict(row, _privileged_source=False, _helper_only=False)
            for row in self._unprivileged_connections()
        ]
        rows = ordinary_rows

        if self.privilege.enabled:
            response = self.privilege.request("net_connections", timeout=1.0)
            if response and response.get("ok"):
                helper_rows = list(response.get("rows", []))
                rows = self._merge_connection_rows(ordinary_rows, helper_rows)

        self._net_cache = list(rows)
        self._net_cache_time = now
        return list(rows)

    @staticmethod
    def _endpoint(ip, port):
        if not ip:
            return ""
        if ":" in str(ip) and not str(ip).startswith("["):
            return f"[{ip}]:{port}" if port else str(ip)
        return f"{ip}:{port}" if port else str(ip)

    def _current_selected_network_interface(self):
        model = self.net_activity_table.selectionModel()
        if model is not None:
            selected_rows = model.selectedRows(0)
            if selected_rows:
                item = self.net_activity_table.item(selected_rows[0].row(), 0)
                if item:
                    return item.text()
        return None

    def _network_activity_selection_changed(self):
        self._selected_network_interface = self._current_selected_network_interface()

    def _network_activity_find_row(self, interface):
        if not interface:
            return -1
        for row in range(self.net_activity_table.rowCount()):
            item = self.net_activity_table.item(row, 0)
            if item and item.text() == interface:
                return row
        return -1

    def _network_activity_select_without_scrolling(self, row):
        table = self.net_activity_table
        model = table.selectionModel()
        if model is None or row < 0 or row >= table.rowCount():
            return False
        model.clearSelection()
        model.clearCurrentIndex()
        index = table.model().index(row, 0)
        model.select(
            index,
            QItemSelectionModel.SelectionFlag.Select
            | QItemSelectionModel.SelectionFlag.Rows,
        )
        return True

    @staticmethod
    def _network_socket_identity(row):
        inode = str(row.get("_socket_inode") or row.get("inode") or "")
        if inode:
            return ("inode", inode)
        remote_ip, remote_port = ResMonWidget._normalise_remote(
            row.get("remote_ip"), row.get("remote_port")
        )
        return (
            "socket",
            str(row.get("protocol") or "").upper(),
            int(row.get("pid") or 0),
            str(row.get("local_ip") or ""),
            int(row.get("local_port") or 0),
            remote_ip,
            remote_port,
            str(row.get("status") or "NONE").upper(),
        )

    @staticmethod
    def _network_selected_identity(table):
        model = table.selectionModel()
        if model is None:
            return None
        selected = model.selectedRows(0)
        if not selected:
            return None
        item = table.item(selected[0].row(), 0)
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def _network_process_selection_changed(self):
        identity = self._network_selected_identity(self.net_process_table)
        self._selected_network_process_pid = identity

    def _network_socket_selection_changed(self, kind):
        table = {
            "tcp": self.tcp_table,
            "udp": self.udp_table,
            "listen": self.listen_table,
        }.get(kind)
        if table is None:
            return
        identity = self._network_selected_identity(table)
        if kind == "tcp":
            self._selected_tcp_socket = identity
        elif kind == "udp":
            self._selected_udp_socket = identity
        else:
            self._selected_listen_socket = identity

    def _fill_network_inventory(
        self,
        table,
        display_rows,
        identities,
        selected_identity=None,
        numeric_cols=None,
        privileged_rows=None,
    ):
        """Refresh one Network inventory without row-owned selection/viewport."""
        numeric_cols = numeric_cols or {}
        privileged_rows = set(privileged_rows or ())
        v_scroll = table.verticalScrollBar().value()
        h_scroll = table.horizontalScrollBar().value()

        table.blockSignals(True)
        model = table.selectionModel()
        if model is not None:
            model.clearSelection()
            model.clearCurrentIndex()

        table.setSortingEnabled(False)
        table.setRowCount(len(display_rows))
        privileged_brush = QBrush(QColor(PRIVILEGED_DATA)) if privileged_rows else None
        for r, row in enumerate(display_rows):
            identity = identities[r] if r < len(identities) else None
            for c, value in enumerate(row):
                if c in numeric_cols:
                    raw = numeric_cols[c](value) if callable(numeric_cols[c]) else value
                    item = NumericItem(str(value), raw)
                else:
                    item = QTableWidgetItem(str(value))
                if c == 0:
                    item.setData(Qt.ItemDataRole.UserRole, identity)
                if privileged_brush is not None and r in privileged_rows:
                    item.setForeground(privileged_brush)
                    item.setToolTip("Visible or ownership-enriched through the active privileged read-only collector")
                table.setItem(r, c, item)
        table.setSortingEnabled(True)

        if selected_identity is not None and model is not None:
            for row in range(table.rowCount()):
                item = table.item(row, 0)
                if item is not None and item.data(Qt.ItemDataRole.UserRole) == selected_identity:
                    index = table.model().index(row, 0)
                    model.select(
                        index,
                        QItemSelectionModel.SelectionFlag.Select
                        | QItemSelectionModel.SelectionFlag.Rows,
                    )
                    break

        table.verticalScrollBar().setValue(v_scroll)
        table.horizontalScrollBar().setValue(h_scroll)
        table.blockSignals(False)
        return self._network_selected_identity(table)

    def _refresh_network(self):
        now = time.monotonic()
        connections = self._get_connections()
        self._net_cache = connections

        grouped = defaultdict(lambda: {"name": "", "tcp": 0, "udp": 0, "remote": set(), "count": 0, "privileged": False})
        for row in connections:
            pid = int(row.get("pid") or 0)
            if not pid:
                continue
            g = grouped[pid]
            g["name"] = row.get("name") or "Unknown"
            proto = str(row.get("protocol") or "").upper()
            if proto == "TCP":
                g["tcp"] += 1
            elif proto == "UDP":
                g["udp"] += 1
            rip = row.get("remote_ip") or ""
            rport = int(row.get("remote_port") or 0)
            if rip and (rip not in ("0.0.0.0", "::") or rport):
                g["remote"].add((rip, rport))
            g["count"] += 1
            g["privileged"] = g["privileged"] or bool(row.get("_privileged_source"))

        prows = [
            (g["name"], pid, g["tcp"], g["udp"], len(g["remote"]), g["count"], g["privileged"])
            for pid, g in grouped.items()
        ]
        prows.sort(key=lambda r: (r[0].casefold(), r[1]))
        self._selected_network_process_pid = self._fill_network_inventory(
            self.net_process_table,
            [r[:6] for r in prows],
            [r[1] for r in prows],
            selected_identity=self._selected_network_process_pid,
            numeric_cols={1: int, 2: int, 3: int, 4: int, 5: int},
            privileged_rows=[i for i, r in enumerate(prows) if r[6]],
        )
        self.net_process_filter.textChanged.emit(self.net_process_filter.text())

        selected_interface = self._selected_network_interface
        net_activity_v_scroll = self.net_activity_table.verticalScrollBar().value()
        net_activity_h_scroll = self.net_activity_table.horizontalScrollBar().value()

        iface_rows = []
        try:
            counters = psutil.net_io_counters(pernic=True) or {}
            for nic, io in counters.items():
                sent = io.bytes_sent
                recv = io.bytes_recv
                up = down = 0.0
                old = self.prev_net_io.get(nic)
                if old:
                    osent, orecv, ot = old
                    dt = now - ot
                    if dt > 0:
                        up = max(0.0, (sent - osent) / dt)
                        down = max(0.0, (recv - orecv) / dt)
                self.prev_net_io[nic] = (sent, recv, now)
                iface_rows.append((nic, format_rate(up), format_rate(down), format_bytes(sent), format_bytes(recv), up + down))
        except (psutil.Error, OSError):
            pass

        # Network Activity is an interface inventory: deterministic A → Z by
        # default. The user can still click another column to sort explicitly.
        iface_rows.sort(key=lambda r: r[0].casefold())

        table = self.net_activity_table
        table.blockSignals(True)
        model = table.selectionModel()
        if model is not None:
            model.clearSelection()
            model.clearCurrentIndex()

        _fill_table(table, [r[:5] for r in iface_rows])

        selected_row = self._network_activity_find_row(selected_interface)
        if selected_row >= 0:
            self._network_activity_select_without_scrolling(selected_row)
            current_interface = self._current_selected_network_interface()
        else:
            current_interface = None

        # Viewport belongs to the user, not to the selected interface.
        table.verticalScrollBar().setValue(net_activity_v_scroll)
        table.horizontalScrollBar().setValue(net_activity_h_scroll)
        table.blockSignals(False)
        self._selected_network_interface = current_interface

        tcp = []
        udp = []
        listen = []
        for row in connections:
            name = row.get("name") or "Unknown"
            pid = int(row.get("pid") or 0)
            local = self._endpoint(row.get("local_ip") or "", int(row.get("local_port") or 0))
            remote_ip, remote_port = self._normalise_remote(
                row.get("remote_ip"), row.get("remote_port")
            )
            remote = self._endpoint(remote_ip, remote_port)
            status = str(row.get("status") or "NONE")
            proto = str(row.get("protocol") or "").upper()
            privileged_source = bool(row.get("_privileged_source"))
            identity = self._network_socket_identity(row)

            if proto == "TCP" and status != "LISTEN" and remote:
                tcp.append((name, pid, local, remote, status, proto, privileged_source, identity))
            elif proto == "UDP" and remote:
                udp.append((name, pid, local, remote, privileged_source, identity))

            is_udp_bound = proto == "UDP" and not remote
            if (proto == "TCP" and status == "LISTEN") or is_udp_bound:
                listen.append((name, pid, local, proto, status, privileged_source, identity))

        tcp.sort(key=lambda r: (r[0].casefold(), r[1], r[2], r[3]))
        udp.sort(key=lambda r: (r[0].casefold(), r[1], r[2], r[3]))
        listen.sort(key=lambda r: (r[0].casefold(), r[1], r[2], r[3]))

        self._selected_tcp_socket = self._fill_network_inventory(
            self.tcp_table,
            [r[:6] for r in tcp],
            [r[7] for r in tcp],
            selected_identity=self._selected_tcp_socket,
            numeric_cols={1: int},
            privileged_rows=[i for i, r in enumerate(tcp) if r[6]],
        )
        self._selected_udp_socket = self._fill_network_inventory(
            self.udp_table,
            [r[:4] for r in udp],
            [r[5] for r in udp],
            selected_identity=self._selected_udp_socket,
            numeric_cols={1: int},
            privileged_rows=[i for i, r in enumerate(udp) if r[4]],
        )
        self._selected_listen_socket = self._fill_network_inventory(
            self.listen_table,
            [r[:5] for r in listen],
            [r[6] for r in listen],
            selected_identity=self._selected_listen_socket,
            numeric_cols={1: int},
            privileged_rows=[i for i, r in enumerate(listen) if r[5]],
        )
        self.tcp_filter.textChanged.emit(self.tcp_filter.text())
        self.udp_filter.textChanged.emit(self.udp_filter.text())
        self.listen_filter.textChanged.emit(self.listen_filter.text())

    def apply_host_settings(self, settings=None, column_visibility_callback=None):
        """Accept Suite appearance settings without importing Suite internals."""
        settings = settings or {}
        value = settings.get("metadata_font", "") if isinstance(settings, dict) else ""
        self._serialized_metadata_font = str(value or "")

    # Host compatibility aliases
    def set_applet_active(self, active):
        self.set_monitoring_active(bool(active))


def create_applet(parent=None):
    return ResMonWidget(parent=parent, start_active=False)


def run_standalone():
    if psutil is None:
        print("psutil is required for Resource Monitor.", file=sys.stderr)
        return 1

    from PyQt6.QtGui import QIcon

    existing = QApplication.instance()
    owns_app = existing is None
    app = existing or QApplication(sys.argv)
    app.setApplicationName(APPLET_NAME)
    app.setOrganizationName(APPLET_AUTHOR)

    icon_path = Path(__file__).resolve().parent / "icon.png"
    if icon_path.is_file():
        app.setWindowIcon(QIcon(str(icon_path)))

    try:
        from ._support import STANDALONE_STYLESHEET
    except ImportError:
        from _support import STANDALONE_STYLESHEET
    app.setStyleSheet(STANDALONE_STYLESHEET)
    app.setQuitOnLastWindowClosed(True)

    window = QMainWindow()
    if icon_path.is_file():
        window.setWindowIcon(QIcon(str(icon_path)))
    window.setWindowTitle(f"{APPLET_NAME} {APPLET_VERSION} — LinSpectacles Applet")
    widget = ResMonWidget(start_active=True)
    window.setCentralWidget(widget)
    window.resize(1280, 850)
    app.aboutToQuit.connect(widget.shutdown)
    window.show()

    # A normal standalone.py invocation always owns its QApplication. The
    # existing-app branch makes accidental/repeated in-process invocation safe
    # instead of trying to nest a second Qt event loop.
    if not owns_app:
        window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        return 0

    try:
        return int(app.exec())
    finally:
        widget.shutdown()

