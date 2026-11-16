"""Vercel Serverless Function entrypoint for FastAPI backend."""

import os
import sys
from pathlib import Path

# Ensure project root is at the beginning of sys.path so 'src' and modules resolve
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.api import app

# Expose app for Vercel's ASGI runner
__all__ = ["app"]
