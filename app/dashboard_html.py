# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
"""Dashboard interactivo en un único archivo HTML (sin servidor ni internet).

Dos versiones:
- "interno" (español): avance, CPI/SPI, margen, curva S en moneda base, costo por persona y tareas con costos.
- "cliente" (español o inglés): avance, etapas, hitos, aprobaciones y actividades, sin costos ni personas.
Ambas llevan el logo de la empresa (si se cargó) a la izquierda de la barra de título.
Chart.js y el logo van embebidos en el archivo.
"""
from __future__ import annotations

import base64
import json
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from . import CREDITO, costeo, documentos, licencia, seguimiento
from .config import frontend_dir, logo_efectivo
from .models import Proyecto


def _json(o):
    if isinstance(o, (date, datetime)):
        return o.isoformat()
    if isinstance(o, Decimal):
        return float(o)
    if hasattr(o, "value"):
        return o.value
    raise TypeError(type(o))


def _logo_data_url() -> str | None:
    p = logo_efectivo()
    return "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode() if p else None


def _gantt(p: Proyecto, m: dict, hoy: date, con_personas: bool) -> list[dict]:
    filas = []
    tareas = sorted(p.tareas, key=lambda t: (t.fecha_inicio, t.orden))
    ids = {e["id"] for e in m["etapas"]}
    for e in m["etapas"]:
        filas.append(dict(tipo="etapa", nombre=e["nombre"] if e["id"] is not None else "—",
                          inicio=e["inicio_previsto"], fin=e["fin_previsto"], inicio_real=e["inicio_real"],
                          fin_real=e["fin_real"], avance=e["avance"], atrasada=e["estado"] == "atrasada",
                          hito=e["hito"], hito_cumplido=e["hito_cumplido"]))
        for t in tareas:
            if t.etapa_id == e["id"] or (e["id"] is None and t.etapa_id not in ids):
                av = seguimiento.avance_tarea(t, hoy)
                filas.append(dict(tipo="tarea", nombre=t.nombre,
                                  sub=(t.persona.nombre if (con_personas and t.persona) else ""),
                                  inicio=t.fecha_inicio, fin=t.fecha_fin, inicio_real=t.inicio_real,
                                  fin_real=t.fin_real, avance=av, atrasada=t.fecha_fin < hoy and av < 0.999))
    return filas


