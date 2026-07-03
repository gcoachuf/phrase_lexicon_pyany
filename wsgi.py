"""
PythonAnywhere WSGI entry point.

Web tab → WSGI configuration file:
  point it at this file, e.g.
  /home/YOURUSERNAME/phrase_lexicon_pyany/wsgi.py

Or paste these contents into the default
  /var/www/YOURUSERNAME_pythonanywhere_com_wsgi.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_HOME = Path(__file__).resolve().parent
DATA_HOME = Path.home() / "data" / "phrase_lexicon_pyany"

if str(PROJECT_HOME) not in sys.path:
    sys.path.insert(0, str(PROJECT_HOME))

DATA_HOME.mkdir(parents=True, exist_ok=True)
(DATA_HOME / "hints").mkdir(parents=True, exist_ok=True)

# Must be set before importing app / db / parser (they read DATA_DIR at import time).
os.environ.setdefault("DATA_DIR", str(DATA_HOME))
os.environ.setdefault("GOOGLE_DOC_ID", "1TX2Qd17AJ9nQ_A3QUtNSNbQ5WEqt4hfFVoaAUD_ifCw")
os.environ.setdefault("GOOGLE_DOC_TAB", "t.x0jh4b5vn4op")
os.environ.setdefault("SYNC_INTERVAL_MINUTES", "10")
os.environ.setdefault("BUILD_ID", "pythonanywhere-1")
# os.environ.setdefault("CRON_SECRET", "change-me")

from app import app as application  # noqa: E402
