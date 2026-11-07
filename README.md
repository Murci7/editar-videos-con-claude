# Editar vídeos con Claude

*Creada por **Antonio Murciano** · [github.com/Murci7](https://github.com/Murci7)*

Una *skill* para Claude Code que monta tus vídeos a cámara. Tú grabas las tomas; Claude hace el resto y te entrega el
vídeo terminado y, además, un proyecto de CapCut con cada cosa en su pista, por si quieres retocarlo a mano.

Pensada para creadores y dueños de negocio que graban vídeos para YouTube y no quieren pasarse horas editando.

## Qué hace

```
tomas en bruto (OBS, móvil, cámara)
  → identifica cada toma y elige la mejor repetición
  → quita silencios y titubeos, con zoom en cortes alternos
  → transcribe palabra a palabra (whisper.cpp, en tu Mac)
  → coloca gráficos animados justo en la palabra en que los dices
  → grabaciones de pantalla con zoom (también en 3D con desenfoque) y un antes/después que se entiende
  → la línea de tiempo de tu proyecto de CapCut, animada con sus datos reales
  → subtítulos, efectos de sonido, música que entra y sale por tramos, volumen a −14 LUFS
  → limpieza del eco opcional (Adobe Podcast, gratis, o ElevenLabs), sin perder la sincronía
  → vista previa en 720p → vídeo final 1080p (y versión 4K para subir)
  → proyecto de CapCut: tomas, gráficos, subtítulos, voz, efectos y música en pistas separadas
  → miniatura, título, descripción con capítulos y subtítulos .srt
```

Todo se hace en tu ordenador. Lo único que necesita internet es la instalación y las fuentes de los gráficos.

## Requisitos
- **macOS** (Apple Silicon o Intel). Las partes de CapCut y del recorte de caras solo funcionan en Mac.
- **Claude Code** con un plan de pago de Claude (Pro basta).
- **CapCut** para escritorio, la versión gratuita (probado con la 9.5). Es opcional: sin él tienes igualmente el vídeo.
- **ffmpeg** (con Homebrew).
- **whisper.cpp** y su modelo `large-v3-turbo` (~550 MB). La instalación los compila y los descarga si le dices que sí.
- **Python 3** con **Playwright** (y su Chromium) y **Pillow**, en un entorno `.venv` dentro de esta carpeta.
- Unos 10 GB libres mientras montas.

## Empezar
1. Descarga esta carpeta.
2. Ábrela con Claude Code.
3. Dile: «lee INSTALL.md y configúralo».

Claude comprueba lo que ya tienes, te pregunta antes de instalar cada cosa, pone tu marca (colores, nombre, logo) y
hace un montaje de prueba con un clip de 10 segundos. Después, para tu primer vídeo: «monta el vídeo con las tomas de
esta carpeta: …».

## Qué obtienes
- La skill `editar-videos` (`.claude/skills/editar-videos/`): las instrucciones que sigue Claude, de la idea al
  vídeo publicado.
- Una plantilla de proyecto (`template/`) con el montaje completo en un solo comando (`run_all.sh`), 10 gráficos
  animados reutilizables (título, rótulo con tu nombre, texto, pasos, flujo, lista, antes/después, contador de
  ediciones, pistas de CapCut y pantalla final), 7 efectos de sonido, el generador del proyecto de CapCut, la
  miniatura y un teleprompter.
- **Tu marca en un solo sitio:** `template/motion/src/marca.css` (colores y fuentes), `marca.js` (nombre, rol, web) y
  `logo.svg`. Cámbialos una vez y salen así en todos los gráficos, la miniatura, los fondos y CapCut.

## Límites
- Vídeos a cámara en horizontal (1920×1080, 30 fps), con la persona en el tercio derecho y el lado izquierdo libre
  para los gráficos.
- Subtítulos y textos pensados para español; whisper admite otros idiomas (`WHISPER_LANG`).
- No inventa planos que no grabaste. El eco de la sala se limpia con un servicio externo (Adobe Podcast o
  ElevenLabs), siempre sincronizado con la imagen.
- El formato de proyecto de CapCut no es público: puede romperse con una versión nueva de CapCut. El vídeo final no
  depende de CapCut.
- La versión gratuita de CapCut exporta a 1080p; la versión 4K para YouTube se saca con ffmpeg.
- Montar lleva tiempo de máquina, casi todo en renderizar gráficos: en un Mac Intel, 10 s de gráfico a pantalla
  completa tardan unos 2,5 minutos.
- Revisa siempre la vista previa antes de publicar.

## Autor y licencia
Creada por Antonio Murciano. MIT, ver `LICENSE`: puedes usarla y cambiarla, manteniendo el aviso de autoría. Las fuentes Inter de `template/edit/fonts/` tienen su propia licencia (SIL Open Font License).