def generar(db: Session, p: Proyecto, version: str, a_fecha: date | None = None, idioma: str = "es") -> str:
    hoy = a_fecha or date.today()
    m = seguimiento.metricas(db, p, hoy)
    curva = seguimiento.curva_s(db, p, hoy)
    cliente = version == "cliente"
    idioma = idioma if (cliente and idioma == "en") else "es"
    datos = dict(version=version, hoy=hoy, idioma=idioma, moneda=costeo.moneda_base(db), generado=datetime.now().strftime("%d/%m/%Y %H:%M"),
                 credito=CREDITO, logo=_logo_data_url(),
                 empresa=costeo.config(db).empresa_nombre or "",
                 registro="" if version == "cliente" else licencia.leyenda_interna(db),
                 gantt=_gantt(p, m, hoy, con_personas=not cliente))
    if cliente:
        d = documentos.datos(db, p, hoy, None, idioma)
        datos.update(proyecto=d["proyecto"], avance=d["avance"], avance_planificado=d["avance_planificado"],
                     etapas_terminadas=d["etapas_terminadas"], etapas_aprobadas=d["etapas_aprobadas"],
                     proximo_hito=d["proximo_hito"],
                     etapas=[{k: e[k] for k in ("nombre", "inicio", "fin", "hito", "hito_cumplido", "aprobada",
                                                "fecha_aprobacion", "horas", "avance", "avance_planificado", "estado",
                                                "estado_cod")}
                             for e in d["etapas"]],
                     actividades=[dict(etapa=e["nombre"], nombre=t["nombre"], inicio=t["inicio"], fin=t["fin"],
                                       avance=t["avance"]) for e in d["etapas"] for t in e["tareas"]],
                     curva=[dict(fecha=c["fecha"], plan=(c["pv"] / m["bac"]) if m["bac"] else None,
                                 real=(c["ev"] / m["bac"]) if (m["bac"] and c["ev"] is not None) else None)
                            for c in curva])
    else:
        etapas_n = {e["id"]: e["nombre"] for e in m["etapas"]}
        tareas = []
        for t in sorted(p.tareas, key=lambda t: (t.fecha_inicio, t.orden)):
            tareas.append(dict(etapa=etapas_n.get(t.etapa_id, "Sin etapa"), nombre=t.nombre,
                               persona=t.persona.nombre if t.persona else "", inicio=t.fecha_inicio, fin=t.fecha_fin,
                               horas_prev=t.horas_previstas, horas_real=sum(h.horas for h in t.horas if h.fecha <= hoy),
                               costo_prev=float(t.costo_previsto_base),
                               costo_real=sum(h.horas * float(h.costo_hora_base) for h in t.horas if h.fecha <= hoy),
                               avance=seguimiento.avance_tarea(t, hoy)))
        datos.update(proyecto=dict(nombre=p.nombre, cliente=p.cliente.nombre if p.cliente else "",
                                   inicio=p.fecha_inicio, fin=p.fecha_fin),
                     m={k: v for k, v in m.items() if k != "etapas"}, etapas=m["etapas"], curva=curva,
                     por_persona=seguimiento.costo_por_persona(p, hoy), tareas=tareas,
                     margen_alerta=costeo.config(db).margen_alerta)
    chart_js = (frontend_dir() / "assets" / "vendor" / "chart.umd.min.js").read_text(encoding="utf-8")
    titulo = ("Project dashboard" if idioma == "en" else "Tablero del proyecto") + f" · {p.nombre}"
    return (PLANTILLA.replace("__TITULO__", _html(titulo))
            .replace("__LANG__", idioma)
            .replace("__CHARTJS__", chart_js.replace("</script", "<\\/script"))
            .replace("__DATOS__", json.dumps(datos, default=_json, ensure_ascii=False).replace("</", "<\\/")))


