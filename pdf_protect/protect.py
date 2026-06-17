#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
protect.py — Abre un PDF, le agrega la marca de agua "CVZ", lo cifra con una
clave de usuario y restringe copiar / imprimir / modificar / extraer texto.

Uso:
    python3 protect.py ENTRADA.pdf [-o SALIDA.pdf] [--watermark CVZ] [--key 1.x.b225]

Por defecto:
    - Marca de agua  : CVZ   (en mosaico diagonal sobre cada pagina)
    - Clave (apertura): 1.x.b225
    - Permisos        : se DENIEGAN copia, impresion, modificacion,
                        anotaciones, ensamblado y extraccion de texto.

Notas de seguridad (importante leerlas):
    - El cifrado AES-256 y los permisos del PDF SI impiden de forma efectiva
      copiar texto e imprimir en lectores que respetan el estandar PDF
      (Acrobat, Chrome, Edge, Preview, etc.).
    - NINGUN formato de archivo puede impedir por si mismo una captura de
      pantalla: cualquier sistema operativo puede fotografiar lo que se ve.
      Para disuadir capturas usa ademas el visor web incluido en ./viewer,
      que aplica bloqueos de copia, clic derecho, arrastre y oscurece la
      pantalla al perder el foco. Sigue siendo disuasion, no garantia.
"""

import argparse
import sys
from pathlib import Path

import fitz  # PyMuPDF


DEFAULT_WATERMARK = "CVZ"
DEFAULT_KEY = "1.x.b225"


def add_watermark(page: fitz.Page, text: str) -> None:
    """Dibuja el texto en mosaico diagonal (45 grados) cubriendo la pagina."""
    rect = page.rect
    fontsize = 38
    gray = (0.62, 0.62, 0.62)  # gris claro
    opacity = 0.18             # semitransparente para no impedir la lectura

    # Separacion del mosaico
    step_x = 230
    step_y = 170

    tw = fitz.TextWriter(rect)
    y = -step_y
    while y < rect.height + step_y:
        x = -step_x
        while x < rect.width + step_x:
            tw.append(fitz.Point(x, y), text, fontsize=fontsize)
            x += step_x
        y += step_y

    # Pivote central + rotacion de 45 grados para toda la capa de texto
    pivot = fitz.Point(rect.width / 2, rect.height / 2)
    morph = (pivot, fitz.Matrix(45))
    tw.write_text(page, color=gray, opacity=opacity, morph=morph)

    # Sello solido y legible en el centro (referencia visible del documento)
    big = fitz.TextWriter(rect)
    big.append(fitz.Point(rect.width / 2 - 120, rect.height / 2),
               text, fontsize=90)
    big.write_text(page, color=gray, opacity=0.22,
                   morph=(pivot, fitz.Matrix(45)))


def protect(in_path: Path, out_path: Path, watermark: str, key: str,
            owner_key: str | None = None) -> Path:
    doc = fitz.open(in_path)

    if doc.is_encrypted:
        # Si el original ya estaba cifrado intentamos autenticar sin clave.
        if not doc.authenticate(""):
            raise SystemExit(
                "El PDF de entrada esta cifrado y requiere clave para abrirlo."
            )

    for page in doc:
        add_watermark(page, watermark)

    # La clave de propietario debe ser distinta de la de usuario para que las
    # restricciones tengan efecto. Si no se indica, se deriva una fuerte.
    if not owner_key:
        owner_key = key + "::OWNER::" + watermark

    # Permisos: NO incluimos COPY, PRINT, MODIFY, ANNOTATE, ASSEMBLE ni
    # ACCESSIBILITY -> todo eso queda DENEGADO. El usuario solo puede VER.
    permissions = 0  # 0 = no se permite ninguna accion privilegiada

    doc.save(
        out_path,
        encryption=fitz.PDF_ENCRYPT_AES_256,
        user_pw=key,          # clave para ABRIR el documento
        owner_pw=owner_key,   # clave de administrador (levanta restricciones)
        permissions=permissions,
        garbage=4,
        deflate=True,
    )
    doc.close()
    return out_path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Protege un PDF con marca de agua, clave y restricciones."
    )
    parser.add_argument("input", type=Path, help="PDF de entrada")
    parser.add_argument("-o", "--output", type=Path, default=None,
                        help="PDF de salida (por defecto: <entrada>-protegido.pdf)")
    parser.add_argument("--watermark", default=DEFAULT_WATERMARK,
                        help=f"Texto de la marca de agua (def: {DEFAULT_WATERMARK})")
    parser.add_argument("--key", default=DEFAULT_KEY,
                        help=f"Clave para abrir el archivo (def: {DEFAULT_KEY})")
    parser.add_argument("--owner-key", default=None,
                        help="Clave de propietario (admin). Opcional.")
    args = parser.parse_args(argv)

    in_path: Path = args.input
    if not in_path.exists():
        print(f"No existe el archivo: {in_path}", file=sys.stderr)
        return 1

    out_path: Path = args.output or in_path.with_name(
        in_path.stem + "-protegido.pdf"
    )

    protect(in_path, out_path, args.watermark, args.key, args.owner_key)

    print("OK - PDF protegido generado:")
    print(f"   archivo : {out_path}")
    print(f"   marca   : {args.watermark}")
    print(f"   clave   : {args.key}")
    print("   permisos: copiar / imprimir / modificar DENEGADOS")
    print("   tiempo  : sin limite de lectura")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
