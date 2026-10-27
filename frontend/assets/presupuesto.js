// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
// Pestaña "Presupuesto" de un proyecto: versiones, editor de ítems desde el catálogo, estados y aprobación.
// Usa PID, P y cargar() de proyecto.html.
const ESTADO_PRES = { borrador: ['Borrador', ''], enviado: ['Enviado', 'emp'], aprobado: ['Aprobado', 'ok'], rechazado: ['Rechazado', 'bad'] };
let PR = { versiones: [], sel: null, d: null, roles: [], personas: [], servicios: [], etapas: [], timer: null };

async function cargarPresupuestos(seleccionar) {
  const [vs, roles, pers, servs, etapas] = await Promise.all([api(`/proyectos/${PID}/presupuestos`), api('/roles'),
    api('/personas?solo_activas=true'), api('/servicios?solo_activos=true'), api(`/proyectos/${PID}/etapas`)]);
  Object.assign(PR, { versiones: vs, roles, personas: pers, servicios: servs, etapas });
  const id = seleccionar || (PR.sel && vs.some(v => v.id === PR.sel) ? PR.sel : null)
    || (vs.find(v => v.estado === 'aprobado') || vs[vs.length - 1] || {}).id;
  pintarVersiones();
  if (id) await abrirVersion(id); else { PR.sel = null; PR.d = null; pintarEditor(); }
}

function pintarVersiones() {
  document.getElementById('pres-versiones').innerHTML = PR.versiones.map(v => {
    const [txt, cls] = ESTADO_PRES[v.estado];
    return `<tr style="cursor:pointer" class="${v.id === PR.sel ? 'sel' : ''}" onclick="abrirVersion(${v.id})">
      <td><strong>v${v.version}</strong></td><td><span class="tag ${cls}">${txt}</span></td>
      <td class="num">${v.n_items}</td><td class="num">${fmtNum(v.horas, 1)}</td><td class="num">${fmtBase(v.costo_total)}</td>
      <td class="num"><strong>${fmtBase(v.precio)}</strong></td><td class="num">${fmtPct(v.margen_real, 1)}</td>
      <td>${v.fecha_envio ? fmtFecha(v.fecha_envio) : '—'}</td><td>${v.fecha_aprobacion ? fmtFecha(v.fecha_aprobacion) : '—'}</td></tr>`;
  }).join('') || '<tr><td colspan="9" class="muted">Todavía no hay presupuestos. Creá la primera versión con "+ Nueva versión".</td></tr>';
}

async function abrirVersion(id) {
  PR.sel = id; PR.d = await api('/presupuestos/' + id);
  pintarVersiones(); pintarEditor();
}

async function nuevaVersion(copiar) {
  try {
    const d = await api(`/proyectos/${PID}/presupuestos`, { method: 'POST', body: { copiar_de: copiar || null } });
    toast(`Versión ${d.version} creada`); await cargarPresupuestos(d.id);
  } catch (e) { toast(e.message, true); }
}

const editable = () => PR.d && PR.d.estado === 'borrador';
const opts = (lista, val, vacio) => (vacio !== undefined ? `<option value="">${vacio}</option>` : '')
  + lista.map(([v, t]) => `<option value="${v}" ${String(v) === String(val ?? '') ? 'selected' : ''}>${esc(t)}</option>`).join('');

