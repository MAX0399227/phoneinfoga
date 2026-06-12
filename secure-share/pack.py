#!/usr/bin/env python3
"""
pack.py — Empaqueta un PDF confidencial en un ZIP cifrado (AES-256) y
autodestructible, listo para compartir.

Lo que SÍ hace (garantizado):
  * Cifra el contenido con AES-256 usando tu clave.
  * Asigna al título un CÓDIGO NUMÉRICO INVISIBLE (metadatos + esteganografía
    de ancho cero) que viaja oculto y permite trazar fugas.
  * Rasteriza cada página a imagen (no hay texto seleccionable/copiable).
  * Genera una versión "numérica" de cada página para el modo anti-pantallazo.
  * Incrusta una marca de agua con el código de trazabilidad.

Lo que NO puede hacer (ninguna tecnología puede, y este programa no miente):
  * Impedir que el receptor fotografíe la pantalla con otra cámara.
  * Impedir copiar/reenviar/archivar el archivo una vez descifrado en RAM.
  * Garantizar que no quede ningún registro en la máquina ajena.

Uso:
    python pack.py ENTRADA.pdf -o SALIDA.zip
La clave se pide de forma interactiva (no se escribe en la línea de comandos).
"""
import argparse
import getpass
import hashlib
import io
import json
import os
import sys
import time

try:
    import fitz  # PyMuPDF
    import pyzipper
    from PIL import Image, ImageDraw, ImageFont
except ImportError as e:
    sys.exit(f"Falta una dependencia: {e}. Instala con: pip install -r requirements.txt")

TTL_SECONDS = 75           # 1 min 15 s
RENDER_DPI = 150
HEAD_MIN_SIZE = 12.0       # spans de este tamaño o mayor = títulos/encabezados


def numeric_code(data: bytes) -> str:
    """Código numérico determinista (20 dígitos) derivado del contenido."""
    h = hashlib.sha256(data).hexdigest()
    n = int(h, 16) % (10 ** 20)
    return f"{n:020d}"


def recipient_tag(name: str) -> str:
    """Etiqueta numérica de 6 dígitos por destinatario (trazabilidad)."""
    h = hashlib.sha256(name.encode()).hexdigest()
    return f"{int(h, 16) % 1000000:06d}"


def digitize(text: str, code: str) -> str:
    """Convierte un texto en una cadena de dígitos del mismo largo (deterministico).

    Conserva los espacios para que el bloque numérico ocupe el mismo lugar que
    el título original. Reversible solo con el documento original (no es cifrado,
    es ocultación visual)."""
    h = hashlib.sha256((code + text).encode()).digest()
    out, j = [], 0
    for ch in text:
        if ch.isspace():
            out.append(ch)
        else:
            out.append(str(h[j % len(h)] % 10))
            j += 1
    return "".join(out)


def hide_titles(doc, code):
    """Redacta los títulos/encabezados y los sustituye por su versión numérica."""
    n_hidden = 0
    for page in doc:
        spans = []
        for b in page.get_text("dict")["blocks"]:
            for l in b.get("lines", []):
                for s in l["spans"]:
                    if s["size"] >= HEAD_MIN_SIZE and s["text"].strip():
                        spans.append((fitz.Rect(s["bbox"]), s["text"], s["size"]))
        for rect, _txt, _sz in spans:
            page.add_redact_annot(rect, fill=(1, 1, 1))  # blanquea el título
        if spans:
            page.apply_redactions()
        for rect, txt, sz in spans:
            digits = digitize(txt, code)
            box = fitz.Rect(rect.x0, rect.y0 - 1, rect.x1, rect.y1 + sz * 0.5)
            fs = sz
            while fs > 4:
                rc = page.insert_textbox(box, digits, fontsize=fs,
                                         fontname="cour", color=(0, 0, 0))
                if rc >= 0:
                    break
                fs -= 0.5
            n_hidden += 1
    return n_hidden


def zero_width_stego(code: str) -> str:
    """Codifica el código numérico en caracteres de ancho cero (invisible)."""
    bits = "".join(f"{int(d):04b}" for d in code)
    # 0 -> U+200B (zero width space), 1 -> U+200C (zero width non-joiner)
    return "".join("​" if b == "0" else "‌" for b in bits)


