// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
// Utilidades compartidas por todas las pantallas
const PAGINAS = [
  ['index.html', 'Inicio'],
  ['proyectos.html', 'Proyectos'],
  ['horas.html', 'Horas'],
  ['equipo.html', 'Equipo'],
  ['estructura.html', 'Estructura'],
  ['servicios.html', 'Servicios'],
  ['cotizaciones.html', 'Cotizaciones'],
  ['configuracion.html', 'Configuración'],
  ['ayuda.html', 'Ayuda'],
];

// Configuración global: moneda base, monedas admitidas y nombre de la empresa.
// Todas las llamadas a api() esperan a que esté cargada, así los importes salen con la moneda correcta.
let BASE = 'ARS', MONEDAS = { ARS: 'Peso argentino', USD: 'Dólar estadounidense', EUR: 'Euro', GBP: 'Libra esterlina' };
let CFG = null;
const CFG_LISTA = fetch('/api/config').then(r => r.json()).then(c => {
  CFG = c; BASE = c.moneda_base || 'ARS'; if (c.monedas) MONEDAS = c.monedas;
  const b = document.querySelector('header.top .brand');
  if (b && c.empresa_nombre) b.textContent = c.empresa_nombre;
  return c;
}).catch(() => null);

// Equivalente en otra moneda (por defecto USD) con la cotización vigente: "≈ USD 5.396,10" o "" si no hay
const _cotVig = {};
async function equivalente(monto, moneda = 'USD') {
  if (monto == null || moneda === BASE) return '';
  if (!(moneda in _cotVig)) _cotVig[moneda] = await api('/cotizaciones/vigente?moneda=' + moneda).catch(() => null);
  const c = _cotVig[moneda];
  return c ? '≈ ' + fmtBase(monto / c.valor, moneda) : '';
}

// Completa en la página los textos de moneda base (<span class="mb">) y los <select data-monedas>.
function aplicarBase() {
  document.querySelectorAll('.mb').forEach(e => e.textContent = BASE);
  document.querySelectorAll('select[data-monedas]').forEach(s => opcionesMoneda(s));
}
CFG_LISTA.then(() => { if (document.readyState !== 'loading') aplicarBase(); else document.addEventListener('DOMContentLoaded', aplicarBase); });

// Llena un <select> con las monedas (la base primero). `sinBase`: excluye la moneda base.
function opcionesMoneda(sel, { sinBase = false, vacio = null } = {}) {
  const v = sel.value;
  const cods = [BASE, ...Object.keys(MONEDAS).filter(m => m !== BASE)].filter(m => !(sinBase && m === BASE));
  sel.innerHTML = (vacio ? `<option value="">${vacio}</option>` : '') + cods.map(m => `<option value="${m}">${m} · ${MONEDAS[m] || m}</option>`).join('');
  if (v && [...sel.options].some(o => o.value === v)) sel.value = v;
}

// El logo es opcional: solo se pide si la empresa cargó uno
function mostrarLogo() {
  const a = document.querySelector('header.top .logo-top');
  if (!a || !CFG || !CFG.tiene_logo) return;
  a.querySelector('img').src = '/api/config/logo?t=' + Date.now(); a.style.display = '';
}

function renderNav() {
  if (!document.querySelector('link[rel=icon]')) document.head.insertAdjacentHTML('beforeend', '<link rel="icon" href="favicon.ico">');
  let actual = location.pathname.split('/').pop() || 'index.html';
  if (actual === 'proyecto.html') actual = 'proyectos.html';
  const links = PAGINAS.map(([href, txt]) =>
    `<a href="${href}" class="${href === actual ? 'on' : ''}">${txt}</a>`).join('');
  document.body.insertAdjacentHTML('afterbegin',
    `<header class="top"><a class="logo-top" href="index.html" title="Inicio" style="display:none"><img alt="Logo"
       onerror="this.parentNode.style.display='none'"></a><div class="brand">${esc((CFG && CFG.empresa_nombre) || 'Presupuestos')}</div><nav>${links}</nav></header>`);
  CFG_LISTA.then(mostrarLogo);
  document.body.insertAdjacentHTML('beforeend', '<footer class="credito"><span><span id="pie-version">Presupuestos</span>'
    + ' · <a href="ayuda.html#licencia" title="Software libre bajo GPL-3.0, sin garantía">Software libre GPL-3.0</a></span>'
    + '<span class="cred">Desarrollo e Implementación: Lic. Eduardo J. Moreno</span></footer><div id="toast"></div>');
  fetch('/api/health').then(r => r.json()).then(h => { document.getElementById('pie-version').textContent = 'Presupuestos v' + h.version; }).catch(() => {});
}