function pintarEditor() {
  const box = document.getElementById('pres-editor');
  if (!PR.d) { box.innerHTML = ''; return; }
  const d = PR.d, ed = editable(), dis = ed ? '' : 'disabled';
  const [txt, cls] = ESTADO_PRES[d.estado];
  const etapasNom = [...new Set([...PR.etapas.map(e => e.nombre), ...d.items.map(i => i.etapa).filter(Boolean)])];
  const acciones = {
    borrador: `<button onclick="estadoPres('enviado')">Marcar como enviado</button><button class="primary" onclick="aprobarPres()">Aprobar</button><button class="danger" onclick="borrarPres()">Borrar versión</button>`,
    enviado: `<button onclick="estadoPres('borrador')">Volver a borrador</button><button onclick="estadoPres('rechazado')">Rechazado</button><button class="primary" onclick="aprobarPres()">Aprobar</button>`,
    aprobado: '', rechazado: `<button onclick="estadoPres('borrador')">Reabrir como borrador</button>`,
  }[d.estado];
  box.innerHTML = `
  <div class="card" style="margin-top:16px">
    <div style="display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;align-items:center">
      <h2 style="margin:0">Versión ${d.version} <span class="tag ${cls}">${txt}</span></h2>
      <div class="bar-tools">${acciones}<button onclick="nuevaVersion(${d.id})">Nueva versión desde esta</button>
        <button class="primary" onclick="exportarPres()">Propuesta para el cliente</button></div>
    </div>
    ${d.estado === 'aprobado' ? `<p class="small muted">Aprobada el ${fmtFecha(d.fecha_aprobacion)}: los costos quedaron congelados, el precio pasó al proyecto${d.tiene_tareas_generadas ? ' y se generaron sus tareas' : ''}.</p>` : ''}
    ${d.estado === 'enviado' ? '<p class="small muted">Una versión enviada no se modifica: para cambiarla, creá una nueva versión desde esta.</p>' : ''}
    ${d.avisos.length ? `<div class="alert warn" style="margin-top:12px">${d.avisos.map(esc).join('<br>')}</div>` : ''}
    <div style="overflow-x:auto;margin-top:12px"><table class="pres-items">
      <thead><tr><th style="min-width:110px">Etapa</th><th style="min-width:200px">Actividad</th><th>Rol</th><th>Responsable</th>
        <th class="num">Horas</th><th class="num">% s/total</th><th class="num">Costo/h</th><th class="num">Costo</th><th></th></tr></thead>
      <tbody>${d.items.map((it, i) => `<tr data-i="${i}">
        <td><select data-k="etapa" ${dis}>${opts(etapasNom.map(n => [n, n]), it.etapa, '—')}</select></td>
        <td><input data-k="tarea" value="${esc(it.tarea)}" ${dis} style="width:100%">${it.servicio_nombre && it.servicio_nombre !== it.tarea ? `<div class="small muted">${esc(it.servicio_nombre)}</div>` : ''}</td>
        <td><select data-k="rol_id" ${dis}>${opts(PR.roles.map(r => [r.id, r.nombre]), it.rol_id, '—')}</select></td>
        <td><select data-k="persona_id" ${dis}>${opts(PR.personas.map(p => [p.id, p.nombre]), it.persona_id, 'según rol')}</select></td>
        <td class="num"><input class="celda" data-k="horas" type="number" step="0.5" min="0" value="${it.pct_sobre_total ? '' : it.horas_cargadas ?? it.horas}" ${dis || (it.pct_sobre_total ? 'disabled' : '')} title="${it.pct_sobre_total ? fmtNum(it.horas, 1) + ' h calculadas' : ''}"></td>
        <td class="num"><input class="celda" data-k="pct_sobre_total" type="number" step="1" min="0" max="100" value="${it.pct_sobre_total ? +(it.pct_sobre_total * 100).toFixed(2) : ''}" ${dis}></td>
        <td class="num"><input class="celda" style="width:90px" data-k="costo_hora_base" type="number" step="0.01" min="0" value="${it.costo_hora_manual ?? ''}" placeholder="${it.costo_hora != null ? fmtNum(it.costo_hora, 0) : '?'}" ${dis} title="${{ persona: 'Costo del responsable', rol: 'Promedio del rol', manual: 'Cargado a mano', congelado: 'Congelado al aprobar' }[it.origen_costo] || 'Sin costo'}"></td>
        <td class="num" data-c="costo">${it.costo == null ? '<span class="v-bad">sin costo</span>' : fmtBase(it.costo)}${it.pct_sobre_total ? `<div class="small muted">${fmtNum(it.horas, 1)} h</div>` : ''}</td>
        <td>${ed ? `<button class="link danger" onclick="quitarItem(${i})" title="Quitar">✕</button>` : ''}</td></tr>`).join('')
        || '<tr><td colspan="9" class="muted">Sin ítems. Agregalos desde el catálogo de servicios o como ítem libre.</td></tr>'}</tbody>
    </table></div>
    ${ed ? `<div class="bar-tools" style="margin-top:10px">
      <select id="pres-servicio" style="min-width:280px"><option value="">Agregar desde el catálogo…</option>${PR.servicios.map(s => `<option value="${s.id}">${esc(s.nombre)} · ${s.pct_sobre_total ? fmtPct(s.pct_sobre_total) + ' s/total' : fmtNum(s.horas_sugeridas, 0) + ' h'}</option>`).join('')}</select>
      <button onclick="agregarItem()">+ Ítem libre</button><a class="small" href="servicios.html">Editar catálogo</a></div>` : ''}

    <div class="grid g2" style="margin-top:20px;align-items:start">
      <div>
        <h3 style="font-size:14px;margin:0 0 8px">Gastos externos</h3>
        <table><thead><tr><th>Concepto</th><th>Moneda</th><th class="num">Importe</th><th class="num">${BASE}</th><th></th></tr></thead>
        <tbody>${d.externos.map((g, i) => `<tr data-g="${i}"><td><input data-k="concepto" value="${esc(g.concepto)}" ${dis} style="width:100%"></td>
          <td><select data-k="moneda" ${dis}>${opts(Object.keys(MONEDAS).map(m => [m, m]), g.moneda)}</select></td>
          <td class="num"><input class="celda" style="width:100px" data-k="importe" type="number" step="0.01" min="0" value="${g.importe}" ${dis}></td>
          <td class="num">${fmtNum(g.importe_base)}</td><td>${ed ? `<button class="link danger" onclick="quitarGasto(${i})">✕</button>` : ''}</td></tr>`).join('')
          || '<tr><td colspan="5" class="muted small">Sin gastos externos (licencias, hosting, impresión…).</td></tr>'}</tbody></table>
        ${ed ? '<button style="margin-top:8px" onclick="agregarGasto()">+ Gasto externo</button>' : ''}
        <div class="fields" style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:16px">
          <label>Margen objetivo (%)<input id="pres-margen" type="number" step="0.5" min="0" max="95" value="${+(d.margen * 100).toFixed(2)}" ${dis}></label>
          <label>Impuesto (%)<input id="pres-imp" type="number" step="0.5" min="0" max="100" value="${+(d.impuesto_pct * 100).toFixed(2)}" ${dis}></label>
          <label>Precio final (${BASE})<input id="pres-precio" type="number" step="1000" min="0" value="${d.precio_manual ?? ''}" placeholder="${fmtNum(d.resumen.precio_sugerido, 0)}" ${dis}></label>
          <label style="grid-column:1/-1">Moneda del contrato<select id="pres-moneda" ${dis}>${opts([BASE, ...Object.keys(MONEDAS).filter(m => m !== BASE)].map(m => [m, m === BASE ? m + ' (moneda base)' : m + ' · el precio queda fijo en ' + m + ' al aprobar']), d.moneda_contrato || BASE)}</select></label>
        </div>
        <label style="margin-top:12px">Notas internas<textarea id="pres-notas" rows="2" ${dis}>${esc(d.notas || '')}</textarea></label>
      </div>
      <div class="card" style="background:#fafbfc" id="pres-resumen"></div>
    </div>
  </div>`;
  pintarResumen();
  box.querySelectorAll('input, select, textarea').forEach(el => {
    if (el.id === 'pres-servicio') el.onchange = () => { if (el.value) agregarDesdeCatalogo(+el.value); };
    else el.addEventListener('change', programarGuardado);
  });
}