def render_pages(doc, code, wm_text):
    """Devuelve (imagen_normal_png, imagen_numerica_png) por página."""
    normals, numerics = [], []
    for page in doc:
        pix = page.get_pixmap(dpi=RENDER_DPI)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

        # --- marca de agua diagonal tenue con el código (trazabilidad) ---
        wm = img.copy().convert("RGBA")
        overlay = Image.new("RGBA", wm.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(overlay)
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", 22)
        except Exception:
            font = ImageFont.load_default()
        txt = wm_text
        step = 260
        for y in range(0, wm.height + step, step):
            for x in range(-200, wm.width, step * 2):
                d.text((x, y), txt, fill=(120, 120, 120, 38), font=font)
        wm = Image.alpha_composite(wm, overlay).convert("RGB")
        buf = io.BytesIO(); wm.save(buf, "PNG"); normals.append(buf.getvalue())

        # --- versión "numérica" (lo que se muestra ante un pantallazo) ---
        dec = Image.new("RGB", img.size, (8, 10, 18))
        dd = ImageDraw.Draw(dec)
        try:
            mono = ImageFont.truetype("DejaVuSansMono.ttf", 16)
        except Exception:
            mono = ImageFont.load_default()
        # rejilla de dígitos derivada del código (parece una matriz cifrada)
        seed = int(code) or 1
        line = ""
        rng = seed
        rows = []
        for _ in range(img.height // 20):
            row = ""
            for _ in range(img.width // 11):
                rng = (1103515245 * rng + 12345) & 0x7FFFFFFF
                row += str(rng % 10)
            rows.append(row)
        dd.text((20, 18), "*** CONTENIDO PROTEGIDO — VISTA NUMERICA ***",
                fill=(0, 200, 120), font=mono)
        for i, row in enumerate(rows):
            dd.text((10, 44 + i * 20), row, fill=(0, 120, 90), font=mono)
        dd.text((20, img.height - 40), f"COD {code}", fill=(0, 200, 120), font=mono)
        buf = io.BytesIO(); dec.save(buf, "PNG"); numerics.append(buf.getvalue())
    return normals, numerics


def main():
    ap = argparse.ArgumentParser(description="Empaqueta PDF en ZIP cifrado autodestructible.")
    ap.add_argument("pdf", help="PDF de entrada")
    ap.add_argument("-o", "--out", help="ZIP de salida", default=None)
    ap.add_argument("-r", "--recipient", default=None,
                    help="Nombre/ID del destinatario (marca de agua individual)")
    ap.add_argument("--no-hide-title", action="store_true",
                    help="No ocultar los títulos como números")
    args = ap.parse_args()

    if not os.path.isfile(args.pdf):
        sys.exit(f"No existe: {args.pdf}")

    raw = open(args.pdf, "rb").read()
    code = numeric_code(raw)

    pwd = getpass.getpass("Clave de cifrado: ")
    if not pwd:
        sys.exit("Clave vacía, abortado.")
    if getpass.getpass("Repite la clave:  ") != pwd:
        sys.exit("Las claves no coinciden.")

    doc = fitz.open(stream=raw, filetype="pdf")

    # Código numérico INVISIBLE en metadatos + esteganografía de ancho cero.
    meta = doc.metadata or {}
    meta["title"] = code + zero_width_stego(code)
    meta["keywords"] = f"docid:{code}"
    doc.set_metadata(meta)

    print(f"[*] Código numérico invisible del título: {code}")

    if not args.no_hide_title:
        n = hide_titles(doc, code)
        print(f"[*] Títulos ocultados como números: {n}")

    rtag = recipient_tag(args.recipient) if args.recipient else None
    if args.recipient:
        wm_text = f"COD {code}  ·  DEST {args.recipient} [{rtag}]  ·  NO REENVIAR"
        print(f"[*] Destinatario: {args.recipient}  (etiqueta {rtag})")
    else:
        wm_text = f"COD {code}  ·  CONFIDENCIAL  ·  NO REENVIAR"

    print(f"[*] Renderizando {doc.page_count} páginas (DPI {RENDER_DPI})...")
    normals, numerics = render_pages(doc, code, wm_text)

    manifest = {
        "docid": code,
        "title_invisible": code,
        "recipient": args.recipient,
        "recipient_tag": rtag,
        "titles_hidden_as_numbers": not args.no_hide_title,
        "pages": doc.page_count,
        "ttl_seconds": TTL_SECONDS,
        "created": int(time.time()),
        "created_human": time.strftime("%Y-%m-%d %H:%M:%S"),
        "note": f"Autodestruccion a los {TTL_SECONDS}s. No reenviar.",
    }

    base = os.path.splitext(args.pdf)[0]
    if args.recipient:
        safe = "".join(c if c.isalnum() else "_" for c in args.recipient)
        out = args.out or f"{base}.{safe}.secure.zip"
    else:
        out = args.out or (base + ".secure.zip")
    with pyzipper.AESZipFile(out, "w", compression=pyzipper.ZIP_DEFLATED,
                             encryption=pyzipper.WZ_AES) as z:
        z.setpassword(pwd.encode())
        z.setencryption(pyzipper.WZ_AES, nbits=256)
        z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        for i, b in enumerate(normals):
            z.writestr(f"pages/p{i:03d}.png", b)
        for i, b in enumerate(numerics):
            z.writestr(f"numeric/p{i:03d}.png", b)

    size = os.path.getsize(out)
    print(f"[OK] ZIP cifrado AES-256 generado: {out}  ({size/1024:.0f} KB)")
    print(f"[OK] Comparte ESTE archivo + el visor (viewer.py). La clave va por canal aparte.")
    print(f"[OK] El receptor ejecuta:  python viewer.py {os.path.basename(out)}")


if __name__ == "__main__":
    main()
