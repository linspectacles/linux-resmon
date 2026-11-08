#!/usr/bin/env python3
import sys
from pathlib import Path

APPLET_ROOT = Path(__file__).resolve().parent
IMPLEMENTATION_ROOT = APPLET_ROOT / "linux_resmon"
if str(APPLET_ROOT) not in sys.path:
    sys.path.insert(0, str(APPLET_ROOT))

from linux_resmon.tui_applet import create_tui_applet
from linux_resmon._tui_support import standalone

if __name__ == "__main__":
    standalone(create_tui_applet, IMPLEMENTATION_ROOT)