function pintarResumen() {
  const r = PR.d.resumen, al = (S && S.margen_alerta) || 0.25;
  const fila = (l, v, fuerte) => `<tr><td>${l}</td><td class="num">${fuerte ? '<strong>' + v + '</strong>' : v}</td></tr>`;
  document.getElementById('pres-resumen').innerHTML = `<h2>Resumen</h2><table>
    ${fila('Horas', fmtNum(r.horas, 1))}
    ${fila('Mano de obra (incluye estructura ' + fmtBase(r.tasa_estructura) + '/h)', fmtBase(r.costo_mano_obra))}
    ${fila('Gastos externos', fmtBase(r.costos_externos))}
    ${fila('Costo total', fmtBase(r.costo_total), true)}
    ${PR.d.estado === 'aprobado' ? '' : fila('Precio sugerido (' + fmtPct(PR.d.margen, 1) + ' de margen)', fmtBase(r.precio_sugerido))}
    ${fila('Precio', fmtBase(r.precio) + ' <div class="small muted" id="pres-eq"></div>', true)}
    ${fila('Ganancia', fmtBase(r.ganancia))}
    ${fila('Margen real', `<span class="v-${claseMargen(r.margen_real, al)}">${fmtPct(r.margen_real, 1)}</span>`, true)}
    ${r.impuesto ? fila('Impuesto', fmtBase(r.impuesto)) + fila('Total con impuesto', fmtBase(r.total), true) : ''}
    ${PR.d.contrato ? fila(`Precio del contrato en ${PR.d.contrato.moneda} (1 ${PR.d.contrato.moneda} = ${fmtNum(PR.d.contrato.cotizacion)} ${BASE})`, fmtBase(PR.d.contrato.precio, PR.d.contrato.moneda), true) : ''}
  </table>`;
  equivalente(r.precio).then(eq => { const e = document.getElementById('pres-eq'); if (e) e.textContent = eq; });
}

