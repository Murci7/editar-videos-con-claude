# Gráficos reutilizables

Páginas HTML de `src/` que `render.py` convierte en vídeo, fotograma a fotograma. Se programan en `edit/schedule.py`
con `g(id, página, inicio, fin, overlay, query, cues, sfx)`.

- **Cues:** en segundos desde el inicio del gráfico. `g()` los calcula a partir de los tiempos globales de
  `at(toma, "palabra")`. Sin `c=`, cada página usa sus cues por defecto.
- **`d=`:** en los overlays que salen con fundido, `d` tiene que coincidir con la duración del clip (`fin - inicio`).
- **Texto en la query:** `*palabras*` salen en el color de acento y `|` es un salto de línea. No uses `&`, `#`, `+` ni
  `%` dentro de un texto.
- **Zonas seguras:** los overlays van en x 110-790 (la persona, en el tercio derecho). Todo el contenido queda por encima
  de y≈900, donde van los subtítulos. `antes-despues` y `pistas` son las únicas excepciones, a propósito.
- **Fondo:** los overlays van sobre tarjetas oscuras, para que se lean sobre una pared clara. Las pantallas completas
  usan `<body class="fs">`.
- **Marca:** colores y fuentes en `src/marca.css`; nombre, rol, marca, web y logo en `src/marca.js` y `src/logo.svg`.
  Ninguna página lleva colores propios: cambia esos tres archivos y cambian todas.

| Página | Tipo | Parámetros | Cues | Duración | SFX |
|---|---|---|---|---|---|
| `titulo.html` | pantalla completa | `t` título · `eyebrow` · `sub` · `tl=1` añade un timeline animado | — | 2,8 s (`TITLE_DUR`) | golpe-grave o whoosh |
| `texto.html` | overlay | `txt` (`*azul*`, `!naranja!` solo para avisos) · `d` | — (las palabras entran una a una) | 2,8 s | pop |
| `rotulo.html` | overlay | `kind=nombre` (por defecto: nombre y rol de `marca.js`) · `a`, `b` sustituyen las dos líneas (sirve para una llamada a la acción) · `d` | — | 5 s | pop |
| `pildora.html` | overlay | `n` = nº de ediciones (de `work/capcut_stats.json`) · `t` etiqueta · `d` | 0 entra; la cuenta sube 0,3 s después | 5 s | pop-suave |
| `paso.html` | overlay | `n` paso · `de` total (4) · `t` título · `d` | — | 3,5 s | pop |
| `flujo.html` | pantalla completa | `pasos=Título\|sub;…` (2-5) · `eyebrow` · `h` · `active=N` resalta uno · `q` pregunta abierta | 0…n-1 cada nodo · n la pregunta | 8-10 s | whoosh |
| `trucos.html` | overlay | `items=Título\|detalle;…` (1-4) · `h` palabra tras el número («claves») · `d` | 0…n-1 cada fila | la toma | pop |
| `antes-despues.html` | overlay de marco completo | `a` s en bruto · `b` s montado · `x` velocidad · `la`, `lb` etiquetas | 0 contador izquierdo · 1 derecho | lo pone `ad()` | whoosh-suave |
| `pistas.html` | overlay | `x` borde izquierdo de las flechas · `ys` y de cada píldora · `n` (1-5) · `d` | 0 Tomas · 1 Gráficos · 2 Subtítulos · 3 Sonidos · 4 Música | ~6 s | pop |
| `cierre.html` | pantalla completa | `h` · `s` · `regalo` (píldora, oculta si falta) · `web` (por defecto la de `marca.js`) · `slots=0` quita los huecos de la pantalla final de YouTube | — | 12 s (`END_DUR`) | whoosh |

`antes-despues.html` no se programa con `g()`: lo pone `ad()`, con el vídeo de las dos ventanas debajo (lo hace
`edit/pantalla.py`). Geometría de las ventanas: izquierda x=60 y=250, derecha x=980 y=250, ambas 880×495, radio 18 px.
`pistas.html` señala las pistas de CapCut en una grabación de pantalla (`p()`): alinea `ys` con las pistas que se ven.

## Páginas nuevas
Copia una parecida y usa `base.css`/`base.js` (colores siempre con las variables de `marca.css`, como `var(--sky)`): `cue(i, defecto)`, `num(k, defecto)`, `str(k, defecto)`,
`rich(texto)`, `anim(el, 'rise .6s ${t}s both var(--ease)')` y `tick(fn)` para contadores (fn depende solo de t).
Nunca llames `top`, `name` ni `status` a una variable global (son del navegador y la página muere sin avisar).
Previsualiza en el navegador con `?bg=1` si es de pantalla completa, más los cues: `flujo.html?bg=1&c=0.3,1.6,3,4.4`.

**Peso del render:** las pantallas completas tardan ~0,5 s por fotograma en un Mac Intel (10 s de gráfico ≈ 2,5 min);
`antes-despues` es un .mov de marco completo, ~2,8 MB por segundo.

## antes-despues2.html · antes/después en secuencia (con `ad_seq`)
Una ventana grande (x=320 y=128, 1280×720) que pasa del bruto al cortado en el cue 1. Parámetros: `a` (segundos en
bruto), `b` (segundos cortados), `sp` (tramos de voz `ini-fin,…`; el resto es silencio). Lo pone todo `ad_seq()`.

## capcut.html · tu proyecto de CapCut, dibujado
Necesita `capcut-data.js` (`python edit/capcut_data.py` después de `to_capcut.py`) y, para la cabecera, los logos de
`tools/logos.sh`. `mode=flat|3d` · `head=1` (Claude ⋯⋯ CapCut) · `t0` (segundo de la línea de tiempo al empezar) ·
`x` (velocidad del cabezal) · `pps` (píxeles por segundo). Cues 0-3: ✓ en Tomas, Gráficos, Subtítulos, Efectos.
