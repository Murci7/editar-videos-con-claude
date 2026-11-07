# Retrato con IA para la miniatura (ChatGPT u otro generador de imágenes)

Leyendo un teleprompter casi nunca sale una sonrisa natural. Muchas miniaturas llevan caras recreadas con IA a partir
de fotos reales de la misma persona. Es la alternativa cuando ningún fotograma de las tomas sirve.

## Qué prepara Claude
Una carpeta (`miniatura-para-ia/`) con:
- `mi-cara-1.jpg` … `mi-cara-4.jpg`: 4 fotogramas de las tomas, a resolución máxima, con expresiones distintas;
- el diseño elegido de la miniatura (con la cara de un fotograma), para que el generador vea dónde irá el retrato.

## Qué haces tú
En un chat nuevo, en un solo mensaje: las 4 fotos + las miniaturas de referencia que te gusten (si las hay) + el diseño
+ el prompt de abajo (cambia `diseno-elegido` por el nombre real del archivo y rellena lo que va entre corchetes).
Descarga las que te gusten. Si sale «otra persona», responde en el mismo chat:
*"The face doesn't look like me. Keep my exact facial features from the four photos; only change the expression and
the lighting."*

Usa solo fotos tuyas o de alguien que te haya dado permiso.

## Después (Claude)
Copiar a `thumbnail/ia/`, comparar con la cara real (que no se aleje), `tools/prep_face.py` → `caras/cara-<clave>.png`
+ caja de la cara, y renderizar con `thumb.html`.

## Qué expresión pedir
- **Sonrisa abierta con «ojos que sonríen»** para promesas positivas. En el móvil la miniatura mide como un sello: una
  sonrisa con la boca cerrada se lee neutra.
- **Media sonrisa segura, boca cerrada** para títulos de curiosidad.
- **Seria e intensa** para títulos de problema o aviso.
- Nunca sorpresa exagerada: a un público profesional le suena a vendehúmos.
- Generar siempre dos expresiones y que la prueba A/B de YouTube decida.

## Prompt (en inglés: los modelos de imagen lo siguen mejor; la imagen no lleva texto)

```
I'm attaching three groups of images:

1) FOUR PHOTOS OF ME ("mi-cara-1" to "mi-cara-4"). These are the identity reference. The generated person must be unmistakably me: same face shape, eyes, nose, eyebrows, hairline, [describe your hair and facial hair, e.g. "short dark hair, short beard"], skin tone and age. Do not beautify me into a different person, do not change my ethnicity, age, or facial proportions.

2) YOUTUBE THUMBNAILS FROM ANOTHER CREATOR (optional). Use them ONLY as a reference for the photographic style of the face: a re-created, studio-quality portrait (crisp detail, clean even key light, soft fill, subtle rim light, natural-but-polished skin, confident and approachable expression). Do NOT copy that person, their clothes, their layout, their text or their colours.

3) MY THUMBNAIL DESIGN ("diseno-elegido"). This shows where the portrait will go: right side of a 16:9 thumbnail, [describe your background colour] background, bold text on the left. The portrait must fit that look.

TASK: Generate a new studio-style portrait of ME for that thumbnail.
- Expression: a genuine, open, warm smile showing my upper teeth, with "smiling eyes" (slight crinkles at the outer corners of the eyes, cheeks lifted), eyes looking straight into the camera, relaxed eyebrows. It must read as real happiness and confidence, a friendly expert who has solved the problem. Not cheesy, not forced, not surprised, no exaggerated grin.
- Framing: head and shoulders, chest-up, facing the camera, head slightly turned (5–10°), face large in frame with a little space above the hair. Shoulders visible to the bottom edge of the image.
- Clothing: the same [describe your top, e.g. "dark crew-neck T-shirt"] I'm wearing in my photos.
- Lighting: professional studio portrait. Soft key light from the front-left, gentle fill, a subtle rim light in my accent colour on the hair and shoulders so I separate from the background. Natural skin texture (keep pores and detail, no plastic look, no heavy retouching).
- Background: plain, solid, very dark [your background colour, e.g. #0E1116], completely empty. No text, no logos, no objects, no gradients with shapes, no frame.
- Output: one photorealistic image, vertical 4:5 or square, the highest resolution you can produce, sharp focus on the eyes.

Please generate 3 variations: (1) open genuine smile with teeth, (2) a slightly bigger, more joyful open smile, (3) a confident closed-mouth half smile. Keep my identity identical in all three.
```
