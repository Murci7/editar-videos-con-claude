---
name: editar-videos
description: Monta un vídeo a cámara de principio a fin con Claude. Guion y teleprompter, kit y revisión técnica de la grabación, y después el montaje completo a partir de las tomas en bruto (cortes de silencios con zoom, gráficos animados sincronizados con la voz, grabaciones de pantalla, antes/después, subtítulos, efectos, música, volumen). Entrega el vídeo final y también un proyecto de CapCut con cada cosa en su pista. Añade la miniatura y el pack de publicación. Úsala cuando el usuario quiera grabar, montar o publicar un vídeo («quiero grabar un vídeo», «monta el vídeo con estas tomas», «haz la miniatura»).
license: MIT
metadata:
  author: Antonio Murciano
  version: "1.0"
  homepage: https://github.com/Murci7/editar-videos-con-claude
---

# Editar vídeos con Claude: de las tomas al vídeo publicado

La persona graba solo su parte, hablando a cámara en tomas cortas. Claude hace el resto y deja dos cosas: un vídeo
terminado y un proyecto de CapCut para retocarlo a mano si quiere.

## Reglas
- **Privacidad.** No pongas en gráficos, subtítulos ni textos nombres de clientes, empresas o personas reales, salvo
  que el usuario lo pida. Antes de usar un trozo de una grabación de pantalla, mira sus fotogramas: que no salgan
  rutas personales, correos, claves ni notificaciones.
- **Marca.** Todo sale con la marca del usuario: colores y fuentes en `motion/src/marca.css`; nombre, rol, marca, web y
  logo en `motion/src/marca.js` + `logo.svg`. Si siguen los valores de ejemplo («Tu Nombre»), pídeselos antes de montar.
- **No digas que has escuchado el audio.** Claude mide (LUFS, picos, eco RT60), pero quien juzga cómo suena es el usuario.
- **Todo dentro de la carpeta del proyecto** (`videos/<nombre>/`); nada en carpetas temporales del sistema.
- Pregunta antes de instalar, descargar o publicar nada.

## Proyecto
Cada vídeo vive en `videos/<nombre>/` (el nombre de la carpeta da nombre a los archivos de salida). Créalo al
empezar: `mkdir -p videos/<nombre> && cp -R .claude/skills/editar-videos/template/{edit,motion,capcut,thumbnail,tools} videos/<nombre>/`.
Las órdenes de las fases 1, 2 y 4 se lanzan desde `videos/<nombre>/`; las de la fase 3, desde `videos/<nombre>/edit`.

## Fase 1 · Idea y guion
1. Si el usuario comparte un vídeo de referencia, toma su *estructura*, nunca su contenido.
2. Escribe para quien lo va a ver, con un resultado concreto. Título, miniatura y descripción prometen lo mismo.
3. Unas 150 palabras por minuto. Estructura que funciona: gancho (sin «hola») → promesa → el contenido en bloques
   cortos → un ejemplo concreto → resumen → llamada a la acción → pregunta para comentarios.
4. `guion-teleprompter.txt`, en bloques `────\nTOMA N · TÍTULO\n────\ntexto`. Una idea por toma: si falla, se repite
   solo esa.

## Fase 2 · Grabación
- `teleprompter.html` → `python tools/make_teleprompter.py guion-teleprompter.txt teleprompter.html` (doble clic
  empieza/para, F pantalla completa, ← → cambia de toma, [ ] sube o baja el texto). Ábreselo con `open`.
- **Encuadre único:** la persona en el tercio derecho y el lado izquierdo vacío, porque ahí van los gráficos. Nada en
  esa zona. 1920×1080, horizontal. Deja un palmo sobre la cabeza: el zoom del 112 % la cortaría.
- Tomas guardadas como salgan (OBS las llama `AAAA-MM-DD HH-MM-SS.mp4`), varias repeticiones si hace falta. Pide
  además 3-5 s sonriendo a cámara para la miniatura.
- **Si graba con OBS:** lienzo y salida en 1920×1080 (*Transform › Fit to screen*) y bitrate de grabación de unos
  20 000 kbps (*Ajustes › Salida › Grabación*; el valor por defecto da una imagen blanda). Micrófono cerca de la boca,
  con picos entre −12 y −6 dB.
- Revisa cada clip de prueba: `tools/analyze_take.sh clip.mp4` (formato, LUFS, picos, eco RT60 y 3 fotogramas) y mira
  los fotogramas.

