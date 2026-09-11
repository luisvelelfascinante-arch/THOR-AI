"""Fuerza UTF-8 en stdout/stderr en Windows.

Los prints con emojis (✅❌⏳🧠🚨) en main.py/diagnostico.py/test_*.py
crashean con UnicodeEncodeError en consolas Windows que usan cp1252
por defecto en vez de UTF-8. Se llama al principio de cada script de
entrada, antes de cualquier print.
"""

import sys


def forzar_utf8() -> None:
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
