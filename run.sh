#!/usr/bin/env bash
# Launch the Systematic Risk Macro Dashboard.
#
#   ./run.sh          -> localhost only
#   ./run.sh --lan    -> also reachable from your phone on the same network
#                        (or over Tailscale, if you have it installed)
#
# On first run this creates the virtual environment and installs dependencies;
# after that it just starts the app.

set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
  # shellcheck disable=SC1091
  source .venv/bin/activate
  echo "Installing dependencies (one-off, takes a minute)..."
  pip install --quiet --upgrade pip
  pip install --quiet -r requirements.txt
else
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

if [ "${1:-}" = "--lan" ]; then
  echo "Starting on all interfaces — reachable from other devices on this network."
  exec streamlit run app.py --server.address 0.0.0.0
else
  exec streamlit run app.py
fi
