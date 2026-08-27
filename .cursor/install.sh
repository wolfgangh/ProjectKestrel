#!/usr/bin/env bash
#
# Cloud Agent environment bootstrap for Project Kestrel.
#
# Idempotent: safe to re-run. Installs system libraries, creates a Python
# virtual environment with the runtime dependencies, and best-effort fetches
# the Git LFS model weights.
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

# ── System packages ────────────────────────────────────────────────────────
# - python3.12-venv / python3-dev : virtualenv + C-extension builds
# - libimage-exiftool-perl         : `exiftool` (PyExifTool backend)
# - python3-gi + gir1.2-webkit2-4.1 + libwebkit2gtk-4.1-0 : the GTK/WebKit2
#   backend pywebview needs to open the desktop window on Linux
sudo apt-get update -qq
sudo apt-get install -y --no-install-recommends \
  python3.12-venv \
  python3-dev \
  libimage-exiftool-perl \
  python3-gi \
  python3-gi-cairo \
  gir1.2-gtk-3.0 \
  gir1.2-webkit2-4.1 \
  libwebkit2gtk-4.1-0

# ── Python virtual environment ─────────────────────────────────────────────
# --system-site-packages lets the venv import the system PyGObject / WebKit2
# introspection bindings (there is no pip wheel for the GTK backend).
if [ ! -d .venv ]; then
  python3 -m venv --system-site-packages .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pytest  # dev / test dependency (not shipped in requirements.txt)

# ── Model weights (Git LFS) ────────────────────────────────────────────────
# The ONNX model weights are stored in Git LFS. Fetching may fail if the
# repository's LFS bandwidth budget is exhausted; the app still starts in
# browse-only mode without them (analysis requires the weights).
git lfs install --local || true
if ! git lfs pull; then
  echo "WARNING: 'git lfs pull' failed (LFS budget may be exhausted)." >&2
  echo "         ML model weights are unavailable; the app runs in browse-only mode." >&2
fi

echo "Kestrel environment ready. Run: source .venv/bin/activate && DISPLAY=:1 python analyzer/visualizer.py"
