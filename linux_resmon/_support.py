#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# LinSpectacles - Linux Inspection Suite
# Copyright (C) 2026 brunonlinespace
# GPL-3.0-or-later

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import QApplication

DARK_STYLESHEET = r"""
QMainWindow, QWidget { background-color: #1e1e1e; color: #dcdcdc; font-family: "Segoe UI", Ubuntu, sans-serif; font-size: 10pt; }
QTabWidget::pane { border: 1px solid #333333; background-color: #1e1e1e; }
QTabBar::tab { background-color: #2d2d2d; color: #aaaaaa; padding: 8px 16px; border: 1px solid #333333; border-radius: 4px; margin-right: 2px; }
QTabBar::tab:selected { background-color: #007acc; color: #ffffff; font-weight: bold; }
QTabBar::tab:hover:!selected { background-color: #3e3e42; color: #ffffff; }
QGroupBox { border: 1px solid #333333; border-radius: 6px; margin-top: 6px; padding-top: 10px; background-color: #252526; }
QLineEdit, QComboBox { background-color: #333333; color: #ffffff; border: 1px solid #454545; border-radius: 4px; padding: 4px 8px; selection-background-color: #007acc; }
QLineEdit:focus, QComboBox:focus { border: 1px solid #007acc; }
QComboBox QAbstractItemView { background-color: #252526; color: #dcdcdc; selection-background-color: #094771; selection-color: #ffffff; }
QTableWidget { background-color: #1e1e1e; alternate-background-color: #252526; color: #dcdcdc; gridline-color: #2d2d2d; border: 1px solid #333333; border-radius: 4px; }
QTableWidget::item:selected { background-color: #094771; color: #ffffff; }
QHeaderView::section { background-color: #2d2d2d; color: #ffffff; padding: 5px; border: 1px solid #333333; font-weight: bold; }
QTextEdit { background-color: #1e1e1e; color: #dcdcdc; border: 1px solid #333333; }
QPushButton { background-color: #333333; color: #ffffff; border: 1px solid #454545; border-radius: 3px; padding: 4px 8px; }
QPushButton:hover { background-color: #007acc; border-color: #007acc; }
QPushButton:pressed { background-color: #005999; }
QPushButton:disabled { background-color: #2a2a2a; color: #777777; border-color: #3a3a3a; }
QSplitter::handle { background-color: #2d2d2d; height: 3px; }
QScrollBar:vertical, QScrollBar:horizontal { background: #1e1e1e; border: none; width: 10px; height: 10px; }
QScrollBar::handle:vertical, QScrollBar::handle:horizontal { background: #424242; border-radius: 5px; }
QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover { background: #686868; }
"""

LIGHT_STYLESHEET = r"""
QMainWindow, QWidget { background-color: #f3f3f3; color: #202020; font-family: "Segoe UI", Ubuntu, sans-serif; font-size: 10pt; }
QTabWidget::pane { border: 1px solid #b8b8b8; background-color: #f3f3f3; }
QTabBar::tab { background-color: #e6e6e6; color: #4a4a4a; padding: 8px 16px; border: 1px solid #b8b8b8; border-radius: 4px; margin-right: 2px; }
QTabBar::tab:selected { background-color: #0b64a0; color: #ffffff; font-weight: bold; }
QTabBar::tab:hover:!selected { background-color: #dcecf8; color: #202020; }
QGroupBox { border: 1px solid #b8b8b8; border-radius: 6px; margin-top: 6px; padding-top: 10px; background-color: #fafafa; }
QLineEdit, QComboBox { background-color: #ffffff; color: #202020; border: 1px solid #aaaaaa; border-radius: 4px; padding: 4px 8px; selection-background-color: #0b64a0; selection-color: #ffffff; }
QLineEdit:focus, QComboBox:focus { border: 1px solid #0b64a0; }
QComboBox QAbstractItemView { background-color: #ffffff; color: #202020; selection-background-color: #0b64a0; selection-color: #ffffff; }
QTableWidget { background-color: #ffffff; alternate-background-color: #f0f0f0; color: #202020; gridline-color: #d0d0d0; border: 1px solid #b8b8b8; border-radius: 4px; }
QTableWidget::item:selected { background-color: #0b64a0; color: #ffffff; }
QHeaderView::section { background-color: #e6e6e6; color: #202020; padding: 5px; border: 1px solid #b8b8b8; font-weight: bold; }
QTextEdit { background-color: #ffffff; color: #202020; border: 1px solid #b8b8b8; }
QPushButton { background-color: #f7f7f7; color: #202020; border: 1px solid #aaaaaa; border-radius: 3px; padding: 4px 8px; }
QPushButton:hover { background-color: #dcecf8; border-color: #0b64a0; }
QPushButton:pressed { background-color: #c5e0f2; }
QPushButton:disabled { background-color: #eeeeee; color: #999999; border-color: #cccccc; }
QSplitter::handle { background-color: #c8c8c8; height: 3px; }
QScrollBar:vertical, QScrollBar:horizontal { background: #f3f3f3; border: none; width: 10px; height: 10px; }
QScrollBar::handle:vertical, QScrollBar::handle:horizontal { background: #b0b0b0; border-radius: 5px; }
QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover { background: #8e8e8e; }
"""

_DARK_THEME = {
    "window": "#1e1e1e",
    "text": "#dcdcdc",
    "metadata_bg": "#1e1e1e",
    "source_key": "#9cdcfe",
    "status_bg": "#252526",
    "status_fg": "#dcdcdc",
    "border": "#666666",
}

_LIGHT_THEME = {
    "window": "#f3f3f3",
    "text": "#202020",
    "metadata_bg": "#ffffff",
    "source_key": "#17698b",
    "status_bg": "#e9eef2",
    "status_fg": "#303030",
    "border": "#b8b8b8",
}


def system_prefers_dark():
    """Return the desktop colour-scheme preference reported by Qt."""
    app = QApplication.instance()
    if app is not None:
        try:
            scheme = app.styleHints().colorScheme()
            dark = getattr(Qt.ColorScheme, "Dark", None)
            light = getattr(Qt.ColorScheme, "Light", None)
            if dark is not None and scheme == dark:
                return True
            if light is not None and scheme == light:
                return False
        except Exception:
            pass
        try:
            color = app.palette().color(QPalette.ColorRole.Window)
            return color.lightnessF() < 0.5
        except Exception:
            pass
    return True


def adaptive_theme_palette(dark=None):
    if dark is None:
        dark = system_prefers_dark()
    return dict(_DARK_THEME if dark else _LIGHT_THEME)


def adaptive_stylesheet(dark=None):
    if dark is None:
        dark = system_prefers_dark()
    return DARK_STYLESHEET if dark else LIGHT_STYLESHEET


def install_adaptive_app_theme(app):
    """Apply the matching LinSpectacles stylesheet and follow Qt scheme changes."""
    state = {"dark": None}

    def refresh(*_args):
        dark = system_prefers_dark()
        if state["dark"] == dark:
            return
        state["dark"] = dark
        app.setStyleSheet(adaptive_stylesheet(dark))

    refresh()
    try:
        signal = app.styleHints().colorSchemeChanged
        signal.connect(refresh)
        app._linspectacles_theme_refresh = refresh
    except Exception:
        pass
    return refresh


# Backward name retained for any source-local consumers.
STANDALONE_STYLESHEET = DARK_STYLESHEET
