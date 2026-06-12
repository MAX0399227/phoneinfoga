# secure-share — Compartir documentos cifrados y autodestructibles

Herramienta para empaquetar un PDF confidencial en un **ZIP cifrado AES‑256**
con un **visor autodestructible** (3 min 30 s) y trazabilidad por **código
numérico invisible** + marca de agua.

## Qué hace (garantizado de verdad)

- **Cifrado AES‑256** del contenido con tu clave (formato WinZip AES, estándar).
- **Código numérico invisible** asignado al título: se incrusta en los
  metadatos del documento y mediante esteganografía de caracteres de ancho
  cero. Permite identificar el origen de una fuga.
- **Autodestrucción a los 210 s** (3:30): el visor se cierra solo y libera el
  contenido de memoria. El contenido se descifra **solo en RAM**, nunca se
  escribe en disco.
- **Sin texto copiable**: las páginas se rasterizan a imagen; no hay texto
  seleccionable ni botón de guardar; el clic derecho se ignora.
- **Marca de agua** con el código de trazabilidad en cada página.
- **Modo numérico best‑effort** ante captura: al perder el foco la ventana o
  al pulsar ImprPant / Ctrl+C / Ctrl+P / Ctrl+S, el contenido se sustituye por
  una vista de dígitos.

## Qué NO hace (y por qué ninguna herramienta puede)

Esto es honestidad técnica, no una limitación de esta implementación:

- **No impide fotografiar la pantalla** con otro teléfono o cámara (el
  "agujero analógico"). Es físicamente imposible de evitar.
- **No impide copiar/reenviar/archivar** el ZIP cifrado. Quien recibe el
  archivo y la clave tiene los datos; eso es el problema irresoluble del DRM.
- **No garantiza "cero registro"** en la máquina del receptor. No controlas su
  sistema operativo.
- El modo anti‑pantallazo **disuade**, no bloquea: una captura disparada sin
  que la ventana pierda el foco puede capturar el contenido real.

**La seguridad real está en la CLAVE (canal aparte) y en la TRAZABILIDAD
(código invisible + marca de agua), no en intentar bloquear la pantalla
ajena.**

## Instalación

```bash
pip install -r requirements.txt
```

## Uso

Empaquetar (lado emisor):

```bash
python pack.py documento.pdf -o documento.secure.zip
# La clave se pide de forma interactiva (no queda en el historial del shell).
```

Abrir (lado receptor):

```bash
python viewer.py documento.secure.zip
# Pide la clave, muestra el documento 3:30 y se cierra solo.
```

Comparte el `documento.secure.zip` y el `viewer.py` por un canal, y **la clave
por un canal distinto** (nunca juntos).

## Recomendaciones de uso seguro

1. Envía la clave por un canal separado del archivo (p. ej. archivo por correo,
   clave por una llamada).
2. No reutilices la clave entre destinatarios; genera un paquete por receptor
   para que la marca de agua identifique fugas individualmente.
3. Asume que el contenido puede ser fotografiado: comparte solo lo que estés
   dispuesto a que, en el peor caso, sea visto.
