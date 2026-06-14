"""
Root conftest: add all project directories to sys.path so tests can
import project modules without installing them as packages.
"""
import sys
from pathlib import Path

_ROOT = Path(__file__).parent
for _proj in ("price-recon", "alpha-pipeline", "market-data-hub", "data-onboard", "market-ops"):
    _p = _ROOT / _proj
    if _p.exists() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
