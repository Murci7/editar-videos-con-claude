#!/bin/bash
# The whole edit in one go, once schedule.py is written:
#   1 segments → 2 aroll + eco limpio (ElevenLabs, isolate.py) → 3 transcribe → 4 timeline → 5 graphics (HTML) → 6 pantalla / antes-después
#   → 7 captions.mov → 8 compose --preview (720p) → 9 CapCut project + edit count
# Stops at the first error and says which step failed (full output in work/log-<step>.txt).
# Usage (from anywhere): edit/run_all.sh [first-step]      e.g. ./run_all.sh 4  after changing schedule.py
# env: TAKES_DIR (default: takes) · PY (python with Playwright + Pillow; default: the nearest .venv above, else python3) · ISOLATE=0 (sin limpiar el eco con ElevenLabs)
#      CAPCUT_NAME (draft name) · CAPCUT=0 (count the edits but don't write the CapCut project) · MUSIC (music.wav)
#      WHISPER_PROMPT (names to spell right) · TRANSCRIBE (path to transcribe_cut.sh, found by itself)
set -uo pipefail
cd "$(dirname "$0")"
if [ -z "${PY:-}" ]; then   # the repo's .venv (INSTALL.md creates it), searched upwards
  d="$(pwd)"; while [ "$d" != "/" ] && [ ! -x "$d/.venv/bin/python" ]; do d="$(dirname "$d")"; done
  if [ -x "$d/.venv/bin/python" ]; then PY="$d/.venv/bin/python"; else PY=python3; fi
fi
export TAKES_DIR="${TAKES_DIR:-takes}"
# WHISPER_PROMPT (optional): names whisper should spell right in this video, e.g. "Claude, CapCut, YouTube."
FROM="${1:-1}"
mkdir -p work

# transcribe_cut.sh: <project>/tools (copied from the template), else the skill's template/tools in a folder above
TRANSCRIBE="${TRANSCRIBE:-}"
[ -z "$TRANSCRIBE" ] && [ -f ../tools/transcribe_cut.sh ] && TRANSCRIBE="$(cd .. && pwd)/tools/transcribe_cut.sh"
d="$(cd .. && pwd)"
while [ -z "$TRANSCRIBE" ] && [ "$d" != "/" ]; do
  for c in "$d"/.claude/skills/*/template/tools/transcribe_cut.sh; do
    [ -f "$c" ] && { TRANSCRIBE="$c"; break; }
  done
  d="$(dirname "$d")"
done

space() {   # heavy steps need room: stop below 8 GB free
  local free; free=$(df -g /System/Volumes/Data 2>/dev/null | awk 'NR==2 {print $4}')
  [ -n "$free" ] && [ "$free" -lt 8 ] && { echo "✗ Solo quedan ${free} GB libres en el disco (mínimo 8). Libera espacio y repite: ./run_all.sh $1" >&2; exit 1; }
  return 0
}
step() {    # step <n> <name> <command...>
  local n="$1" name="$2"; shift 2
  [ "$n" -lt "$FROM" ] && return 0
  space "$n"
  echo "▶ [$n/9] $name"
  if ! "$@" > "work/log-$n.txt" 2>&1; then
    echo "✗ Falló el paso $n ($name). Últimas líneas de work/log-$n.txt:" >&2
    tail -n 12 "work/log-$n.txt" >&2
    echo "  Corrige y repite desde ese paso: ./run_all.sh $n" >&2
    exit 1
  fi
}
transcribe() {
  [ -n "$TRANSCRIBE" ] || { echo "no encuentro transcribe_cut.sh (define TRANSCRIBE=/ruta)"; return 1; }
  rm -rf work/txc && bash "$TRANSCRIBE" || return 1
  for w in work/take_*.wav; do   # whisper fails silently: check every take got its transcript
    n=$(basename "$w" .wav); n=${n#take_}
    [ -s "work/txc/$n.json" ] || { echo "falta la transcripción de la toma $n"; return 1; }
  done
}
cuts() { "$PY" aroll.py && "$PY" isolate.py; }
graphics() { rm -rf work/gfx && "$PY" ../motion/render.py work/jobs.json work/gfx; }
preview() { if [ -n "${MUSIC:-}" ]; then "$PY" compose.py --preview --music "$MUSIC"; else "$PY" compose.py --preview; fi; }
capcut() {
  local nb=""; [ "${CAPCUT:-1}" = 0 ] && nb="--no-build"
  if [ -n "${CAPCUT_NAME:-}" ]; then "$PY" to_capcut.py --name "$CAPCUT_NAME" $nb; else "$PY" to_capcut.py $nb; fi
}

[ "$FROM" -le 4 ] && [ ! -f schedule.py ] && { echo "✗ Falta schedule.py (cópialo de schedule.example.py y escríbelo)" >&2; exit 1; }
[ "$FROM" -le 1 ] && ! ls "$TAKES_DIR"/[0-9]*.mp4 >/dev/null 2>&1 && { echo "✗ No hay tomas N.mp4 en $TAKES_DIR" >&2; exit 1; }

step 1 "Cortes: tramos de voz por toma"              "$PY" segments.py && [ "$FROM" -le 1 ] && tail -n 1 work/log-1.txt
step 2 "Tomas cortadas (jump cuts + zoom) y eco limpio" cuts && [ "$FROM" -le 2 ] && tail -n 1 work/log-2.txt
step 3 "Transcripción palabra a palabra (Whisper)"    transcribe
step 4 "Línea de tiempo, gráficos en su palabra y subtítulos" "$PY" timeline.py && [ "$FROM" -le 4 ] && head -n 1 work/log-4.txt
step 5 "Gráficos animados"                            graphics && [ "$FROM" -le 5 ] && echo "  $(grep -c '^ok' work/log-5.txt) gráficos"
step 6 "Pantalla y antes/después"                     "$PY" pantalla.py
step 7 "Subtítulos para CapCut (captions.mov)"        "$PY" captions_mov.py
step 8 "Vista previa 720p"                            preview && [ "$FROM" -le 8 ] && tail -n 1 work/log-8.txt
step 9 "Proyecto de CapCut"                           capcut && grep -E "ediciones hechas|proyecto de CapCut|ERROR" work/log-9.txt
if [ "${CAPCUT:-1}" = 0 ]; then echo "✓ Listo. Vista previa en render/ y recuento en work/capcut_stats.json (sin proyecto de CapCut: CAPCUT=0)"; else echo "✓ Listo. Vista previa en render/, proyecto en CapCut, recuento en work/capcut_stats.json"; fi