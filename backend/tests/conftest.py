"""Ensure `backend/` is on sys.path so `eval_core` resolves when running pytest from repo."""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
