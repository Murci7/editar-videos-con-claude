#!/bin/bash
# Transcribe las tomas YA CORTADAS (edit/work/take_N.wav) palabra a palabra (alineación DTW) → edit/work/txc/N.json
# Uso (desde edit/): ../tools/transcribe_cut.sh N [N...]   (sin argumentos: todas las take_N.wav)
# WHISPER_PROMPT: nombres que whisper debe escribir bien en este vídeo (tu nombre, tu marca, herramientas).
D="${WHISPER_DIR:-$HOME/.cache/whisper.cpp}/build/bin"; M=$HOME/.cache/whisper-models/ggml-large-v3-turbo-q5_0.bin
PROMPT="${WHISPER_PROMPT:-YouTube, Claude, CapCut, WhatsApp, Excel.}"
TH=$(sysctl -n hw.ncpu 2>/dev/null || echo 4)
mkdir -p work/txc
TAKES="$@"; [ -z "$TAKES" ] && TAKES=$(ls work/take_*.wav | sed -E 's/.*take_([0-9]+)\.wav/\1/' | sort -n)
for i in $TAKES; do
  ffmpeg -hide_banner -loglevel error -y -i work/take_$i.wav -ac 1 -ar 16000 -c:a pcm_s16le work/txc/$i.wav
  DYLD_LIBRARY_PATH=$D $D/whisper-cli -m $M -dtw large.v3.turbo -l es -t "$TH" -ml 1 -sow -oj -of work/txc/$i \
    --prompt "$PROMPT" -f work/txc/$i.wav >/dev/null 2>&1
  rm -f work/txc/$i.wav; echo "toma $i ok"
done
