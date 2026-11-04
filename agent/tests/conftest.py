import sys
from pathlib import Path

AGENT = Path(__file__).resolve().parents[1]
REPO = AGENT.parent
# agent/ for flat imports, repo root for pipeline.py
for p in (REPO, AGENT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
