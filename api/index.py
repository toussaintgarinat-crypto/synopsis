# api/index.py
"""Point d'entrée Vercel — réexporte l'application FastAPI de main.py."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from main import app  # noqa: E402,F401
