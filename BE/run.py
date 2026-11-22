import sys
from pathlib import Path

import uvicorn


if __name__ == "__main__":
    backend_dir = Path(__file__).resolve().parent
    sys.path.insert(0, str(backend_dir))
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
