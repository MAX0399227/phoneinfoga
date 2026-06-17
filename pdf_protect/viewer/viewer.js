// viewer.js — Lector seguro con marca de agua CVZ y bloqueos anti-copia/captura.
//
// Importante: ningun visor web puede GARANTIZAR que se impida una captura de
// pantalla (el sistema operativo siempre puede fotografiar la pantalla). Aqui
// se aplican las mejores barreras posibles del lado del navegador:
//   - El PDF se dibuja en <canvas> (no hay texto seleccionable -> no se copia).
//   - Se desactivan clic derecho, copiar, cortar, arrastrar e impresion.
//   - La pantalla se oscurece al perder el foco o al pulsar Impr Pant.
//   - Marca de agua "CVZ" superpuesta y repetida en cada pagina.
//   - Sin temporizador: el documento permanece abierto sin limite de lectura.

import * as pdfjsLib from "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.4.168/pdf.min.mjs";
pdfjsLib.GlobalWorkerOptions.workerSrc =
  "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.4.168/pdf.worker.min.mjs";

const WATERMARK = "CVZ";
// Ruta al PDF protegido (relativa al visor). Cambia si lo ubicas en otro sitio.
const PDF_URL = "../MAMAESTAPRESA-protegido.pdf";

let pdfDoc = null;
let scale = 1.3;

const $ = (id) => document.getElementById(id);

// ---------- Apertura con clave ----------
async function open() {
  const pass = $("pwd").value;
  $("err").textContent = "";
  try {
    const task = pdfjsLib.getDocument({ url: PDF_URL, password: pass });
    pdfDoc = await task.promise;
  } catch (e) {
    if (e && e.name === "PasswordException") {
      $("err").textContent = "Clave incorrecta.";
    } else {
      $("err").textContent = "No se pudo abrir el archivo.";
      console.error(e);
    }
    return;
  }
  $("gate").style.display = "none";
  $("toolbar").style.display = "flex";
  await render();
}

// ---------- Render de todas las paginas ----------
async function render() {
  const stage = $("stage");
  stage.innerHTML = "";
  for (let n = 1; n <= pdfDoc.numPages; n++) {
    const page = await pdfDoc.getPage(n);
    const viewport = page.getViewport({ scale });

    const wrap = document.createElement("div");
    wrap.className = "page-wrap";

    const canvas = document.createElement("canvas");
    canvas.width = viewport.width;
    canvas.height = viewport.height;
    const ctx = canvas.getContext("2d");
    wrap.appendChild(canvas);

    // Capa de marca de agua repetida
    const wm = document.createElement("div");
    wm.className = "wm";
    const count = Math.ceil((viewport.width * viewport.height) / 9000);
    for (let i = 0; i < count; i++) {
      const s = document.createElement("span");
      s.textContent = WATERMARK;
      wm.appendChild(s);
    }
    wrap.appendChild(wm);

    stage.appendChild(wrap);
    await page.render({ canvasContext: ctx, viewport }).promise;
  }
}

// ---------- Bloqueos anti-copia ----------
function hardenCopyProtection() {
  const block = (e) => { e.preventDefault(); return false; };
  document.addEventListener("contextmenu", block);   // clic derecho
  document.addEventListener("copy", block);          // copiar
  document.addEventListener("cut", block);
  document.addEventListener("dragstart", block);     // arrastrar imagenes
  document.addEventListener("selectstart", block);   // seleccionar

  document.addEventListener("keydown", (e) => {
    const k = (e.key || "").toLowerCase();
    // Ctrl/Cmd + C/S/P/A/U  e  Impr Pant
    if ((e.ctrlKey || e.metaKey) && ["c", "s", "p", "a", "u"].includes(k)) {
      e.preventDefault();
    }
    if (k === "printscreen") {
      flashBlackout(1200);
      // Intento de vaciar el portapapeles tras la captura
      navigator.clipboard?.writeText("Contenido protegido — CVZ").catch(() => {});
    }
  });
}

// ---------- Cortina anti-captura ----------
let blackoutTimer = null;
function showBlackout() { $("blackout").classList.add("show"); }
function hideBlackout() { $("blackout").classList.remove("show"); }
function flashBlackout(ms) {
  showBlackout();
  clearTimeout(blackoutTimer);
  blackoutTimer = setTimeout(hideBlackout, ms);
}
function hardenScreenProtection() {
  // Al cambiar de pestana / minimizar -> ocultar contenido
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) showBlackout(); else hideBlackout();
  });
  // Al perder el foco de la ventana (posible captura/grabacion) -> ocultar
  window.addEventListener("blur", showBlackout);
  window.addEventListener("focus", hideBlackout);
}

// ---------- Zoom ----------
function bindToolbar() {
  $("zoomIn").addEventListener("click", () => { scale = Math.min(3, scale + 0.15); render(); });
  $("zoomOut").addEventListener("click", () => { scale = Math.max(0.6, scale - 0.15); render(); });
}

// ---------- Init ----------
$("open").addEventListener("click", open);
$("pwd").addEventListener("keydown", (e) => { if (e.key === "Enter") open(); });
hardenCopyProtection();
hardenScreenProtection();
bindToolbar();