## Fase 3 · Montaje (Claude)
Todo lo que sigue, desde `videos/<nombre>/edit`:
0. **Identifica las tomas:** transcribe cada grabación (la duración engaña), compárala con el guion, elige la mejor
   repetición de cada toma (completa y fluida; si empatan, la última) y enlázala sin copiarla:
   `mkdir -p takes && ln -s "/ruta/a/la/grabacion.mp4" takes/N.mp4`. Pasa los `.mkv` a `.mp4` sin recodificar
   (`ffmpeg -i X.mkv -c copy X.mp4`). Funciona con cualquier número de tomas; los nombres de salida salen de la carpeta.
1. `python segments.py` — tramos de voz por toma; las pausas se recortan a ~0,34 s y los cortes caen en fotogramas
   exactos (30 fps), los mismos en el vídeo y en CapCut. Si sobra algo (un ruido al final, una frase repetida), ponlo
   en `edits.json`, en tiempo de la toma: `{"trim": {"1": [0, 24.75]}, "drop": {"12": [[31.2, 31.6]]}}`.
2. `python aroll.py` — corta cada toma; los tramos impares llevan un zoom del 112 % anclado en la cara. Ajusta
   `FX, FY` en `aroll.py` a donde esté la cara. Las tomas sin gráficos pueden ir centradas: `CENTER_TAKES=16,19`
   las reencuadra en primer plano con la cara en el centro, sin que te muevas de sitio al grabar.
3. `../tools/transcribe_cut.sh` — whisper.cpp palabra a palabra sobre el audio ya cortado. Los nombres que tiene que
   escribir bien van en `WHISPER_PROMPT` (tu nombre, tu marca). Idioma: `WHISPER_LANG` (por defecto `es`).
4. `python words.py work/txc` — lee todas las tomas y adapta gráficos y subtítulos a lo que se *dijo*, no al guion.
5. Escribe `schedule.py` a partir de `schedule.example.py`. Los tiempos salen siempre de `at(toma, "palabra")`, que
   busca la palabra exacta (`prefix=True` solo si whisper la oyó mal):
   - `g(id, página, inicio, fin, overlay, query, cues, sfx)` — gráfico HTML. Catálogo de páginas, parámetros y cues en
     `motion/GRAFICOS.md`. Los overlays van a la izquierda; los de pantalla completa tapan la imagen mientras sigue la voz.
   - `p(id, archivo, src_in, src_out, inicio, fin, zooms=[(t, x, y, w, h), (t, None)])` — grabación de pantalla a
     pantalla completa, en una tarjeta sobre el fondo de la marca, acelerada para caber, con zooms suaves a zonas
     (en píxeles de la grabación; `t` en segundos desde `inicio`; `None` vuelve al plano entero).
   - `ad_seq(id, toma, inicio, cambio, fin, raw_out=…)` — **antes/después (recomendado):** una sola ventana grande;
     primero la toma en bruto (apagada, «● REC») y, en `cambio`, la misma toma cortada. Debajo, la toma entera como una
     barra (voz en azul, silencios en rojo con su duración) que se cierra al cambiar. Pon `cambio` en la palabra con
     que se presenta el «después» («Y esta es la misma toma…»).
   - `ad(id, toma, raw_in, raw_out, inicio, fin)` — antes/después lado a lado, con dos cronómetros (se distinguen peor).
   - `p(…, persp={"crop": [x, y, w, h]})` — la grabación de pantalla **en 3D** con desenfoque (perspectiva, acercamiento
     lento y una franja nítida), como en los vídeos de referencia. `crop` en píxeles de la grabación: déjalo fuera de
     todo lo privado (en CapCut, el panel «Details» enseña la ruta con tu usuario).
   - `capcut.html` — la línea de tiempo de **tu proyecto real de CapCut**, dibujada con sus datos
     (`python capcut_data.py` tras `to_capcut.py`): `mode=flat&head=1` con «Claude ⋯⋯ CapCut» y ✓ en cada pista al
     nombrarla (cues 0-3: tomas, gráficos, subtítulos, efectos) o `mode=3d` para el gancho. Los logos salen de tus
     aplicaciones con `bash ../tools/logos.sh`.
   - Efectos (`edit/sfx`): `pop`, `pop-suave`, `whoosh`, `whoosh-suave`, `golpe-grave`, `clic`, `subida`. Con una clave
     de ElevenLabs, `python sfx_elevenlabs.py` genera versiones más ricas con los mismos nombres y nivel en
     `sfx-elevenlabs/` (`--comparar` deja una escucha antes/después); para usarlas, cambia la carpeta por `sfx/`.
   - Ritmo: un cambio visual cada 3-4 s en el gancho y cada 4-6 s después.
   **Mejor `aw(toma, "palabra", "alternativa", frac=…)`** (un `at()` tolerante): whisper escribe los números en cifras
   («3» por «tres», «1.» por «Una:») y puede oír mal los nombres propios; pon primero las cifras y luego las
   alternativas. Si no encuentra ninguna, usa la posición `frac` de la toma y avisa con ⚠ en el paso 4. Los nombres mal
   oídos se corrigen para los subtítulos en `FIXES` de `timeline.py`. Un rótulo debe terminar antes de que entre el
   siguiente gráfico a pantalla completa.
