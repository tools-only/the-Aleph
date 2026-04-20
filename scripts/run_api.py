from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import uvicorn
except ImportError as exc:  # pragma: no cover - optional dependency
    raise SystemExit(
        "uvicorn is required to run the Aleph API service. Install the 'service' extra first."
    ) from exc

from aleph.service import create_app


if __name__ == "__main__":
    app = create_app(root_dir=ROOT)
    uvicorn.run(app, host="0.0.0.0", port=8000)
