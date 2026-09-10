"""Configuración de logging, extraída de main.py (antes vivía inline)."""

import logging
import os
import sys

from core.config import rutas


def configurar_logging():
    os.makedirs(os.path.dirname(rutas.LOG_PATH), exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        handlers=[
            logging.FileHandler(rutas.LOG_PATH, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