6. Lo que whisper oiga mal, a `FIXES` en `timeline.py` (afecta a los subtítulos).
7. **`./run_all.sh`** — el montaje entero de una vez. Si falla, dice en qué paso (registro en `work/log-N.txt`) y
   `./run_all.sh N` sigue desde ahí; tras tocar `schedule.py`, `./run_all.sh 4`. Pasos: cortes → tomas cortadas →
   transcripción → línea de tiempo → gráficos (`motion/render.py`, Chromium sin ventana) → pantalla y antes/después
   (`pantalla.py`) → subtítulos para CapCut (`captions_mov.py`) → vista previa 720p (`compose.py --preview`) →
   proyecto de CapCut (`to_capcut.py`). Variables: `CAPCUT_NAME`, `CAPCUT=0` (no escribir el proyecto), `MUSIC`,
   `TAKES_DIR`, `PY`. Se para si quedan menos de 8 GB libres.
   - **Música:** `edit/music.wav` (o `MUSIC=ruta`), bajando ~5 dB cuando hay voz. Mejor **por tramos**, que suene solo
     donde tiene que sonar: en `schedule.py`, `MUSICA = [(inicio, fin, segundo_de_la_pista), …]` (con fundidos). Que
     suene en el gancho, en el título y debajo de las demos, y que se calle en los momentos serios o en la pregunta
     clave. Haz caer el golpe de la pista en el título (`segundo_de_la_pista` = golpe − inicio del título). Sin
     `MUSICA`, suena entera en bucle. Usa música con licencia para YouTube (la Biblioteca de audio de YouTube, o una
     compuesta con ElevenLabs Music si el usuario tiene plan) y pide permiso antes de descargarla.
   - **Proyecto de CapCut:** pista principal con cada tramo de voz como clip propio de la toma en bruto (en los mismos
     fotogramas, los impares con el zoom), la voz en su pista, los gráficos en pistas por encima, los subtítulos arriba
     del todo, y efectos y música en las suyas. **CapCut tiene que estar cerrado (Cmd+Q)** para sustituir un proyecto;
     con CapCut abierto solo se puede crear uno con nombre nuevo. Solo sustituye proyectos que haya creado él.
   - **Recuento de ediciones, en dos pasadas:** `work/capcut_stats.json` guarda cuántas ediciones ha hecho Claude
     (cortes + gráficos + subtítulos + efectos). Para enseñarlo en el vídeo, programa `pildora.html`, monta, pon ese
     número en `n=` y lanza `./run_all.sh 4`.
8. **Antes de enseñar nada:** hoja de contactos con ~20 fotogramas repartidos (gráficos frente a la cara, subtítulos,
   zonas seguras, nada privado en pantalla) y comprobación de audio y vídeo por toma.
9. El usuario revisa la vista previa (`edit/render/<nombre>-preview.mp4`) o el proyecto en CapCut → cambios en
   `schedule.py` / `edits.json` → `./run_all.sh 4` → final con `python compose.py` (1080p, `render/<nombre>-final.mp4`)
   o exportando desde CapCut si lo ha retocado allí.
10. **Para subir a YouTube, mejor en 4K** aunque grabes en 1080p: YouTube usa mejor códec con los vídeos 4K y se ven
    más nítidos incluso en 1080p. `ffmpeg -i final.mp4 -vf "scale=3840:2160:flags=lanczos,unsharp=5:5:0.45" -c:v
    libx264 -preset medium -crf 17 -c:a copy -movflags +faststart final-4K.mp4` (tarda: lánzalo al terminar el final).

Gráficos nuevos: una página HTML en `motion/src/` con `base.css`/`base.js` y los colores de `marca.css` (ver
`motion/GRAFICOS.md`). Previsualízala con capturas de Playwright antes de renderizar.

