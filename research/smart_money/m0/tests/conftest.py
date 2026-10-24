"""Pytest configuration ensuring project root is in sys.path."""

import sys
from pathlib import Path

# Project root: 宏观观察器
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
