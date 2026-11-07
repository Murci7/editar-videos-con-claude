#!/bin/bash
# Prueba de instalación: crea un proyecto con un clip de 10 s hecho con la voz de macOS (sin grabar nada) y lo monta
# entero: cortes, transcripción, gráficos con tu marca, pantalla, antes/después, subtítulos, vista previa 720p y,
# si CapCut está instalado y cerrado, el proyecto de CapCut «Prueba editar vídeos».
# Usage: tools/prueba.sh [carpeta]          (por defecto videos/prueba-instalacion, desde la raíz del repo)
# env: PY (python con Playwright y Pillow) · CAPCUT=0 para no crear el proyecto de CapCut
set -euo pipefail
TPL="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${1:-videos/prueba-instalacion}"
[ -e "$DEST" ] && { echo "✗ $DEST ya existe: bórrala o elige otra carpeta" >&2; exit 1; }
mkdir -p "$DEST" && DEST="$(cd "$DEST" && pwd)"
cp -R "$TPL"/{edit,motion,capcut,thumbnail,tools} "$DEST/"
mkdir -p "$DEST/edit/takes"

# 1 · clip de prueba: 1 s de silencio, una frase con pausas (voz española de macOS) y fondo con un hueco a la derecha
VOZ=$(say -v '?' | grep -E '^(Mónica|Monica|Paulina|Jorge|Juan) ' | head -n 1 | sed -E 's/ +es_.*//' || true)
[ -z "$VOZ" ] && VOZ=$(say -v '?' | grep -E ' es_[A-Z]{2} ' | head -n 1 | sed -E 's/ +es_.*//' || true)
TXT="Hola. Esto es una prueba del editor. [[slnc 900]] Si ves gráficos y subtítulos, [[slnc 700]] la instalación funciona."
if [ -n "$VOZ" ]; then say -v "$VOZ" -o "$DEST/edit/work-voz.aiff" "$TXT"; else say -o "$DEST/edit/work-voz.aiff" "$TXT"; fi
ffmpeg -hide_banner -loglevel error -y -f lavfi -i "color=c=0x9CA3AF:s=1920x1080:r=30:d=10" -i "$DEST/edit/work-voz.aiff" \
  -filter_complex "[0:v]drawbox=x=1180:y=180:w=520:h=900:color=0x4B5563:t=fill,format=yuv420p[v];[1:a]adelay=1000|1000,apad[a]" \
  -map "[v]" -map "[a]" -t 10 -c:v libx264 -crf 20 -c:a aac -ar 48000 "$DEST/edit/takes/1.mp4"
rm -f "$DEST/edit/work-voz.aiff"

# 2 · un schedule mínimo que toca todas las piezas
cat > "$DEST/edit/schedule.py" <<'PY'
s = at(1, "prueba")
g("t01-texto", "texto.html", s - 0.1, s + 2.7, True, "txt=Una *prueba*&d=2.8", sfx="pop")
g("t01-rotulo", "rotulo.html", take_start(1) + 0.3, take_start(1) + 3.3, True, "kind=nombre&d=3", sfx="pop-suave")
g("t01-titulo", "titulo.html", START["titulo"], START["titulo"] + TITLE_DUR, False, "t=Prueba de|*instalación*", sfx="whoosh")
p("t02-pantalla", "takes/1.mp4", 1.0, 7.0, START["cierre"] + 0.2, START["cierre"] + 3.2,
  zooms=[(0.5, 1180, 180, 520, 600), (2.0, None)], sfx="whoosh-suave")
ad_seq("t03-antes-despues", 1, START["cierre"] + 3.4, START["cierre"] + 5.6, START["cierre"] + 8.4, raw_out=10.0, sfx="whoosh")
g("t04-pildora", "pildora.html", START["cierre"] + 8.6, START["cierre"] + 11.6, True, "n=12&d=3", sfx="clic")
PY

# 3 · montaje
cd "$DEST/edit"
CAPCUT_NAME="Prueba editar vídeos" ./run_all.sh
echo "Vista previa: $DEST/edit/render/$(basename "$DEST")-preview.mp4"
