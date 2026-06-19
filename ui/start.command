#!/bin/bash
# Double-click this file (macOS) to set up and launch the Card Maker UI.
DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="$(command -v python3 || command -v python)"
if [ -z "$PYTHON" ]; then
  echo "Python 3 is required but was not found. Please install it from https://www.python.org/downloads/"
  read -r -p "Press Enter to close."
  exit 1
fi
"$PYTHON" "$DIR/run.py"
