#!/usr/bin/env python3
"""One-step launcher for the Card Maker UI.

Run this with any Python 3 (``python ui/run.py`` or double-click the
``start`` script for your OS). It will, on first run:

  1. create a virtual environment at the repository root (``venv/``),
  2. install the project + UI dependencies into it,
  3. start the web server and open it in your browser.

On later runs it skips straight to launching, so startup is fast.
"""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VENV_DIR = REPO_ROOT / "venv"

HOST = "127.0.0.1"
PORT = 5000

# Dependencies (import name) that must be present before we can launch.
REQUIRED_MODULES = ("flask", "PIL", "matplotlib", "mtg_parser", "pypdfium2")


def venv_python() -> Path:
    """Path to the Python interpreter inside the project virtual environment."""
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def running_in_target_venv() -> bool:
    try:
        return Path(sys.executable).resolve() == venv_python().resolve()
    except OSError:
        return False


def create_venv() -> None:
    print("Creating virtual environment (one-time setup)...")
    subprocess.check_call([sys.executable, "-m", "venv", str(VENV_DIR)])


def dependencies_present() -> bool:
    return all(importlib.util.find_spec(name) is not None for name in REQUIRED_MODULES)


def install_dependencies() -> None:
    print("Installing dependencies — the first run can take a few minutes...")
    pip_install = [sys.executable, "-m", "pip", "install", "-q"]
    subprocess.check_call(pip_install + ["-r", str(REPO_ROOT / "requirements.txt")])
    subprocess.check_call(pip_install + ["-r", str(REPO_ROOT / "ui" / "requirements.txt")])


def relaunch_in_venv() -> int:
    """Re-run this script using the venv's interpreter and wait for it to finish."""
    return subprocess.call([str(venv_python()), str(Path(__file__).resolve()), *sys.argv[1:]])


def launch_app() -> None:
    import threading
    import webbrowser

    os.environ.setdefault("MPLBACKEND", "Agg")
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

    from ui.app import app

    url = f"http://{HOST}:{PORT}"
    print(f"\nCard Maker UI is starting at {url}")
    print("Your browser should open automatically.")
    print("Leave this window open while you use the app. Press Ctrl+C (or close it) to stop.\n")

    threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    app.run(host=HOST, port=PORT, threaded=True)


def main() -> int:
    if running_in_target_venv():
        if not dependencies_present():
            install_dependencies()
        launch_app()
        return 0

    # Bootstrapping with the user's system Python: prepare the venv, then re-launch.
    try:
        if not venv_python().exists():
            create_venv()
        return relaunch_in_venv()
    except subprocess.CalledProcessError as exc:
        print(f"\nSetup failed: {exc}")
        print("Please ensure Python 3 and an internet connection are available, then try again.")
        return exc.returncode or 1


if __name__ == "__main__":
    raise SystemExit(main())
