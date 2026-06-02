"""Gunicorn entry point. Run with:
    gunicorn --bind 0.0.0.0:$PORT --workers 4 --timeout 120 wsgi:app
"""
from app import app  # noqa: F401 — gunicorn reads `wsgi:app`
