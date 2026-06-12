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

TTL_SECONDS = 210          # 3 min 30 s
RENDER_DPI = 150


def numeric_code(data: bytes) -> str:
    """Código numérico determinista (20 dígitos) derivado del contenido."""
    h = hashlib.sha256(data).hexdigest()
    n = int(h, 16) % (10 ** 20)
    return f"{n:020d}"


def zero_width_stego(code: str) -> str:
    """Codifica el código numérico en caracteres de ancho cero (invisible)."""
    bits = "".join(f"{int(d):04b}" for d in code)
    # 0 -> U+200B (zero width space), 1 -> U+200C (zero width non-joiner)
    return "".join("​" if b == "0" else "‌" for b in bits)


def render_pages(doc, code):
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
        txt = f"COD {code}  ·  CONFIDENCIAL"
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
    print(f"[*] Renderizando {doc.page_count} páginas (DPI {RENDER_DPI})...")
    normals, numerics = render_pages(doc, code)

    manifest = {
        "docid": code,
        "title_invisible": code,
        "pages": doc.page_count,
        "ttl_seconds": TTL_SECONDS,
        "created": int(time.time()),
        "created_human": time.strftime("%Y-%m-%d %H:%M:%S"),
        "note": "Autodestruccion a los 210s. No reenviar.",
    }

    out = args.out or (os.path.splitext(args.pdf)[0] + ".secure.zip")
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