async function api(path, opts = {}) {
  await CFG_LISTA;
  const init = { method: opts.method || 'GET', headers: {} };
  if (opts.body !== undefined) {
    init.headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(opts.body);
  }
  const r = await fetch('/api' + path, init);
  if (r.status === 204) return null;
  const data = await r.json().catch(() => ({}));
  if (!r.ok) {
    let msg = data.detail;
    if (Array.isArray(msg)) msg = msg.map(e => e.msg.replace('Value error, ', '')).join('; ');
    const err = new Error(msg || 'Error ' + r.status);
    err.status = r.status; err.data = data;
    throw err;
  }
  return data;
}

function toast(msg, error = false) {
  const t = document.getElementById('toast');
  t.textContent = msg; t.className = 'show' + (error ? ' err' : '');
  clearTimeout(t._h); t._h = setTimeout(() => t.className = '', 3500);
}

const fmtBase = (n, m = BASE) => n == null ? '—' : m + ' ' + n.toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2, useGrouping: 'always' });
const fmtNum = (n, d = 2) => n == null ? '—' : n.toLocaleString('es-AR', { minimumFractionDigits: d, maximumFractionDigits: d, useGrouping: 'always' });
const fmtPct = (n, d = 0) => n == null ? '—' : (n * 100).toLocaleString('es-AR', { maximumFractionDigits: d }) + '%';
const hoyISO = () => new Date().toLocaleDateString('sv-SE');
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const ayuda = txt => `<span class="help" data-tip="${esc(txt)}">?</span>`;

function datosForm(form) {
  const o = {};
  for (const el of form.elements) {
    if (!el.name) continue;
    if (el.type === 'checkbox') o[el.name] = el.checked;
    else if (el.value === '') o[el.name] = null;
    else if (el.type === 'number' || el.dataset.num) o[el.name] = Number(el.value) / (el.dataset.pct ? 100 : 1);
    else o[el.name] = el.value;
  }
  return o;
}

function llenarForm(form, obj) {
  for (const el of form.elements) {
    if (!el.name || !(el.name in obj)) continue;
    const v = obj[el.name];
    if (el.type === 'checkbox') el.checked = !!v;
    else if (v == null) el.value = '';
    else el.value = el.dataset.pct ? +(v * 100).toFixed(4) : v;
  }
}

// Colores de gráficos
const COLORES = { acento: '#2456c8', suave: '#9db5ea', gris: '#b7bec9', ok: '#1a7f37', warn: '#b26a00' };

document.addEventListener('DOMContentLoaded', renderNav);

// Fechas
const fmtFecha = iso => iso ? iso.slice(8, 10) + '/' + iso.slice(5, 7) + '/' + iso.slice(0, 4) : '—';
const sumarDias = (iso, n) => { const d = new Date(iso + 'T12:00:00'); d.setDate(d.getDate() + n); return d.toLocaleDateString('sv-SE'); };
const diasEntre = (a, b) => Math.round((new Date(b + 'T12:00:00') - new Date(a + 'T12:00:00')) / 864e5);
const lunesDe = iso => { const d = new Date(iso + 'T12:00:00'); const w = (d.getDay() + 6) % 7; return sumarDias(iso, -w); };

// Semáforos
function claseIndice(v) { if (v == null) return ''; return v >= 0.98 ? 'ok' : v >= 0.9 ? 'warn' : 'bad'; }
function claseMargen(m, alerta) { if (m == null) return ''; return m >= alerta ? 'ok' : m >= 0 ? 'warn' : 'bad'; }
const ESTADO_ETAPA = { 'terminada': 'ok', 'en curso': 'emp', 'atrasada': 'bad', 'no iniciada': '' };
const ESTADOS_PROY = { en_presupuesto: 'En presupuesto', en_curso: 'En curso', pausado: 'Pausado', terminado: 'Terminado', cancelado: 'Cancelado' };

// Barra de progreso con marca de lo planificado
function barraAvance(real, plan) {
  const r = Math.max(0, Math.min(1, real || 0)), p = plan == null ? null : Math.max(0, Math.min(1, plan));
  const atras = p != null && r + 0.02 < p;
  return `<div class="prog" title="Real ${fmtPct(r)}${p != null ? ' · planificado ' + fmtPct(p) : ''}">
    <div class="prog-fill ${atras ? 'atras' : ''}" style="width:${r * 100}%"></div>
    ${p != null ? `<div class="prog-plan" style="left:${p * 100}%"></div>` : ''}</div>`;
}

function descargar(url) { window.location.href = url; }  // el servidor responde como adjunto con su nombre