// ----- edición (se guarda sola un momento después de cada cambio) -----
function leerEditor() {
  const num = v => v === '' || v == null ? null : Number(v);
  const items = [...document.querySelectorAll('.pres-items tbody tr[data-i]')].map(tr => {
    const g = k => tr.querySelector(`[data-k=${k}]`).value, orig = PR.d.items[+tr.dataset.i];
    const pct = num(g('pct_sobre_total'));
    return { tarea: g('tarea').trim() || 'Actividad', etapa: g('etapa') || null, servicio_id: orig.servicio_id,
      rol_id: num(g('rol_id')), persona_id: num(g('persona_id')), horas: pct ? 0 : (num(g('horas')) || 0),
      pct_sobre_total: pct ? pct / 100 : null, costo_hora_base: num(g('costo_hora_base')),
      fecha_inicio: orig.fecha_inicio, fecha_fin: orig.fecha_fin };
  });
  const externos = [...document.querySelectorAll('[data-g]')].map(tr => ({
    concepto: tr.querySelector('[data-k=concepto]').value.trim() || 'Gasto', moneda: tr.querySelector('[data-k=moneda]').value,
    importe: Number(tr.querySelector('[data-k=importe]').value) || 0 })).filter(g => g.importe > 0);
  return { margen: (num(document.getElementById('pres-margen').value) || 0) / 100,
    impuesto: (num(document.getElementById('pres-imp').value) || 0) / 100,
    precio_base: num(document.getElementById('pres-precio').value), notas: document.getElementById('pres-notas').value || null,
    moneda_contrato: (v => v === BASE ? null : v)(document.getElementById('pres-moneda').value),
    items, externos };
}
function programarGuardado() { clearTimeout(PR.timer); PR.timer = setTimeout(() => guardarPres(), 400); }
async function guardarPres(datos, repintar = false) {
  if (!editable()) return;
  try {
    PR.d = await api('/presupuestos/' + PR.d.id, { method: 'PUT', body: datos || leerEditor() });
    if (repintar) pintarEditor(); else actualizarCostos();
    PR.versiones = await api(`/proyectos/${PID}/presupuestos`); pintarVersiones();
  } catch (e) { toast(e.message, true); }
}
function actualizarCostos() {  // refresca costos y resumen sin perder el foco de la celda
  PR.d.items.forEach((it, i) => {
    const tr = document.querySelector(`.pres-items tr[data-i="${i}"]`); if (!tr) return;
    tr.querySelector('[data-c=costo]').innerHTML = (it.costo == null ? '<span class="v-bad">sin costo</span>' : fmtBase(it.costo))
      + (it.pct_sobre_total ? `<div class="small muted">${fmtNum(it.horas, 1)} h</div>` : '');
    const ch = tr.querySelector('[data-k=costo_hora_base]'); ch.placeholder = it.costo_hora != null ? fmtNum(it.costo_hora, 0) : '?';
    tr.querySelector('[data-k=horas]').disabled = !!it.pct_sobre_total;
  });
  document.getElementById('pres-precio').placeholder = fmtNum(PR.d.resumen.precio_sugerido, 0);
  pintarResumen();
}
function agregarDesdeCatalogo(sid) {
  const s = PR.servicios.find(x => x.id === sid), d = leerEditor();
  d.items.push({ tarea: s.nombre, etapa: s.etapa_sugerida || null, servicio_id: s.id, rol_id: s.rol_sugerido_id,
    persona_id: null, horas: s.pct_sobre_total ? 0 : (s.horas_sugeridas || 0), pct_sobre_total: s.pct_sobre_total || null, costo_hora_base: null });
  guardarPres(d, true);
}
function agregarItem() { const d = leerEditor(); d.items.push({ tarea: 'Nueva actividad', horas: 1 }); guardarPres(d, true); }
function quitarItem(i) { const d = leerEditor(); d.items.splice(i, 1); guardarPres(d, true); }
function agregarGasto() {
  const d = leerEditor(); d.externos.push({ concepto: 'Gasto externo', moneda: BASE, importe: 1 }); guardarPres(d, true);
}
function quitarGasto(i) {
  const d = leerEditor(), filas = [...document.querySelectorAll('[data-g]')];
  d.externos = filas.filter((_, j) => j !== i).map(tr => ({ concepto: tr.querySelector('[data-k=concepto]').value,
    moneda: tr.querySelector('[data-k=moneda]').value, importe: Number(tr.querySelector('[data-k=importe]').value) || 0 }));
  guardarPres(d, true);
}

