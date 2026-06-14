"""Add price-recon project root to sys.path for test imports."""
import sys
from pathlib import Path
_proj = Path(__file__).parent.parent
if str(_proj) not in sys.path:
    sys.path.insert(0, str(_proj))
