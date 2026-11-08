#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# LinSpectacles TUI - applet support
# Copyright (C) 2026 brunonlinespace
# GPL-3.0-or-later

import csv
import curses
import io
import json
import os
import re
import time
from pathlib import Path

class BaseTUIApplet:
    """Toolkit-neutral contract consumed by the LinSpectacles curses host."""
    name = "Applet"
    metadata_title = " Metadata "
    scan_required = False
    live = False
    export_enabled = True

    def __init__(self, applet_dir=None):
        self.applet_dir = Path(applet_dir or Path(__file__).resolve().parent)
        self.records = []
        self.loaded = False
        self.status = "Ready."
        self.current_row = 0
        self.top_row = 0

    def ensure_loaded(self):
        if not self.loaded and not self.scan_required:
            self.refresh()

    def refresh(self):
        self.loaded = True

    def action_label(self):
        if self.scan_required:
            return "Rescan" if self.loaded else "Scan"
        return "Refresh"

    def get_records(self):
        return self.records

    def format_row(self, record, width):
        return f" {record.get('name', '')}"[:max(0, width)]

    def details(self, record):
        if record is None:
            return self.status
        return "\n".join(f"{k}: {v}" for k, v in record.items() if not str(k).startswith('_'))

    def export_sections(self):
        return {}

    def export_records(self):
        return list(self.records)

    def export_columns(self):
        return []

    def on_activate(self):
        self.ensure_loaded()

    def on_deactivate(self):
        pass

    def tick(self):
        pass

    def handle_key(self, key):
        return False

    def extra_footer(self):
        return ""

    def metadata_heading(self):
        return self.metadata_title


def _friendly_label(key):
    return str(key).replace('_', ' ').strip().title()


def _scalar(value):
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return value
    return None


def _schema(records, columns=None):
    labels, order = {}, []
    for col in columns or []:
        key = str(col[0]); label = str(col[1]) if len(col) > 1 else _friendly_label(key)
        labels[key] = label
        if key not in order: order.append(key)
    clean=[]
    for rec in records or []:
        if not isinstance(rec, dict): continue
        for key, value in rec.items():
            if str(key).startswith('_') or _scalar(value) is None: continue
            key=str(key)
            if key not in labels: labels[key]=_friendly_label(key)
            if key not in order: order.append(key)
        c={}
        for key in order:
            val=_scalar(rec.get(key, ''))
            if val is not None: c[key]=val
        clean.append(c)
    return order, labels, clean


def render_export(applet, fmt='txt'):
    records = applet.export_records()
    order, labels, records = _schema(records, applet.export_columns())
    sections = applet.export_sections() or {}
    title = applet.name
    fmt = (fmt or 'txt').lower()
    if fmt == 'json':
        return json.dumps({'title': title, 'sections': sections, 'items': records}, indent=2, ensure_ascii=False) + '\n'
    if fmt == 'csv':
        stream=io.StringIO(newline='')
        w=csv.writer(stream); w.writerow([labels.get(k, _friendly_label(k)) for k in order])
        for rec in records: w.writerow([rec.get(k, '') for k in order])
        return stream.getvalue()
    if fmt in ('md','markdown'):
        lines=[f"# {title}", ""]
        for heading,text in sections.items(): lines += [f"## {heading}", "", str(text).rstrip(), ""]
        if order:
            lines += ["| " + " | ".join(labels.get(k,_friendly_label(k)) for k in order) + " |",
                      "| " + " | ".join('---' for _ in order) + " |"]
            for rec in records:
                vals=[str(rec.get(k,'')).replace('|','\\|').replace('\n','<br>') for k in order]
                lines.append("| " + " | ".join(vals) + " |")
        return "\n".join(lines).rstrip() + "\n"
    lines=[f"LinSpectacles - {title}", "="*max(12,len(title)+12), ""]
    for heading,text in sections.items(): lines += [str(heading), '-'*len(str(heading)), str(text).rstrip(), ""]
    lines += [f"Items: {len(records)}", ""]
    for i,rec in enumerate(records,1):
        lines += [f"Item {i}", '-'*(5+len(str(i)))]
        for key in order:
            if key in rec: lines.append(f"{labels.get(key,_friendly_label(key))}: {rec.get(key,'')}")
        lines.append('')
    return "\n".join(lines).rstrip()+"\n"


