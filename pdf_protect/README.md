# Protección de PDF — Marca de agua CVZ + clave + anti-copia

Herramienta para **abrir un PDF**, agregarle la marca de agua **CVZ**, cifrarlo
con una **clave** y restringir **copiar / imprimir / compartir**, además de un
**visor web** que disuade las capturas de pantalla. La lectura **no tiene límite
de tiempo**.

## Contenido

| Archivo | Qué hace |
|---|---|
| `protect.py` | Abre el PDF, pone la marca de agua CVZ, lo cifra (AES-256) con la clave y deniega copiar/imprimir/modificar. |
| `viewer/` | Visor web seguro: pide la clave, muestra la marca CVZ y bloquea copia, clic derecho, arrastre y oscurece la pantalla al perder el foco. |
| `requirements.txt` | Dependencias de Python. |

## 1) Generar el PDF protegido

```bash
pip install -r requirements.txt

python3 protect.py MAMAESTAPRESA.pdf -o MAMAESTAPRESA-protegido.pdf
# Marca de agua: CVZ   ·   Clave de apertura: 1.x.b225
```

Opciones:

```bash
python3 protect.py ENTRADA.pdf \
    -o SALIDA.pdf \
    --watermark CVZ \
    --key 1.x.b225 \
    --owner-key "clave-admin-opcional"
```

Resultado: un PDF que **solo abre con la clave `1.x.b225`** y en el que copiar,
imprimir y modificar quedan **denegados** en cualquier lector que respete el
estándar PDF (Acrobat, Chrome, Edge, Vista Previa, etc.).

## 2) Visor web seguro (anti-captura)

```bash
# Sirve la carpeta por HTTP (necesario para que el navegador cargue el worker)
cd pdf_protect
python3 -m http.server 8000
# Abre en el navegador:  http://localhost:8000/viewer/
```

El visor:

- Pide la **clave** antes de mostrar nada.
- Dibuja el PDF en `<canvas>` → **no hay texto seleccionable** que copiar.
- Superpone la marca **CVZ** repetida en cada página.
- Bloquea **clic derecho, copiar, cortar, arrastrar, Ctrl+C/S/P/A/U**.
- **Oscurece la pantalla** al cambiar de pestaña, minimizar, perder el foco o
  pulsar *Impr Pant* (disuasión de capturas y grabaciones).
- **No impone límite de tiempo**: el documento permanece abierto mientras lo leas.

> El visor carga la librería PDF.js desde un CDN. Si necesitas que funcione sin
> internet, descarga `pdf.min.mjs` y `pdf.worker.min.mjs` a `viewer/` y cambia
> las rutas en `index.html` y `viewer.js`.

## ⚠️ Hasta dónde llega la protección (importante y honesto)

- **Sí se impide** de forma efectiva: abrir sin clave, copiar texto e imprimir
  desde lectores estándar (gracias al cifrado y los permisos del PDF).
- **No se puede garantizar al 100%** impedir una **captura de pantalla o una foto
  con otro dispositivo**: ningún formato de archivo ni página web puede evitar
  que el sistema operativo capture lo que se muestra en pantalla. Lo que aquí se
  hace es **disuadir** (oscurecer, marca de agua que identifica el origen) y
  **dificultar** la extracción, no volverla imposible.
- La protección real frente a fugas combina: marca de agua identificable (CVZ),
  cifrado con clave, control de a quién entregas el archivo y, si lo necesitas,
  un sistema DRM con servidor. Pídelo si quieres avanzar en esa dirección.
