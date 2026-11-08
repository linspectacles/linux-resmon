#!/usr/bin/env python3
from pathlib import Path
try:
    from .tui_applet import create_tui_applet
    from ._tui_support import standalone
except ImportError:
    from tui_applet import create_tui_applet
    from _tui_support import standalone

if __name__ == '__main__':
    standalone(create_tui_applet, Path(__file__).resolve().parent)
