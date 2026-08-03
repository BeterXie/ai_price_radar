from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CLASSIFIER_PATH = ROOT / "apps" / "api" / "app" / "services"
if str(CLASSIFIER_PATH) not in sys.path:
    sys.path.insert(0, str(CLASSIFIER_PATH))