// ----- estados -----
async function estadoPres(estado) {
  try { PR.d = await api(`/presupuestos/${PR.d.id}/estado`, { method: 'POST', body: { estado } }); await cargarPresupuestos(PR.d.id); toast('Estado: ' + ESTADO_PRES[estado][0]); }
  catch (e) { toast(e.message, true); }
}
async function aprobarPres() {
  const genera = !tareas.length || confirm('El proyecto ya tiene tareas. ¿Agregar también las tareas de este presupuesto?\n(Aceptar = agregarlas, Cancelar = solo fijar el precio)');
  if (!confirm(`¿Aprobar la versión ${PR.d.version} por ${fmtBase(PR.d.resumen.precio)}?\nSe congelan los costos, el precio pasa al proyecto${genera ? ' y se generan las tareas' : ''}.`)) return;
  try {
    await api(`/presupuestos/${PR.d.id}/aprobar`, { method: 'POST', body: { generar_tareas: genera } });
    toast('Presupuesto aprobado'); await cargar(); await cargarPresupuestos(PR.sel);
  } catch (e) { toast(e.message, true); }
}
async function borrarPres() {
  if (!confirm(`¿Borrar la versión ${PR.d.version}?`)) return;
  try { await api('/presupuestos/' + PR.d.id, { method: 'DELETE' }); PR.sel = null; await cargarPresupuestos(); }
  catch (e) { toast(e.message, true); }
}

// ----- propuesta para el cliente -----
const DLG_PRES = `<dialog id="dlg-pres-exp" style="width:min(460px,94vw)"><h2>Propuesta para el cliente</h2>
  <form id="f-pres-exp"><p class="small muted" style="margin-top:-8px">Se arma con los ítems de esta versión, agrupados por etapa. No muestra costos, márgenes ni personas.</p>
  <div class="fields"><label>Idioma<select name="idioma"><option value="es">Español</option><option value="en">English</option></select></label>
  <label>Formato<select name="formato"><option value="pdf">PDF</option><option value="xlsx">Excel</option></select></label>
  <label class="full">Mostrar también en<select name="moneda"></select></label></div>
  <div class="actions"><button type="button" onclick="this.closest('dialog').close()">Cancelar</button><button class="primary">Descargar</button></div></form></dialog>`;
function exportarPres() {
  if (!document.getElementById('dlg-pres-exp')) {
    document.body.insertAdjacentHTML('beforeend', DLG_PRES);
    const f = document.getElementById('f-pres-exp');
    opcionesMoneda(f.moneda, { sinBase: true, vacio: 'Solo ' + BASE }); f.moneda.value = '';
    f.onsubmit = ev => { ev.preventDefault(); document.getElementById('dlg-pres-exp').close();
      comprobarYDescargar(`/api/export/presupuesto/${PR.d.id}?formato=${f.formato.value}&idioma=${f.idioma.value}&moneda=${f.moneda.value}`); };
  }
  document.getElementById('dlg-pres-exp').showModal();
}
