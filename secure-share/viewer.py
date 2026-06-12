#!/usr/bin/env python3
"""
viewer.py — Visor seguro y AUTODESTRUCTIBLE para paquetes generados con pack.py.

Comportamiento:
  * Pide la clave, descifra el contenido EN MEMORIA (nunca lo escribe en disco).
  * Muestra el documento a pantalla completa durante 3 min 30 s (210 s) y se
    cierra solo. Una barra muestra el tiempo restante.
  * Modo anti-pantallazo (BEST-EFFORT, no infalible):
      - Al perder el foco la ventana (típico al lanzar una herramienta de
        captura), el contenido se sustituye por la VISTA NUMÉRICA.
      - Al pulsar ImprPant / PrintScreen se fuerza la vista numérica.
  * Marca de agua con el código de trazabilidad incrustada en cada página.
  * No hay texto seleccionable ni botón de guardar; el clic derecho se ignora.

ADVERTENCIA HONESTA: esto DISUADE, no impide. Nadie puede evitar que el
receptor fotografíe la pantalla con otro dispositivo, ni que copie el ZIP
cifrado antes de abrirlo. La seguridad real está en la CLAVE y en la
TRAZABILIDAD (marca de agua + código invisible), no en bloquear la pantalla.

Uso:
    python viewer.py PAQUETE.secure.zip
"""
import io
import json
import sys
import time
import tkinter as tk
from tkinter import simpledialog, messagebox

try:
    import pyzipper
    from PIL import Image, ImageTk
except ImportError as e:
    sys.exit(f"Falta dependencia: {e}. Instala: pip install pyzipper Pillow")


class SecureViewer:
    def __init__(self, root, pages, numerics, manifest):
        self.root = root
        self.pages = pages
        self.numerics = numerics
        self.ttl = int(manifest.get("ttl_seconds", 210))
        self.docid = manifest.get("docid", "????")
        self.idx = 0
        self.numeric_mode = False
        self.deadline = time.time() + self.ttl
        self._photo = None

        root.title("Visor seguro")
        root.attributes("-fullscreen", True)
        root.attributes("-topmost", True)
        root.configure(bg="black")
        root.protocol("WM_DELETE_WINDOW", self.destroy)

        self.canvas = tk.Label(root, bg="black")
        self.canvas.pack(fill="both", expand=True)

        self.status = tk.Label(root, bg="black", fg="#00c878",
                               font=("DejaVu Sans Mono", 12))
        self.status.pack(fill="x", side="bottom")

        # Navegación
        root.bind("<Right>", lambda e: self.nav(1))
        root.bind("<Left>", lambda e: self.nav(-1))
        root.bind("<Escape>", lambda e: self.destroy())
        # Anti-captura best-effort
        root.bind("<FocusOut>", lambda e: self.force_numeric(True))
        root.bind("<FocusIn>", lambda e: self.force_numeric(False))
        for k in ("<Print>", "<Key-Print>", "<Control-c>", "<Control-C>",
                  "<Control-p>", "<Control-s>"):
            root.bind(k, lambda e: self.force_numeric(True))
        # Ignorar clic derecho (sin menú de guardar)
        root.bind("<Button-3>", lambda e: "break")

        self.render()
        self.tick()

    def _current_bytes(self):
        src = self.numerics if self.numeric_mode else self.pages
        return src[self.idx]

    def render(self):
        img = Image.open(io.BytesIO(self._current_bytes()))
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight() - 30
        scale = min(sw / img.width, sh / img.height)
        img = img.resize((max(1, int(img.width * scale)),
                          max(1, int(img.height * scale))), Image.LANCZOS)
        self._photo = ImageTk.PhotoImage(img)
        self.canvas.configure(image=self._photo)

    def nav(self, d):
        self.idx = max(0, min(len(self.pages) - 1, self.idx + d))
        self.render()

    def force_numeric(self, on):
        if self.numeric_mode != on:
            self.numeric_mode = on
            self.render()

    def tick(self):
        left = int(self.deadline - time.time())
        if left <= 0:
            self.destroy()
            return
        m, s = divmod(left, 60)
        mode = "  [VISTA NUMERICA]" if self.numeric_mode else ""
        self.status.configure(
            text=f"COD {self.docid}  ·  Pag {self.idx+1}/{len(self.pages)}  ·  "
                 f"Autodestruccion en {m:01d}:{s:02d}{mode}  ·  "
                 f"Flechas: navegar  ·  Esc: cerrar")
        self.root.after(250, self.tick)

    def destroy(self):
        # Borrado de referencias en memoria (best-effort)
        self.pages = self.numerics = None
        self._photo = None
        try:
            self.root.destroy()
        except Exception:
            pass


def load_package(path):
    pwd = None
    # Pedimos la clave por consola (no queda en historial de shell)
    import getpass
    pwd = getpass.getpass("Clave para abrir el documento: ")
    try:
        with pyzipper.AESZipFile(path) as z:
            z.setpassword(pwd.encode())
            manifest = json.loads(z.read("manifest.json"))
            n = manifest["pages"]
            pages = [z.read(f"pages/p{i:03d}.png") for i in range(n)]
            numerics = [z.read(f"numeric/p{i:03d}.png") for i in range(n)]
    except Exception as e:
        sys.exit(f"No se pudo abrir (clave incorrecta o archivo dañado): {e}")
    return pages, numerics, manifest


def main():
    if len(sys.argv) < 2:
        sys.exit("Uso: python viewer.py PAQUETE.secure.zip")
    pages, numerics, manifest = load_package(sys.argv[1])
    root = tk.Tk()
    SecureViewer(root, pages, numerics, manifest)
    root.mainloop()


if __name__ == "__main__":
    main()