def _html(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


PLANTILLA = r"""<!doctype html>
<html lang="__LANG__">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITULO__</title>
<style>
:root { --bg:#f5f6f8; --panel:#fff; --ink:#1c2230; --muted:#5d6677; --line:#e3e6eb; --accent:#2456c8; --soft:#e8eefb;
  --ok:#1a7f37; --warn:#b26a00; --bad:#c62828; }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--ink); font:14px/1.45 "Segoe UI", system-ui, -apple-system, sans-serif; }
header { background:#fff; color:#1c2230; padding:16px 24px; border-bottom:1px solid var(--line); box-shadow:0 1px 3px rgba(20,25,35,.05); }
header .in { max-width:1180px; margin:0 auto; display:flex; gap:20px; align-items:center; justify-content:flex-start; flex-wrap:wrap; }
header img { height:48px; width:auto; max-width:240px; }
header h1 { margin:0; font-size:20px; color:#1c2230; } header .sub { color:#5d6677; font-size:13px; margin-top:2px; }
header .tit { border-left:1px solid var(--line); padding-left:20px; }
header img[hidden] + .tit { border-left:none; padding-left:0; }
main { max-width:1180px; margin:20px auto; padding:0 16px; }
.grid { display:grid; gap:16px; } .g4 { grid-template-columns:repeat(auto-fit,minmax(210px,1fr)); }
.g2 { grid-template-columns:repeat(auto-fit,minmax(340px,1fr)); }
.card { background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:18px 20px; }
.card h2 { font-size:15px; margin:0 0 12px; }
.kpi .l { color:var(--muted); font-size:12.5px; } .kpi .v { font-size:26px; font-weight:600; margin-top:2px; }
.kpi .n { color:var(--muted); font-size:12px; margin-top:4px; }
.ok { color:var(--ok); } .warn { color:var(--warn); } .bad { color:var(--bad); }
.prog { position:relative; height:8px; background:#e9ecf1; border-radius:99px; margin-top:8px; }
.prog i { position:absolute; left:0; top:0; bottom:0; background:var(--accent); border-radius:99px; }
.prog i.atras { background:var(--warn); } .prog b { position:absolute; top:-3px; bottom:-3px; width:2px; background:#1c2230; }
.etapas { display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:12px; }
.etapa { border:1px solid var(--line); border-radius:8px; padding:12px 14px; cursor:pointer; background:#fff; }
.etapa:hover, .etapa.sel { border-color:#9db5ea; background:#fbfcff; }
.etapa .c { display:flex; justify-content:space-between; gap:6px; align-items:center; }
.etapa .nm { font-weight:600; } .etapa .ln { font-size:12px; color:var(--muted); margin-top:5px; }
.tag { display:inline-block; padding:2px 8px; border-radius:99px; font-size:11px; background:#eef0f3; color:var(--muted); white-space:nowrap; }
.tag.ok { background:#e3f4e8; color:var(--ok); } .tag.bad { background:#fdecec; color:var(--bad); } .tag.on { background:var(--soft); color:var(--accent); }
.gantt { overflow-x:auto; } .gantt svg { display:block; min-width:760px; }
.ley { display:flex; gap:14px; flex-wrap:wrap; font-size:12px; color:var(--muted); margin-top:8px; }
.ley span { display:inline-flex; gap:6px; align-items:center; } .ley i { display:inline-block; width:14px; height:8px; border-radius:2px; }
.box { position:relative; height:280px; }
table { width:100%; border-collapse:collapse; } th, td { text-align:left; padding:7px 9px; border-bottom:1px solid var(--line); vertical-align:top; }
th { font-size:11.5px; color:var(--muted); text-transform:uppercase; letter-spacing:.03em; cursor:pointer; user-select:none; white-space:nowrap; }
th:hover { color:var(--ink); } td.num, th.num { text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }
.filtros { display:flex; gap:10px; flex-wrap:wrap; margin-bottom:10px; }
input, select { font:inherit; padding:6px 10px; border:1px solid #cfd4dc; border-radius:6px; background:#fff; }
footer { max-width:1180px; margin:24px auto 32px; padding:0 16px; color:var(--muted); font-size:12px; display:flex; justify-content:space-between; gap:12px; flex-wrap:wrap; }
footer .cred { font-style:italic; }
@media print { header { -webkit-print-color-adjust:exact; print-color-adjust:exact; } .card { break-inside:avoid; } }
</style>
<script>__CHARTJS__</script>
</head>
<body>
<header><div class="in"><img id="logo" alt="" hidden><div class="tit"><h1 id="titulo"></h1><div class="sub" id="sub"></div></div></div></header>
<main>
  <div class="grid g4" id="kpis"></div>
  <div class="card" style="margin-top:16px"><h2 id="t-etapas"></h2><div class="etapas" id="etapas"></div></div>
  <div class="card" style="margin-top:16px"><h2 id="t-gantt"></h2><div class="gantt" id="gantt"></div><div class="ley" id="ley"></div></div>
  <div class="grid g2" style="margin-top:16px">
    <div class="card"><h2 id="t-g1"></h2><div class="box"><canvas id="g1"></canvas></div></div>
    <div class="card"><h2 id="t-g2"></h2><div class="box"><canvas id="g2"></canvas></div></div>
  </div>
  <div class="card" style="margin-top:16px"><h2 id="t-tabla"></h2>
    <div class="filtros"><select id="f-etapa"></select><input id="f-texto" type="search"></div>
    <div style="overflow-x:auto"><table id="tabla"></table></div></div>
</main>
<footer><span id="pie"></span><span class="cred" id="cred"></span></footer>
<script>
const D = __DATOS__;
const CLI = D.version === 'cliente';
const EN = D.idioma === 'en';
const CLASE = {'no iniciada':'', 'en curso':'on', 'terminada':'ok', 'atrasada':'bad'};
const T = EN ? {
  sub: 'Client: {c} · {i} – {f} · Status as of {h}', etapas: 'Stages', gantt: 'Timeline: planned vs actual',
  g1: 'Progress over time', g2: 'Progress by stage', tabla: 'Activities', todas: 'All stages', buscar: 'Search activity…',
  real: 'Actual', plan: 'Planned', hoy: 'Today', pie: 'Generated {g}{e}',
  ley: ['Planned period', 'Progress', 'Progress of an overdue item', 'Actual execution', 'Milestone delivered', 'Today'],
  k1: 'Overall progress', k1n: 'planned to date', k2: 'Stages completed', k2n: 'stages finished', k3: 'Client approvals',
  k3n: 'stages approved', k4: 'Next milestone', k4n: 'all milestones delivered', aprob: 'Approved', pend: 'Pending approval',
  cols: ['Stage', 'Activity', 'Start', 'End', 'Progress'],
} : CLI ? {
  sub: 'Cliente: {c} · {i} – {f} · Estado al {h}', etapas: 'Etapas', gantt: 'Cronograma: previsto vs real',
  g1: 'Avance en el tiempo', g2: 'Avance por etapa', tabla: 'Actividades', todas: 'Todas las etapas', buscar: 'Buscar actividad…',
  real: 'Real', plan: 'Planificado', hoy: 'Hoy', pie: 'Generado el {g}{e}',
  ley: ['Período previsto', 'Avance', 'Avance de una actividad vencida', 'Ejecución real', 'Hito entregado', 'Hoy'],
  k1: 'Avance general', k1n: 'planificado a la fecha', k2: 'Etapas terminadas', k2n: 'etapas finalizadas', k3: 'Aprobaciones del cliente',
  k3n: 'etapas aprobadas', k4: 'Próximo hito', k4n: 'todos los hitos entregados', aprob: 'Aprobada', pend: 'Pendiente de aprobación',
  cols: ['Etapa', 'Actividad', 'Inicio', 'Fin', 'Avance'],
} : {
  sub: 'Cliente: {c} · {i} – {f} · Datos al {h}', etapas: 'Etapas', gantt: 'Cronograma: previsto vs real',
  g1: `Curva S (${D.moneda} acumulados)`, g2: 'Costo por persona: previsto vs real a la fecha', tabla: 'Tareas', todas: 'Todas las etapas', buscar: 'Buscar tarea o persona…',
  real: 'Real', plan: 'Planificado', hoy: 'Hoy', pie: 'Generado el {g}{e} · uso interno',
  ley: ['Plazo previsto', 'Avance', 'Avance de tarea vencida', 'Ejecución real', 'Hito cumplido', 'Hoy'],
  aprob: 'Aprobada', pend: 'Sin aprobación',
};
const loc = EN ? 'en-GB' : 'es-AR';
const pct = (v, d = 0) => v == null ? '—' : (v * 100).toLocaleString(loc, { maximumFractionDigits: d }) + '%';
const num = (v, d = 2) => v == null ? '—' : v.toLocaleString(loc, { minimumFractionDigits: d, maximumFractionDigits: d, useGrouping: 'always' });
const mon = v => v == null ? '—' : D.moneda + ' ' + num(v);
const MES = EN ? ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'] : ['ene','feb','mar','abr','may','jun','jul','ago','sep','oct','nov','dic'];
const fec = s => s ? `${s.slice(8,10)} ${MES[+s.slice(5,7)-1]} ${s.slice(0,4)}` : '—';
const fc = s => s ? `${s.slice(8,10)}/${s.slice(5,7)}` : '';
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = (s, o) => s.replace(/\{(\w)\}/g, (_, k) => o[k] ?? '');
const dias = (a, b) => Math.round((new Date(b + 'T12:00:00') - new Date(a + 'T12:00:00')) / 864e5);
const suma = (iso, n) => { const d = new Date(iso + 'T12:00:00'); d.setDate(d.getDate() + n); return d.toISOString().slice(0, 10); };
const clsI = v => v == null ? '' : v >= .98 ? 'ok' : v >= .9 ? 'warn' : 'bad';
const barra = (r, p) => `<div class="prog"><i class="${p != null && r + .02 < p ? 'atras' : ''}" style="width:${Math.min(r || 0, 1) * 100}%"></i>${p != null ? `<b style="left:${Math.min(p, 1) * 100}%"></b>` : ''}</div>`;

document.title = (EN ? 'Project dashboard · ' : 'Tablero · ') + D.proyecto.nombre;
document.getElementById('titulo').textContent = D.proyecto.nombre;
document.getElementById('sub').textContent = fmt(T.sub, { c: D.proyecto.cliente, i: fec(D.proyecto.inicio), f: fec(D.proyecto.fin), h: fec(D.hoy) });
if (D.logo) { const l = document.getElementById('logo'); l.src = D.logo; l.hidden = false; }
['etapas', 'gantt', 'g1', 'g2', 'tabla'].forEach(k => document.getElementById('t-' + k).textContent = T[k]);
document.getElementById('pie').textContent = fmt(T.pie, { g: D.generado, e: D.empresa ? ' · ' + D.empresa : '' }) + (D.registro ? ' · ' + D.registro : '');
document.getElementById('cred').textContent = D.credito;

// KPIs
const kpi = (l, v, n, c) => `<div class="card kpi"><div class="l">${l}</div><div class="v ${c || ''}">${v}</div><div class="n">${n}</div></div>`;
if (CLI) {
  const ph = D.proximo_hito;
  document.getElementById('kpis').innerHTML = [
    kpi(T.k1, pct(D.avance), barra(D.avance, D.avance_planificado) + `<div style="margin-top:6px">${T.k1n}: ${pct(D.avance_planificado)}</div>`, D.avance + .02 < D.avance_planificado ? 'warn' : 'ok'),
    kpi(T.k2, `${D.etapas_terminadas} / ${D.etapas.length}`, T.k2n),
    kpi(T.k3, `${D.etapas_aprobadas} / ${D.etapas.length}`, T.k3n),
    kpi(T.k4, ph ? fec(ph.fecha) : '—', ph ? esc(ph.hito) + ' · ' + esc(ph.etapa) : T.k4n),
  ].join('');
} else {
  const m = D.m, al = D.margen_alerta;
  const cm = v => v == null ? '' : v >= al ? 'ok' : v >= 0 ? 'warn' : 'bad';
  document.getElementById('kpis').innerHTML = [
    kpi('Avance ponderado', pct(m.avance_ponderado), barra(m.avance_ponderado, m.avance_planificado) + `<div style="margin-top:6px">planificado: ${pct(m.avance_planificado)}</div>`, m.avance_ponderado + .02 < m.avance_planificado ? 'warn' : ''),
    kpi('Eficiencia en costo (CPI)', num(m.cpi), `ganado ${mon(m.ev)} / real ${mon(m.ac)}`, clsI(m.cpi)),
    kpi('Eficiencia en plazo (SPI)', num(m.spi), `ganado ${mon(m.ev)} / planificado ${mon(m.pv)}`, clsI(m.spi)),
    kpi('Margen proyectado', pct(m.margen_proyectado, 1), `previsto ${pct(m.margen_previsto, 1)} · costo final est. ${mon(m.eac)}`, cm(m.margen_proyectado)),
  ].join('');
}

// Etapas (clic = filtrar la tabla)
const etapas = D.etapas;
document.getElementById('etapas').innerHTML = etapas.map((e, i) => {
  const est = e.estado, cls = CLASE[CLI ? e.estado_cod : e.estado] ?? '';
  const ini = CLI ? e.inicio : e.inicio_previsto, fin = CLI ? e.fin : e.fin_previsto;
  const aprob = CLI ? e.aprobada : e.aprobada_cliente;
  return `<div class="etapa" data-i="${i}"><div class="c"><span class="nm">${esc(e.nombre)}</span><span class="tag ${cls}">${esc(est)}</span></div>
    ${barra(e.avance, e.avance_planificado)}
    <div class="ln"><b style="color:var(--ink)">${pct(e.avance)}</b>${CLI ? ` · ${num(e.horas, 0)} h` : ` · peso ${pct(e.peso_efectivo)}`}</div>
    <div class="ln">${fec(ini)} – ${fec(fin)}</div>
    ${e.hito ? `<div class="ln">${e.hito_cumplido ? '<span class="ok">◆</span>' : '◇'} ${esc(e.hito)}</div>` : ''}
    <div class="ln">${aprob ? `<span class="ok">✓ ${T.aprob} ${fec(e.fecha_aprobacion)}</span>` : T.pend}</div></div>`;
}).join('');
document.querySelectorAll('.etapa').forEach(el => el.onclick = () => {
  const n = etapas[+el.dataset.i].nombre, s = document.getElementById('f-etapa');
  s.value = s.value === n ? '' : n; pintarTabla();
  document.querySelectorAll('.etapa').forEach(x => x.classList.toggle('sel', x === el && s.value !== ''));
});

// Cronograma
function gantt() {
  const cont = document.getElementById('gantt'), hoy = D.hoy, F = D.gantt;
  const fs = [D.proyecto.inicio, D.proyecto.fin, hoy];
  F.forEach(r => fs.push(r.inicio, r.fin, r.inicio_real, r.fin_real));
  const o = fs.filter(Boolean).sort(), ini = suma(o[0], -2), fin = suma(o[o.length - 1], 3), tot = dias(ini, fin);
  const W = Math.max(cont.clientWidth, 760), L = 230, AX = 30, FI = 28;
  const X = d => L + dias(ini, d) / tot * (W - L - 16);
  const H = AX + F.length * FI + 14;
  let s = `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" font-family="Segoe UI, system-ui, sans-serif" font-size="12">`;
  const d0 = new Date(ini + 'T12:00:00'); d0.setDate(d0.getDate() - ((d0.getDay() + 6) % 7));
  for (let d = d0.toISOString().slice(0, 10); d <= fin; d = suma(d, 7)) if (d >= ini)
    s += `<line x1="${X(d)}" x2="${X(d)}" y1="${AX - 6}" y2="${H}" stroke="#eef0f3"/><text x="${X(d) + 3}" y="${AX - 11}" fill="#5d6677" font-size="11">${fc(d)}</text>`;
  F.forEach((r, i) => {
    const y = AX + i * FI, cy = y + FI / 2, et = r.tipo === 'etapa';
    if (et) s += `<rect x="0" y="${y}" width="${W}" height="${FI}" fill="#f7f8fa"/>`;
    const nm = r.nombre.length > 30 ? r.nombre.slice(0, 29) + '…' : r.nombre;
    s += `<text x="${et ? 8 : 20}" y="${cy + (r.sub ? 0 : 4)}" ${et ? 'font-weight="600"' : ''} fill="#1c2230">${esc(nm)}<title>${esc(r.nombre)}</title></text>`;
    if (r.sub) s += `<text x="20" y="${cy + 11}" fill="#8a93a3" font-size="10.5">${esc(r.sub)}</text>`;
    s += `<text x="${L - 8}" y="${cy + 4}" text-anchor="end" fill="#5d6677" font-size="11">${pct(r.avance)}</text>`;
    if (r.inicio && r.fin) {
      const x1 = X(r.inicio), x2 = X(suma(r.fin, 1)), h = et ? 12 : 10;
      s += `<g><title>${esc(r.nombre)}: ${fec(r.inicio)} – ${fec(r.fin)} · ${pct(r.avance)}</title><rect x="${x1}" y="${cy - h / 2}" width="${Math.max(x2 - x1, 2)}" height="${h}" rx="3" fill="${et ? '#dbe5f8' : '#eef3fc'}" stroke="${et ? '#9db5ea' : '#b9cbef'}"/>`;
      s += `<rect x="${x1}" y="${cy - h / 2}" width="${Math.max((x2 - x1) * Math.min(r.avance || 0, 1), 0)}" height="${h}" rx="3" fill="${r.atrasada ? '#b26a00' : '#2456c8'}"/></g>`;
      if (et && r.hito) s += `<path d="M${x2} ${cy - 7} l7 7 l-7 7 l-7 -7z" fill="${r.hito_cumplido ? '#1a7f37' : '#fff'}" stroke="${r.hito_cumplido ? '#1a7f37' : '#5d6677'}"><title>${esc(r.hito)}</title></path>`;
    }
    if (r.inicio_real) { const a = X(r.inicio_real), b = X(r.fin_real ? suma(r.fin_real, 1) : hoy); s += `<rect x="${a}" y="${cy + (et ? 8 : 7)}" width="${Math.max(b - a, 2)}" height="2.5" fill="#5d6677"/>`; }
  });
  if (hoy >= ini && hoy <= fin) s += `<line x1="${X(hoy)}" x2="${X(hoy)}" y1="${AX - 4}" y2="${H}" stroke="#c62828" stroke-dasharray="4 3"/><text x="${X(hoy)}" y="${H - 2}" text-anchor="middle" fill="#c62828" font-size="10.5" font-weight="600" paint-order="stroke" stroke="#fff" stroke-width="3">${T.hoy}</text>`;
  cont.innerHTML = s + `<line x1="${L}" x2="${L}" y1="${AX - 6}" y2="${H}" stroke="#e3e6eb"/></svg>`;
}
const L_ = T.ley, col = ['background:#dbe5f8;border:1px solid #9db5ea', 'background:#2456c8', 'background:#b26a00', 'background:#5d6677;height:3px', 'background:#1a7f37;transform:rotate(45deg);width:9px;height:9px', 'border-left:2px dashed #c62828;width:2px;height:12px;border-radius:0'];
document.getElementById('ley').innerHTML = L_.map((t, i) => `<span><i style="${col[i]}"></i>${t}</span>`).join('');
gantt(); addEventListener('resize', () => { clearTimeout(window._r); window._r = setTimeout(gantt, 150); });

// Gráficos
const C = { a: '#2456c8', g: '#b7bec9', w: '#b26a00' };
const optsPct = { maintainAspectRatio: false, interaction: { mode: 'index', intersect: false },
  scales: { y: { min: 0, max: 1, ticks: { callback: v => pct(v) } } }, plugins: { tooltip: { callbacks: { label: c => c.dataset.label + ': ' + pct(c.raw, 1) } } } };
if (CLI) {
  new Chart(document.getElementById('g1'), { type: 'line', options: optsPct, data: { labels: D.curva.map(c => fc(c.fecha)), datasets: [
    { label: T.plan, data: D.curva.map(c => c.plan), borderColor: C.g, backgroundColor: C.g, borderDash: [5, 4], pointRadius: 0, tension: .2 },
    { label: T.real, data: D.curva.map(c => c.real), borderColor: C.a, backgroundColor: C.a, pointRadius: 2, tension: .2 } ] } });
  new Chart(document.getElementById('g2'), { type: 'bar', options: { ...optsPct, indexAxis: 'y', interaction: { mode: 'index', axis: 'y', intersect: false }, scales: { x: { min: 0, max: 1, ticks: { callback: v => pct(v) } } } },
    data: { labels: etapas.map(e => e.nombre), datasets: [
      { label: T.real, data: etapas.map(e => e.avance), backgroundColor: etapas.map(e => e.estado_cod === 'atrasada' ? C.w : C.a) },
      { label: T.plan, data: etapas.map(e => e.avance_planificado), backgroundColor: C.g } ] } });
} else {
  const ou = { maintainAspectRatio: false, interaction: { mode: 'index', intersect: false },
    plugins: { tooltip: { callbacks: { label: c => c.dataset.label + ': ' + mon(c.raw) } } } };
  new Chart(document.getElementById('g1'), { type: 'line', options: { ...ou, scales: { y: { title: { display: true, text: D.moneda } } } },
    data: { labels: D.curva.map(c => fc(c.fecha)), datasets: [
      { label: 'Planificado (PV)', data: D.curva.map(c => c.pv), borderColor: C.g, backgroundColor: C.g, borderDash: [5, 4], pointRadius: 0, tension: .2 },
      { label: 'Ganado (EV)', data: D.curva.map(c => c.ev), borderColor: C.a, backgroundColor: C.a, pointRadius: 2, tension: .2 },
      { label: 'Real (AC)', data: D.curva.map(c => c.ac), borderColor: C.w, backgroundColor: C.w, pointRadius: 2, tension: .2 } ] } });
  const pp = D.por_persona;
  new Chart(document.getElementById('g2'), { type: 'bar', options: { ...ou, indexAxis: 'y', interaction: { mode: 'index', axis: 'y', intersect: false }, scales: { x: { title: { display: true, text: D.moneda } } } },
    data: { labels: pp.map(x => x.nombre), datasets: [
      { label: 'Previsto (total)', data: pp.map(x => x.costo_previsto), backgroundColor: C.g },
      { label: 'Real a la fecha', data: pp.map(x => x.costo_real), backgroundColor: pp.map(x => x.costo_real > x.costo_previsto * 1.05 ? C.w : C.a) } ] } });
}

// Tabla con filtro, búsqueda y orden
const filas = CLI ? D.actividades : D.tareas;
const COLS = CLI ? [['etapa', T.cols[0]], ['nombre', T.cols[1]], ['inicio', T.cols[2], 'f'], ['fin', T.cols[3], 'f'], ['avance', T.cols[4], 'p']]
  : [['etapa', 'Etapa'], ['nombre', 'Tarea'], ['persona', 'Responsable'], ['inicio', 'Inicio', 'f'], ['fin', 'Fin', 'f'],
     ['horas_prev', 'Horas prev.', 'n'], ['horas_real', 'Horas reales', 'n'], ['costo_prev', 'Costo prev.', 'u'], ['costo_real', 'Costo real', 'u'], ['avance', 'Avance', 'p']];
const sel = document.getElementById('f-etapa');
sel.innerHTML = `<option value="">${T.todas}</option>` + [...new Set(filas.map(f => f.etapa))].map(e => `<option>${esc(e)}</option>`).join('');
document.getElementById('f-texto').placeholder = T.buscar;
let orden = null, asc = true;
function pintarTabla() {
  const e = sel.value, q = document.getElementById('f-texto').value.toLowerCase();
  let fs = filas.filter(f => (!e || f.etapa === e) && (!q || (f.nombre + ' ' + (f.persona || '')).toLowerCase().includes(q)));
  if (orden) fs = [...fs].sort((a, b) => (a[orden] > b[orden] ? 1 : a[orden] < b[orden] ? -1 : 0) * (asc ? 1 : -1));
  const v = (f, [k, , t]) => t === 'f' ? fec(f[k]) : t === 'p' ? pct(f[k]) : t === 'n' ? num(f[k], 1) : t === 'u' ? num(f[k]) : esc(f[k]);
  const num_ = t => ['p', 'n', 'u'].includes(t);
  document.getElementById('tabla').innerHTML = `<thead><tr>${COLS.map(c => `<th class="${num_(c[2]) ? 'num' : ''}" data-k="${c[0]}">${c[1]}${orden === c[0] ? (asc ? ' ▲' : ' ▼') : ''}</th>`).join('')}</tr></thead>
    <tbody>${fs.map(f => `<tr>${COLS.map(c => `<td class="${num_(c[2]) ? 'num' : ''}${c[0] === 'costo_real' && f.costo_real > f.costo_prev * 1.05 ? ' warn' : ''}">${v(f, c)}</td>`).join('')}</tr>`).join('')}</tbody>`;
  document.querySelectorAll('#tabla th').forEach(th => th.onclick = () => { const k = th.dataset.k; asc = orden === k ? !asc : true; orden = k; pintarTabla(); });
}
sel.onchange = pintarTabla; document.getElementById('f-texto').oninput = pintarTabla;
pintarTabla();
</script>
</body>
</html>
"""
