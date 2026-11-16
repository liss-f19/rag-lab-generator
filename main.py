"""
Role:   Vercel Python entrypoint for the backend service; exposes the FastAPI app as `app`.
Input:  Environment variables of the deployment (DATABASE_URL, provider names, DATA_DIR).
Output: ASGI application object consumed by the Vercel Python runtime.
Flow:   Puts src/ on sys.path so the package imports without installation, pins DATA_DIR to the
        bundled data/ folder unless overridden, then builds the app through app_factory().
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("DATA_DIR", str(ROOT / "data"))

# pylint: disable=wrong-import-position
from rag_lab_generator.api.app import app_factory  # noqa: E402

app = app_factory()