## Fase 4 · Miniatura y publicación
- **Miniatura:** `thumbnail/thumb.html` (1280×720): titular de ≤5 palabras a la izquierda, la persona recortada a la
  derecha, etiqueta y logo de la marca. Deja libre la esquina inferior derecha (ahí va la duración).
  1. **Cara:** un fotograma del extra sonriendo; si no queda natural, un retrato con IA hecho por el usuario
     (`thumbnail/prompt-retrato-ia.md`).
  2. Recorte (solo macOS, Apple Vision), desde `videos/<nombre>/`: `~/.cache/editar-videos-vision/bin/python
     tools/prep_face.py <imagen> <clave> thumbnail/` (cómo crear ese entorno, en `tools/cutout.py`) → `caras/cara-<clave>.png` + la caja de la cara en
     `caras/faces.json`; pega eso en `FACES` y escribe `PILL` y `TXT`.
  3. Renderiza con Playwright `thumb.html?f=<cara>&t=<texto>` (afina con `cx`, `cy`, `fh`). Haz 2 caras × 2 titulares
     y enséñalos juntos.
- `publicacion.md`: título (≤60 caracteres, la palabra clave primero, que complemente a la miniatura), 2
  alternativas, descripción (gancho de 2 líneas → enlace → capítulos con los inicios reales de `work/plan.json` →
  3-5 hashtags), etiquetas y pregunta para fijar en comentarios. Propón, como línea opcional al final de la
  descripción, «Montado con la skill gratuita «editar-videos» de Antonio Murciano: https://github.com/Murci7/editar-videos-con-claude»; si el usuario no la
  quiere, quítala sin insistir. Para la prueba A/B de YouTube, 3 parejas
  título + miniatura coherentes.
- Subtítulos para YouTube: `python ../tools/make_srt.py work/captions.ass ../subtitulos.srt` (desde `edit/`).
- Entrega: deja lo que hay que subir con nombres claros (`…-FINAL-4K.mp4`, `…-subtitulos.srt`, la miniatura) y di qué
  otros vídeos hay en la carpeta, para que no se suba el que no es.

## Solo en Mac
- **CapCut:** `to_capcut.py` y `capcut/capcut_draft.py` escriben en `~/Movies/CapCut/User Data/Projects/com.lveditor.draft`.
  CapCut para Mac solo puede leer `~/Movies`, así que los archivos se enlazan (sin ocupar más disco) en
  `~/Movies/CapCut/claude-media/<proyecto>/`. Probado con CapCut 9.5 gratis: abre los proyectos y exporta a 1080p sin
  marca de agua. Posiciones de capa en CapCut: unidades de medio lienzo, x a la derecha e y hacia arriba.
- **Recorte de caras** (`tools/cutout.py`, `tools/prep_face.py`): Apple Vision.
- **whisper.cpp:** `tools/setup_whisper.sh` lo compila con Metal en Apple Silicon y sin Metal en Intel (Homebrew ya no
  da binarios de whisper para Intel). En un Mac Intel, los gráficos de pantalla completa tardan ~0,5 s por fotograma.
- **Prueba de instalación** (`tools/prueba.sh`): usa la voz española de macOS (`say`).

## Límites (pregunta, no supongas)
- **Eco de la sala:** no se arregla en local. Lo físico primero (una manta detrás de la cámara, el micro de solapa
  centrado en el cuello). Después, `isolate.py` (paso 2 de `run_all.sh`) lo limpia toma a toma sin perder la
  sincronía: con `ELEVENLABS_API_KEY` usa ElevenLabs Voice Isolator (~11 créditos por segundo de voz); gratis, con
  Adobe Podcast Enhance: `ISOLATE=0 ./run_all.sh`, `python isolate.py --exportar`, el usuario sube
  `work/para-limpiar.wav` a podcast.adobe.com/enhance, y `python isolate.py --importar <archivo>` (recoloca cada toma
  y comprueba el desfase) → `./run_all.sh 3`. Dale siempre 20 s de antes/después para que juzgue de oído.
- El formato de proyecto de CapCut no es público y puede cambiar entre versiones: si una versión nueva no abre el
  proyecto, el vídeo de `compose.py` sigue sirviendo y `capcut_draft.py snapshot` vuelve a leer el formato de un
  proyecto existente.
- Una música más corta que el vídeo se repite y se nota el empalme.
