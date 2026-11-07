#!/bin/bash
# Wait for the DTW transcripts, then timeline → graphics → 720p preview.
set -e
cd "$(dirname "$0")"
if [ -z "${PY:-}" ]; then   # the repo's .venv, searched upwards
  d="$(pwd)"; while [ "$d" != "/" ] && [ ! -x "$d/.venv/bin/python" ]; do d="$(dirname "$d")"; done
  if [ -x "$d/.venv/bin/python" ]; then PY="$d/.venv/bin/python"; else PY=python3; fi
fi
N=$($PY -c "import json; print(len(json.load(open('segments.json'))))")
until [ "$(ls work/txc/*.json 2>/dev/null | wc -l)" -ge "$N" ]; do sleep 5; done
echo "[1/3] transcripciones listas ($N tomas)"
$PY timeline.py | head -1
rm -rf work/gfx
$PY ../motion/render.py work/jobs.json work/gfx > work/render.log 2>&1
$PY pantalla.py >> work/render.log 2>&1      # screen clips + before/after bases (full-screen mp4)
echo "[2/3] gráficos renderizados: $(ls work/gfx | wc -l)"
$PY compose.py --preview > work/compose.log 2>&1
echo "[3/3] preview: $(ls render/*-preview.mp4)"
