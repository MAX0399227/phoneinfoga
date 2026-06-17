// viewer.js — Lector seguro con marca de agua CVZ y bloqueos anti-copia/captura.
//
// Importante: ningun visor web puede GARANTIZAR que se impida una captura de
// pantalla (el sistema operativo siempre puede fotografiar la pantalla). Aqui
// se aplican las mejores barreras posibles del lado del navegador:
//   - El PDF se dibuja en <canvas> (no hay texto seleccionable -> no se copia).
//   - Se desactivan clic derecho, copiar, cortar, arrastrar e impresion.
//   - La pantalla se oscurece al perder el foco o al pulsar Impr Pant.
//   - Marca de agua "CVZ" superpuesta y repetida en cada pagina.
//   - Lectura de UN SOLO USO: se abre exactamente 1 minuto y luego el
//     documento queda cerrado para siempre (no se puede reabrir).

import * as pdfjsLib from "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.4.168/pdf.min.mjs";
pdfjsLib.GlobalWorkerOptions.workerSrc =
  "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.4.168/pdf.worker.min.mjs";

const WATERMARK = "CVZ";
// Ruta al PDF protegido (relativa al visor). Cambia si lo ubicas en otro sitio.
const PDF_URL = "../MAMAESTAPRESA-protegido.pdf";

// --- Autodestruccion: tiempo de lectura permitido (en segundos) ---
const VIEW_SECONDS = 60;                 // exactamente 1 minuto
const STORE_KEY = "cvz_doc_" + PDF_URL;  // marca de consumo por documento

let pdfDoc = null;
let countdownTimer = null;
let scale = 1.3;

const $ = (id) => document.getElementById(id);

// ---------- Estado de consumo (un solo uso) ----------
// Se guarda la fecha limite de la PRIMERA apertura. Tras esa fecha el
// documento queda cerrado para siempre, aunque se recargue la pagina.
function getDeadline() {
  const raw = localStorage.getItem(STORE_KEY);
  return raw ? parseInt(raw, 10) : null;
}
function isExpired() {
  const d = getDeadline();
  return d !== null && Date.now() >= d;
}

// ---------- Apertura con clave ----------
async function open() {
  // Si ya se agoto el minuto en una apertura previa -> cerrado para siempre.
  if (isExpired()) { permanentlyClosed(); return; }

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

  // Fija la fecha limite en la PRIMERA apertura valida. Si se recarga durante
  // el minuto, se reanuda con el tiempo restante (no se reinicia el contador).
  let deadline = getDeadline();
  if (deadline === null) {
    deadline = Date.now() + VIEW_SECONDS * 1000;
    localStorage.setItem(STORE_KEY, String(deadline));
  }

  $("gate").style.display = "none";
  $("toolbar").style.display = "flex";
  await render();
  startCountdown(deadline);
}

// ---------- Cuenta regresiva y cierre definitivo ----------
function startCountdown(deadline) {
  const tick = () => {
    const remaining = Math.max(0, Math.ceil((deadline - Date.now()) / 1000));
    const m = String(Math.floor(remaining / 60)).padStart(2, "0");
    const s = String(remaining % 60).padStart(2, "0");
    $("timer").textContent = `${m}:${s}`;
    $("timer").style.color = remaining <= 10 ? "#ff6b6b" : "#ffd166";
    if (remaining <= 0) {
      clearInterval(countdownTimer);
      permanentlyClosed();
    }
  };
  tick();
  clearInterval(countdownTimer);
  countdownTimer = setInterval(tick, 250);
}

// Cierra el documento de forma irreversible: borra el render y bloquea reapertura.
function permanentlyClosed() {
  clearInterval(countdownTimer);
  pdfDoc = null;
  // Asegura que la marca de consumo quede como expirada.
  localStorage.setItem(STORE_KEY, String(Date.now() - 1));
  $("stage").innerHTML = "";
  $("toolbar").style.display = "none";
  $("gate").style.display = "flex";
  $("gate").querySelector(".card").innerHTML =
    '<h1>Documento cerrado</h1>' +
    '<p style="margin-top:10px;line-height:1.5">El tiempo de lectura de 1 minuto ' +
    'finalizó.<br>Este documento quedó <strong>cerrado para siempre</strong> ' +
    'y no puede volver a abrirse.</p>';
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

// Si el documento ya fue leido y expiro su minuto, mostrar cerrado de inmediato.
if (isExpired()) permanentlyClosed();
