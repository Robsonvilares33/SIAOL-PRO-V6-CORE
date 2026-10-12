from pathlib import Path
import sys

# Vercel executes this file from src/app.py; expose the repository root so the
# packaged lotomaster backend and its mounted static frontend are importable.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from lotomaster.api import app
