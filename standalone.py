#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
from pathlib import Path

APPLET_ROOT = Path(__file__).resolve().parent
if str(APPLET_ROOT) not in sys.path:
    sys.path.insert(0, str(APPLET_ROOT))

from linux_resmon.applet import run_standalone

if __name__ == "__main__":
    raise SystemExit(run_standalone())
