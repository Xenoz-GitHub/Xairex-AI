"""Xairex entry point (Python wrapper).

Convenience entry point that allows running Xairex as:
    python xairex.py
    python xairex.py --gui
    python xairex.py --check

This is a simple wrapper that imports and delegates to app.py main().
For the PowerShell launcher, use: .\\xairex.ps1
"""

from __future__ import annotations

import sys

# Import and delegate to the main entry point in app.py
from app import main

if __name__ == "__main__":
    raise SystemExit(main())
