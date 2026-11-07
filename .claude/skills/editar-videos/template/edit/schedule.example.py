# Graphics schedule — executed inside timeline.py. Copy to schedule.py and write one block per take.
# Times come from the words actually said: at(take, "word", nth=1, after=0, end=False, prefix=False) → global time
# (exact word match; prefix=True only for words whisper mis-hears) · take_start(k) / take_end(k)
# START["titulo"] / TITLE_DUR = title card after take 1 · START["cierre"] / END_DUR = end screen
#
#   g(id, page, start, end, overlay, query, cues, sfx)   HTML graphic from motion/src (catalogue: motion/GRAFICOS.md);
#                                                        overlay=True = transparent, left of the frame; False = full screen
#   p(id, file, src_in, src_out, start, end, zooms, sfx) screen recording, full screen, sped up to fit start..end;
#                                                        zooms=[(t, x, y, w, h), (t, None)] in source pixels, t from start
#   ad(id, take, raw_in, raw_out, start, end, sfx=...)   before/after: raw take span (left) vs the same span cut (right)
# SFX (edit/sfx): pop, pop-suave, whoosh, whoosh-suave, golpe-grave, clic, subida. Ids must be unique.
# Texts in the query: *word* = accent colour, | = line break; never & # + % inside a text.

# 1 · Hook: the key phrase on the left, then the edit-count pill (2nd pass: n = "ediciones" in work/capcut_stats.json)
s = at(1, "Hoy")
g("t01-texto", "texto.html", s - 0.1, s + 2.7, True, "txt=Ni un *clip*&d=2.8", sfx="pop")
g("t01-pildora", "pildora.html", s + 3.0, s + 8.0, True, "n=186&d=5", sfx="pop-suave")
g("t01-titulo", "titulo.html", START["titulo"], START["titulo"] + TITLE_DUR, False,
  "eyebrow=Sin saber editar&t=El título|de tu *vídeo*", sfx="golpe-grave")

# 2 · Name lower third on «Soy»
s = at(2, "Soy")
g("t02-rotulo", "rotulo.html", s, s + 5.0, True, "kind=nombre&d=5", sfx="pop")

# 3 · Full-screen flow: one node per spoken step, then back to camera for the last sentence
s, e = at(3, "primero") - 0.3, at(3, "Y", 2) - 0.2
g("t03-flujo", "flujo.html", s, e, False, "pasos=Grabar|Lo hago yo;Montar|Lo hace Claude;Publicar|Un clic&h=Tres *pasos*",
  cues=[at(3, "primero"), at(3, "segundo"), at(3, "tercero")], sfx="whoosh")

# 4 · Screen recording (file relative to edit/): 15 s sped up into 6.5 s, zoom in, back out, zoom elsewhere
s = take_start(4) + 0.5
p("t04-pantalla", "../pantalla/grabacion.mp4", 0.5, 15.5, s, s + 6.5, sfx="whoosh",
  zooms=[(0.9, 40, 280, 820, 100), (2.6, None), (3.6, 40, 390, 900, 420)])

# 5 · Before/after: take 5 from 0 to 12 s as recorded (left) and after cutting (right), with both timers
s = take_start(5) + 0.3
ad("t05-antes-despues", 5, 0.0, 12.0, s, s + 8.0, sfx="whoosh-suave")

# 6 · A list that fills in on each word
s, e = take_start(6), take_end(6)
g("t06-trucos", "trucos.html", s, e, True, f"items=Tomas cortas|Si fallas, repites diez segundos;Un lado vacío|Ahí van "
  f"los gráficos;Tu estilo escrito|Una vez, en la skill&h=trucos&d={e - s:.2f}",
  cues=[at(6, "Uno"), at(6, "Dos"), at(6, "Tres")], sfx="pop")

# 7 · Call to action (lower third) + end screen
s = at(7, "descripción") - 0.2
g("t07-cta", "rotulo.html", s, s + 6.0, True, "a=Plantilla gratis&b=Enlace en la *descripción*&d=6", sfx="pop")
g("t08-cierre", "cierre.html", START["cierre"], START["cierre"] + END_DUR, False,
  "regalo=Plantilla gratis en la descripción", sfx="whoosh")
