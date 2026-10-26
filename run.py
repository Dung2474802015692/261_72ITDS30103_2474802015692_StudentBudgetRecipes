"""Launcher for the packaged .exe: starts the server and opens the browser.

Settings and data live next to the .exe: put `.env` (GEMINI_API_KEY) there,
`budget.db` is created there. Nothing secret is baked into the .exe.
"""

import os
import socket
import sys
import threading
import webbrowser
from pathlib import Path

home = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve().parent
os.chdir(home)  # budget.db is created relative to this folder
env_file = home / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition("=")
        if sep and not key.lstrip().startswith("#"):
            os.environ.setdefault(key.strip(), value.strip())

sys.path.insert(0, str(home / "src"))  # no effect when frozen, lets `python run.py` work too

import uvicorn  # noqa: E402

from app.main import app  # noqa: E402

with socket.socket() as probe:
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]  # a free port, so a busy 8000 never blocks startup

print(f"Student Budget Recipes: http://127.0.0.1:{port}  (close this window to stop)")
threading.Timer(1.5, webbrowser.open, args=(f"http://127.0.0.1:{port}",)).start()
uvicorn.run(app, host="127.0.0.1", port=port, loop="asyncio", http="h11", ws="none", log_config=None)