// ---------- Exportar (diálogo compartido por Inicio, Proyectos y cada proyecto) ----------
const DLG_EXPORTAR = `<dialog id="dlg-exportar" style="width:min(620px,94vw)">
  <h2>Exportar <span id="exp-proy" class="muted" style="font-weight:400"></span></h2>
  <form id="f-exportar">
    <p class="small muted" style="margin-top:-8px">Los documentos para el cliente salen en español o inglés y nunca muestran costos, márgenes ni personas. Usan la fecha de "Ver al".</p>
    <div class="exp-grupo">
      <strong>Para el cliente</strong>
      <label class="opt"><input type="radio" name="que" value="propuesta" checked> <span><b>Propuesta</b> — alcance por etapa, cronograma, actividades, horas estimadas y precio por etapa</span></label>
      <label class="opt"><input type="radio" name="que" value="avance"> <span><b>Informe de avance</b> — avance por etapa, hitos cumplidos y aprobaciones</span></label>
      <label class="opt"><input type="radio" name="que" value="dash_cliente"> <span><b>Dashboard interactivo (HTML)</b> — avance, cronograma y actividades</span></label>
    </div>
    <div class="exp-grupo">
      <strong>Uso interno</strong>
      <label class="opt"><input type="radio" name="que" value="excel_interno"> <span><b>Excel completo</b> — resumen, etapas, tareas, horas, gastos, curva S y costos</span></label>
      <label class="opt"><input type="radio" name="que" value="dash_interno"> <span><b>Dashboard interactivo (HTML)</b> — con CPI/SPI, margen, curva S y costos</span></label>
    </div>
    <div class="fields" id="exp-opciones" style="margin-top:12px">
      <label>Idioma<select name="idioma"><option value="es">Español</option><option value="en">English</option></select></label>
      <label>Formato<select name="formato"><option value="pdf">PDF</option><option value="xlsx">Excel</option></select></label>
      <label>Mostrar también en<select name="moneda"></select></label>
    </div>
    <p class="small muted" id="exp-aviso"></p>
    <div class="actions"><button type="button" onclick="this.closest('dialog').close()">Cancelar</button><button class="primary">Descargar</button></div>
  </form>
</dialog>`;
let EXP = null;
function abrirExportar(pid, nombre, precio, fechaFn) {
  if (!document.getElementById('dlg-exportar')) {
    document.body.insertAdjacentHTML('beforeend', DLG_EXPORTAR);
    const f = document.getElementById('f-exportar');
    f.addEventListener('change', ajustarExportar);
    f.addEventListener('submit', ev => { ev.preventDefault(); exportarAhora(); });
  }
  EXP = { pid, precio, fechaFn };
  const fm = document.getElementById('f-exportar').moneda;
  if (!fm.options.length) { opcionesMoneda(fm, { sinBase: true, vacio: 'Solo ' + BASE }); }
  document.getElementById('exp-proy').textContent = '· ' + nombre;
  ajustarExportar();
  document.getElementById('dlg-exportar').showModal();
}
function ajustarExportar() {
  const f = document.getElementById('f-exportar'), q = f.que.value, cli = q === 'propuesta' || q === 'avance';
  document.getElementById('exp-opciones').style.display = cli || q === 'dash_cliente' ? '' : 'none';
  f.formato.closest('label').style.display = cli ? '' : 'none';
  f.moneda.closest('label').style.display = q === 'propuesta' ? '' : 'none';
  document.getElementById('exp-aviso').textContent = q.startsWith('dash')
    ? 'Se descarga un único archivo .html que se abre con doble clic, sin el programa y sin internet. Se puede enviar por mail.'
    : (q === 'propuesta' && !EXP.precio ? 'Atención: el proyecto no tiene precio acordado; la propuesta saldrá sin importes.' : '');
}
function exportarAhora() {
  const f = document.getElementById('f-exportar'), q = f.que.value, pid = EXP.pid;
  const fecha = (EXP.fechaFn && EXP.fechaFn()) || hoyISO();
  const url = {
    propuesta: `/api/export/cliente/${pid}?tipo=propuesta&formato=${f.formato.value}&moneda=${f.moneda.value}&idioma=${f.idioma.value}&fecha=${fecha}`,
    avance: `/api/export/cliente/${pid}?tipo=avance&formato=${f.formato.value}&idioma=${f.idioma.value}&fecha=${fecha}`,
    dash_cliente: `/api/export/dashboard/${pid}?version=cliente&idioma=${f.idioma.value}&fecha=${fecha}`,
    dash_interno: `/api/export/dashboard/${pid}?version=interno&fecha=${fecha}`,
    excel_interno: `/api/export/proyecto/${pid}`,
  }[q];
  document.getElementById('dlg-exportar').close();
  comprobarYDescargar(url);
}
async function comprobarYDescargar(url) {
  // pide el archivo para mostrar errores legibles (p. ej. falta cotización) antes de descargar
  toast('Generando archivo…');
  const r = await fetch(url);
  if (!r.ok) { const d = await r.json().catch(() => ({})); return toast(d.detail || 'No se pudo exportar', true); }
  // nombre sin acentos (filename="..."): algunos navegadores descartan nombres con ñ o tildes
  const nombre = ((r.headers.get('content-disposition') || '').match(/filename="([^"]+)"/) || [])[1] || 'export';
  const blob = await r.blob(), a = document.createElement('a');
  a.href = URL.createObjectURL(blob); a.download = nombre; document.body.appendChild(a); a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 4000);
  toast('Descargado en la carpeta Descargas: ' + nombre);
}

// Números de los gráficos con formato argentino (1.234,56)
if (window.Chart) Chart.defaults.locale = 'es-AR';