def slug(text):
    s=re.sub(r'[^A-Za-z0-9._-]+','-',str(text).strip()).strip('-').lower()
    return s or 'linspectacles-export'


def standalone(factory, applet_dir=None):
    """Run one TUI applet using the same visual grammar as the suite host."""
    applet = factory(applet_dir=applet_dir)
    def _run(stdscr):
        curses.curs_set(0); stdscr.keypad(True)
        curses.start_color()
        try: curses.use_default_colors()
        except Exception: pass
        curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_CYAN)
        curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_BLACK, curses.COLOR_WHITE)
        applet.on_activate()
        while True:
            stdscr.clear(); h,w=stdscr.getmaxyx()
            if h<12 or w<60:
                try: stdscr.addstr(0,0,'Terminal window is too small (Min: 60x12)!'[:w-1])
                except curses.error: pass
                stdscr.refresh(); key=stdscr.getch()
                if key in (ord('q'),ord('Q')): break
                continue
            _draw_single(stdscr, applet, h, w)
            stdscr.timeout(1000 if applet.live else -1)
            key=stdscr.getch()
            if key == -1:
                applet.tick(); continue
            if key in (ord('q'),ord('Q')): break
            if key == curses.KEY_UP and applet.current_row>0: applet.current_row-=1
            elif key == curses.KEY_DOWN and applet.records and applet.current_row<len(applet.records)-1: applet.current_row+=1
            elif key in (ord('r'),ord('R')): applet.refresh(); applet.current_row=0; applet.top_row=0
            else: applet.handle_key(key)
        applet.on_deactivate()
    try: curses.wrapper(_run)
    except KeyboardInterrupt: pass


def _draw_single(stdscr, applet, h, w):
    try:
        stdscr.attron(curses.color_pair(2)|curses.A_BOLD)
        title=' LinSpectacles - Linux Inspection Suite TUI '
        stdscr.addstr(0,0,title.ljust(w-1)[:w-1]); stdscr.attroff(curses.color_pair(2)|curses.A_BOLD)
        stdscr.attron(curses.color_pair(3)|curses.A_BOLD)
        tab=f" [1] {applet.name} "
        stdscr.addstr(1,0,tab[:w-1]); stdscr.attroff(curses.color_pair(3)|curses.A_BOLD)
    except curses.error: pass
    _draw_body(stdscr, applet, h, w)
    footer=f" [↑/↓] Navigate | [r] {applet.action_label()}"
    extra=applet.extra_footer()
    if extra: footer += ' | ' + extra
    footer += ' | [q] Quit '
    try:
        stdscr.attron(curses.color_pair(2)); stdscr.addstr(h-1,0,footer.ljust(w-1)[:w-1]); stdscr.attroff(curses.color_pair(2))
    except curses.error: pass
    stdscr.refresh()


def _draw_body(stdscr, applet, h, w):
    records=applet.get_records(); list_width=int(w*0.38); info_width=w-list_width-1; max_rows=h-5
    if records:
        applet.current_row=max(0,min(applet.current_row,len(records)-1))
        if applet.current_row<applet.top_row: applet.top_row=applet.current_row
        elif applet.current_row>=applet.top_row+max_rows: applet.top_row=applet.current_row-max_rows+1
    for idx in range(applet.top_row,min(applet.top_row+max_rows,len(records))):
        y=3+(idx-applet.top_row); line=applet.format_row(records[idx],list_width-1).ljust(list_width-1)
        try:
            if idx==applet.current_row: stdscr.attron(curses.color_pair(1))
            stdscr.addstr(y,0,line[:list_width])
            if idx==applet.current_row: stdscr.attroff(curses.color_pair(1))
        except curses.error: pass
    try:
        stdscr.vline(2,list_width,curses.ACS_VLINE,h-3)
        stdscr.attron(curses.color_pair(2)|curses.A_BOLD)
        heading=applet.metadata_heading()
        stdscr.addstr(2,list_width+2,heading.ljust(info_width-2)[:info_width-2])
        stdscr.attroff(curses.color_pair(2)|curses.A_BOLD)
    except curses.error: pass
    selected=records[applet.current_row] if records else None
    text=applet.details(selected)
    for i,line in enumerate(str(text).split('\n')[:h-6]):
        try: stdscr.addstr(3+i,list_width+2,line[:max(0,info_width-3)])
        except curses.error: pass
