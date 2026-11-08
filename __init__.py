#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LinSpectacles Hub package entrypoint for Resource Monitor."""

from .linux_resmon.applet import create_applet

__all__ = ["create_applet"]
