// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
// Pestaña "Facturación" del proyecto: registro interno de facturas y cobros.
const ESTADO_FACT = { pendiente: ['Pendiente', ''], parcial: ['Cobro parcial', 'emp'], vencida: ['Vencida', 'bad'],
  cobrada: ['Cobrada', 'ok'], anulada: ['Anulada', 'warn'] };
let FACT = null, facturaEdit = null, facturaCobro = null;

document.body.insertAdjacentHTML('beforeend', `
<dialog id="dlg-factura">
  <h2 id="tit-factura">Factura</h2>
  <form id="f-factura">
    <div class="fields">
      <label>Número<input name="numero" maxlength="40" placeholder="A-0001-00000123"></label>
      <label>Etapa / hito<select name="etapa_id" id="sel-fact-etapa"></select></label>
      <label class="full">Concepto<input name="concepto" maxlength="200" placeholder="Anticipo 40 %, entrega de diseño…"></label>
      <label>Fecha<input name="fecha" type="date" required></label>
      <label>Vencimiento<input name="vencimiento" type="date"></label>
      <label>Moneda<select name="moneda" data-monedas id="sel-fact-moneda"></select></label>
      <label id="lbl-fact-cot" hidden><span>Cotización (1 <span id="fact-mon"></span> = … <span class="mb"></span>)</span><input name="cotizacion" type="number" step="any" min="0" placeholder="la del día"></label>
      <label>Importe neto<input name="importe_neto" type="number" step="0.01" min="0.01" required></label>
      <label>Impuestos (IVA, etc.)<input name="impuesto" type="number" step="0.01" min="0" value="0"></label>
      <label style="flex-direction:row;align-items:center;gap:8px;margin-top:18px"><input type="checkbox" name="anulada"> Anulada</label>
      <label class="full">Notas<textarea name="notas" rows="2"></textarea></label>
    </div>
    <p class="small muted">Registro interno: el comprobante fiscal se emite en ARCA (AFIP) u otro sistema. La rentabilidad usa el importe neto.</p>
    <div class="actions" style="justify-content:space-between"><button type="button" class="danger" id="btn-borrar-factura" onclick="borrarFactura()">Borrar factura</button>
      <div style="display:flex;gap:8px"><button type="button" onclick="this.closest('dialog').close()">Cancelar</button><button class="primary">Guardar</button></div></div>
  </form>
</dialog>
<dialog id="dlg-cobro">
  <h2>Registrar cobro</h2>
  <p class="small muted" id="cobro-info"></p>
  <form id="f-cobro">
    <div class="fields">
      <label>Fecha<input name="fecha" type="date" required></label>
      <label><span>Importe (<span id="cobro-mon"></span>)</span><input name="importe" type="number" step="0.01" min="0.01" required></label>
      <label id="lbl-cobro-cot" hidden><span>Cotización del día (… <span class="mb"></span>)</span><input name="cotizacion" type="number" step="any" min="0" placeholder="la cargada para esa fecha"></label>
      <label class="full">Notas<input name="notas" placeholder="Transferencia, retenciones…"></label>
    </div>
    <div class="actions"><button type="button" onclick="this.closest('dialog').close()">Cancelar</button><button class="primary">Registrar</button></div>
  </form>
</dialog>`);

async function cargarFacturacion() {
  FACT = await api(`/proyectos/${PID}/facturas`);
  const F = FACT, m = F.moneda;
  const kpi = (l, v, n, cls) => `<div class="card kpi"><div class="label">${l}</div><div class="value ${cls || ''}">${v}</div><div class="note">${n}</div></div>`;
  document.getElementById('fact-kpis').innerHTML = [
    kpi('Facturado', fmtBase(F.facturado, m), F.precio != null ? `${fmtPct(F.pct_facturado)} del precio ${fmtBase(F.precio, m)}` : 'sin precio acordado'),
    kpi('Por facturar', fmtBase(F.por_facturar, m), F.por_facturar < 0 ? 'se facturó más que el precio' : 'neto, sin impuestos', F.por_facturar < 0 ? 'bad' : ''),
    kpi('Cobrado', fmtBase(F.cobrado_base), F.diferencia_cambio ? `diferencia de cambio ${fmtBase(F.diferencia_cambio)}` : 'a la cotización de cada cobro',
        F.diferencia_cambio < 0 ? 'warn' : ''),
    kpi('Saldo a cobrar', fmtBase(F.saldo_base), F.vencido_base ? `<span class="v-bad">vencido ${fmtBase(F.vencido_base)}</span>` : 'nada vencido',
        F.vencido_base ? 'bad' : ''),
  ].join('');
  document.getElementById('tabla-facturas').innerHTML = F.facturas.map(f => {
    const [txt, cls] = ESTADO_FACT[f.estado];
    const cobros = f.cobros.map(c => `<div>${fmtFecha(c.fecha)} · cobro ${fmtBase(c.importe, f.moneda)}`
      + (f.moneda !== BASE ? ` a ${fmtNum(c.cotizacion)} = ${fmtBase(c.importe_base)}${c.diferencia_cambio ? ` <span class="${c.diferencia_cambio < 0 ? 'v-bad' : 'v-ok'}">(diferencia de cambio ${fmtBase(c.diferencia_cambio)})</span>` : ''}` : '')
      + (c.notas ? ` · ${esc(c.notas)}` : '') + ` <button class="link danger" onclick="borrarCobro(${c.id})" title="Borrar cobro">×</button></div>`).join('');
    return `<tr class="${f.anulada ? 'muted' : ''} ${cobros ? 'con-sub' : ''}"><td><button class="link nowrap" onclick="abrirFactura(${f.id})">${esc(f.numero || 's/n')}</button>
        <div class="small muted">${esc(f.concepto || '')}${f.etapa_nombre ? ' · ' + esc(f.etapa_nombre) : ''}</div></td>
      <td class="nowrap">${fmtFecha(f.fecha)}</td><td class="nowrap">${fmtFecha(f.vencimiento)}${f.dias_vencida ? `<div class="small v-bad">hace ${f.dias_vencida} días</div>` : ''}</td>
      <td class="num">${fmtBase(f.total, f.moneda)}<div class="small muted">${f.impuesto ? `neto ${fmtNum(f.importe_neto)} + imp. ${fmtNum(f.impuesto)}` : 'sin impuestos'}</div>${f.moneda !== BASE ? `<div class="small muted">1 ${f.moneda} = ${fmtNum(f.cotizacion)} ${BASE}</div>` : ''}</td>
      <td class="num">${fmtBase(f.cobrado, f.moneda)}</td><td class="num">${fmtBase(f.saldo, f.moneda)}</td>
      <td><span class="tag ${cls}">${txt}</span></td>
      <td class="num">${f.saldo > 0 ? `<button onclick="abrirCobro(${f.id})">Cobrar</button>` : ''}</td></tr>`
      + (cobros ? `<tr class="sub"><td></td><td colspan="7" class="small muted">${cobros}</td></tr>` : '');
  }).join('') || '<tr><td colspan="8" class="muted">Sin facturas. Registrá el anticipo o las facturas por hito con "+ Factura".</td></tr>';
}

