#!/usr/bin/env bash
# One-time setup of SHARP on the GPU cluster, run from this Mac: bash 3dgs/setup_cluster.sh
# Copies the ml-sharp submodule over, builds a venv with CUDA torch, and checks the GPU.
# Afterwards set SHARP_RUNNER=cluster in backend/.env.
set -euo pipefail

HOST="${SHARP_REMOTE_HOST:-pgowr001@crisgc.engr.ucr.edu}"
REMOTE_HOME="${SHARP_REMOTE_HOME:-~/dashdigital-sharp}"
PYTHON="${SHARP_REMOTE_PYTHON:-python3}"   # needs 3.10+
SSH=(ssh -o ControlMaster=auto -o "ControlPath=~/.ssh/cm-%r@%h:%p" -o ControlPersist=4h "$HOST")

cd "$(dirname "$0")"

echo "Copying ml-sharp to $HOST:$REMOTE_HOME"
"${SSH[@]}" "mkdir -p $REMOTE_HOME/ml-sharp $REMOTE_HOME/jobs"
tar --exclude .git -C ml-sharp -cf - . | "${SSH[@]}" "tar -C $REMOTE_HOME/ml-sharp -xf -"

echo "Building the venv (pulls CUDA torch, a few GB)"
"${SSH[@]}" "cd $REMOTE_HOME && $PYTHON -m venv .venv && .venv/bin/pip install -q -U pip && .venv/bin/pip install -q ./ml-sharp"

echo "Checking the GPU"
"${SSH[@]}" "$REMOTE_HOME/.venv/bin/python -c 'import torch; print(\"CUDA:\", torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"\")'"
