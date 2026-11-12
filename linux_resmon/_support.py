#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2026 brunonlinespace
# GPL-3.0-or-later

STANDALONE_STYLESHEET = r"""
QMainWindow, QWidget { background-color: #1e1e1e; color: #dcdcdc; font-family: "Segoe UI", Ubuntu, sans-serif; font-size: 10pt; }
QTabWidget::pane { border: 1px solid #333333; background-color: #1e1e1e; }
QTabBar::tab { background-color: #2d2d2d; color: #aaaaaa; padding: 8px 16px; border: 1px solid #333333; border-radius: 4px; margin-right: 2px; }
QTabBar::tab:selected { background-color: #007acc; color: #ffffff; font-weight: bold; }
QTabBar::tab:hover:!selected { background-color: #3e3e42; color: #ffffff; }
QGroupBox { border: 1px solid #333333; border-radius: 6px; margin-top: 6px; padding-top: 10px; background-color: #252526; }
QLineEdit { background-color: #333333; color: #ffffff; border: 1px solid #454545; border-radius: 4px; padding: 4px 8px; selection-background-color: #007acc; }
QLineEdit:focus { border: 1px solid #007acc; }
QTableWidget { background-color: #1e1e1e; color: #dcdcdc; gridline-color: #2d2d2d; border: 1px solid #333333; border-radius: 4px; }
QTableWidget::item:selected { background-color: #094771; color: #ffffff; }
QHeaderView::section { background-color: #2d2d2d; color: #ffffff; padding: 5px; border: 1px solid #333333; font-weight: bold; }
QPushButton { background-color: #333333; color: #ffffff; border: 1px solid #454545; border-radius: 3px; padding: 4px 8px; }
QPushButton:hover { background-color: #007acc; border-color: #007acc; }
QPushButton:pressed { background-color: #005999; }
QSplitter::handle { background-color: #2d2d2d; height: 3px; }
QScrollBar:vertical, QScrollBar:horizontal { background: #1e1e1e; border: none; width: 10px; height: 10px; }
QScrollBar::handle:vertical, QScrollBar::handle:horizontal { background: #424242; border-radius: 5px; }
QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover { background: #686868; }
"""