function abrirFactura(id) {
  facturaEdit = id ? FACT.facturas.find(f => f.id === id) : null;
  const f = document.getElementById('f-factura');
  f.reset();
  document.getElementById('tit-factura').textContent = facturaEdit ? 'Editar factura' : 'Nueva factura';
  document.getElementById('btn-borrar-factura').hidden = !facturaEdit;
  document.getElementById('sel-fact-etapa').innerHTML = '<option value="">—</option>'
    + S.etapas.filter(e => e.id).map(e => `<option value="${e.id}">${esc(e.nombre)}${e.hito ? ' · ' + esc(e.hito) : ''}</option>`).join('');
  opcionesMoneda(document.getElementById('sel-fact-moneda'));
  if (facturaEdit) llenarForm(f, facturaEdit);
  else {
    const pf = FACT.por_facturar;
    llenarForm(f, { fecha: hoyISO(), vencimiento: sumarDias(hoyISO(), 15), moneda: FACT.moneda, impuesto: 0,
      importe_neto: pf > 0 ? pf : null });
  }
  if (!facturaEdit) f.cotizacion.value = '';
  ajustarCotFactura();
  document.getElementById('dlg-factura').showModal();
}
function ajustarCotFactura() {
  const m = document.getElementById('sel-fact-moneda').value;
  document.getElementById('lbl-fact-cot').hidden = m === BASE;
  document.getElementById('fact-mon').textContent = m;
}
document.getElementById('sel-fact-moneda').addEventListener('change', ajustarCotFactura);
document.getElementById('f-factura').addEventListener('submit', async ev => {
  ev.preventDefault();
  const d = datosForm(ev.target);
  d.etapa_id = d.etapa_id ? Number(d.etapa_id) : null;
  if (d.moneda === BASE) d.cotizacion = null;
  try {
    await api(facturaEdit ? '/facturas/' + facturaEdit.id : `/proyectos/${PID}/facturas`,
      { method: facturaEdit ? 'PUT' : 'POST', body: d });
    document.getElementById('dlg-factura').close(); toast('Factura guardada'); cargarFacturacion();
  } catch (e) { toast(e.message, true); }
});
async function borrarFactura() {
  if (!confirm('¿Borrar la factura y sus cobros? Si fue emitida, mejor marcala como anulada.')) return;
  await api('/facturas/' + facturaEdit.id, { method: 'DELETE' });
  document.getElementById('dlg-factura').close(); cargarFacturacion();
}

function abrirCobro(id) {
  facturaCobro = FACT.facturas.find(f => f.id === id);
  const f = document.getElementById('f-cobro'), x = facturaCobro;
  f.reset();
  document.getElementById('cobro-info').textContent = `Factura ${x.numero || 's/n'} · total ${fmtBase(x.total, x.moneda)} · saldo ${fmtBase(x.saldo, x.moneda)}`
    + (x.moneda !== BASE ? ` · facturada a 1 ${x.moneda} = ${fmtNum(x.cotizacion)} ${BASE}` : '');
  document.getElementById('cobro-mon').textContent = x.moneda;
  document.getElementById('lbl-cobro-cot').hidden = x.moneda === BASE;
  llenarForm(f, { fecha: hoyISO(), importe: x.saldo });
  document.getElementById('dlg-cobro').showModal();
}
document.getElementById('f-cobro').addEventListener('submit', async ev => {
  ev.preventDefault();
  const d = datosForm(ev.target);
  try {
    await api(`/facturas/${facturaCobro.id}/cobros`, { method: 'POST', body: d });
    document.getElementById('dlg-cobro').close(); toast('Cobro registrado'); cargarFacturacion();
  } catch (e) { toast(e.message, true); }
});
async function borrarCobro(id) {
  if (!confirm('¿Borrar este cobro?')) return;
  await api('/cobros/' + id, { method: 'DELETE' }); cargarFacturacion();
}
