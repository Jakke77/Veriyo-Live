#!/usr/bin/env python3
"""Standalone entry point; no calendar app installation is needed."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
# Source checkout uses the parent repository's unmodified library. Packages put it locally.
for candidate in (ROOT / 'vendor', ROOT.parent / 'vendor'):
    if (candidate / 'pymeeus').is_dir():
        sys.path.insert(0, str(candidate))
        break

if __name__ == '__main__':
    from veriyo_live.app import main
    raise SystemExit(main())
