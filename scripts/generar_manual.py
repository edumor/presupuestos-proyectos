# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
"""Genera la pantalla de Ayuda (frontend/ayuda.html) y el PDF del manual desde docs/manual.md.

Uso (herramienta de desarrollo, no la necesita quien usa el programa):
    pip install markdown playwright && playwright install chromium
    python scripts/generar_manual.py
"""
import re
import sys
from datetime import date
from pathlib import Path

import markdown

RAIZ = Path(__file__).resolve().parent.parent
MD = RAIZ / "docs" / "manual.md"
AYUDA = RAIZ / "frontend" / "ayuda.html"
PDF = RAIZ / "docs" / "Manual_Presupuestos.pdf"
sys.path.insert(0, str(RAIZ))
from app import CREDITO, __version__  # noqa: E402


def convertir(texto: str) -> tuple[str, str, list[tuple[int, str, str]]]:
    titulo = texto.splitlines()[0].lstrip("# ").strip()
    cuerpo = "\n".join(texto.splitlines()[1:])
    md = markdown.Markdown(extensions=["tables", "toc", "sane_lists"],
                           extension_configs={"toc": {"toc_depth": "2-3"}})
    html = md.convert(cuerpo)
    # imágenes como figuras con epígrafe
    html = re.sub(r'<p><img alt="([^"]*)" src="([^"]+)" ?/?></p>',
                  r'<figure><img alt="\1" src="\2"><figcaption>\1</figcaption></figure>', html)
    secciones = [(int(t["level"]), t["id"], t["name"]) for t in _aplanar(md.toc_tokens)]
    return titulo, html, secciones


def _aplanar(tokens):
    for t in tokens:
        yield t
        yield from _aplanar(t.get("children", []))


CSS_MANUAL = """
.manual { display: grid; grid-template-columns: 240px 1fr; gap: 32px; align-items: start; }
.manual nav.indice { position: sticky; top: 16px; font-size: 13px; max-height: calc(100vh - 32px); overflow: auto; }
.manual nav.indice a { display: block; color: var(--muted); text-decoration: none; padding: 4px 8px; border-radius: 4px; }
.manual nav.indice a:hover { background: var(--accent-soft); color: var(--accent); }
.manual nav.indice a.n3 { padding-left: 20px; font-size: 12.5px; }
.contenido { background: #fff; border: 1px solid var(--line); border-radius: 8px; padding: 32px 40px; line-height: 1.6; font-size: 14.5px; max-width: 860px; }
.contenido h2 { font-size: 20px; margin: 36px 0 12px; padding-top: 12px; border-top: 1px solid var(--line); }
.contenido h2:first-of-type { border-top: none; margin-top: 8px; }
.contenido h3 { font-size: 16px; margin: 24px 0 8px; }
.contenido table { margin: 12px 0 18px; font-size: 13.5px; }
.contenido td, .contenido th { border-bottom: 1px solid var(--line); }
.contenido figure { margin: 16px 0 24px; }
.contenido figure img { max-width: 100%; border: 1px solid var(--line); border-radius: 6px; box-shadow: 0 1px 3px rgba(0,0,0,.06); }
.contenido figcaption { font-size: 12px; color: var(--muted); margin-top: 6px; }
.contenido code { background: #f2f4f7; padding: 1px 5px; border-radius: 4px; font-size: 12.5px; }
.contenido li { margin: 4px 0; }
@media (max-width: 900px) { .manual { grid-template-columns: 1fr; } .manual nav.indice { position: static; } .contenido { padding: 20px; } }
"""

CSS_PDF = """
@page { size: A4; margin: 18mm 16mm 18mm 16mm; }
body { font-family: "Segoe UI", system-ui, sans-serif; color: #1c2230; font-size: 10.5pt; line-height: 1.5; margin: 0; }
.portada { height: 255mm; display: flex; flex-direction: column; justify-content: center; page-break-after: always; }
.portada h1 { font-size: 28pt; margin: 0 0 8pt; color: #1c2230; }
.portada .sub { font-size: 13pt; color: #5d6677; }
.portada .barra { width: 60mm; height: 4pt; background: #2456c8; margin: 16pt 0; }
.indice { page-break-after: always; }
.indice h2 { font-size: 16pt; }
.indice a { color: #1c2230; text-decoration: none; display: block; padding: 2pt 0; }
.indice a.n3 { padding-left: 14pt; color: #5d6677; font-size: 9.5pt; }
h2 { font-size: 16pt; margin: 18pt 0 6pt; page-break-before: always; color: #1c2230; }
h3 { font-size: 12pt; margin: 14pt 0 4pt; page-break-after: avoid; }
table { width: 100%; border-collapse: collapse; margin: 8pt 0 12pt; font-size: 9.5pt; page-break-inside: avoid; }
th { background: #1c2230; color: #fff; text-align: left; padding: 4pt 6pt; font-weight: 600; }
td { border-bottom: 1px solid #e3e6eb; padding: 4pt 6pt; vertical-align: top; }
figure { margin: 8pt 0 12pt; page-break-inside: avoid; }
figure img { max-width: 100%; max-height: 120mm; border: 1px solid #e3e6eb; border-radius: 4pt; }
figcaption { font-size: 8.5pt; color: #5d6677; margin-top: 3pt; }
code { background: #f2f4f7; padding: 0 3pt; border-radius: 3pt; font-size: 9pt; }
p, li { orphans: 3; widows: 3; }
"""


def indice_html(secciones):
    return "".join(f'<a class="n{n}" href="#{i}">{nombre}</a>' for n, i, nombre in secciones if n in (2, 3))


def ayuda(titulo, cuerpo, secciones) -> str:
    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Ayuda · Presupuestos</title>
  <link rel="stylesheet" href="assets/app.css">
  <style>{CSS_MANUAL}</style>
</head>
<body>
<main style="max-width:1180px">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:16px;flex-wrap:wrap">
    <div><h1>Ayuda</h1><p class="sub">{titulo} · versión {__version__}</p></div>
    <a href="manual.pdf" download><button>Descargar el manual en PDF</button></a>
  </div>
  <div class="manual">
    <nav class="indice">{indice_html(secciones)}</nav>
    <article class="contenido">{cuerpo}</article>
  </div>
</main>
<script src="assets/app.js"></script>
</body>
</html>
<!-- Generado por scripts/generar_manual.py desde docs/manual.md: no editar a mano. -->
"""


def html_pdf(titulo, cuerpo, secciones) -> str:
    corte = cuerpo.find("<h2")
    intro, cuerpo = (cuerpo[:corte], cuerpo[corte:]) if corte > 0 else ("", cuerpo)
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><style>{CSS_PDF}</style></head><body>
<section class="portada">
  <div class="sub">Manual de uso</div>
  <h1>Presupuestos y seguimiento de proyectos</h1>
  <div class="barra"></div>
  <div class="sub">Versión {__version__} · {date.today():%d/%m/%Y}</div>
  <div class="sub" style="margin-top:6pt;font-style:italic">{CREDITO}</div>
  <div style="margin-top:40pt;max-width:140mm;color:#39404f">{intro}</div>
</section>
<section class="indice"><h2 style="page-break-before:auto">Contenido</h2>{indice_html(secciones)}</section>
{cuerpo}
</body></html>"""


def main() -> None:
    titulo, cuerpo, secciones = convertir(MD.read_text(encoding="utf-8"))
    AYUDA.write_text(ayuda(titulo, cuerpo, secciones), encoding="utf-8")
    print("Escrito", AYUDA)

    from playwright.sync_api import sync_playwright
    tmp = RAIZ / "frontend" / "_manual_pdf.html"
    tmp.write_text(html_pdf(titulo, cuerpo, secciones), encoding="utf-8")
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page()
            pg.goto(tmp.as_uri())
            pg.wait_for_load_state("networkidle")
            pg.pdf(path=str(PDF), format="A4", print_background=True, display_header_footer=True,
                   header_template="<span></span>",
                   footer_template='<div style="font-size:8px;color:#8a93a3;width:100%;text-align:center;line-height:1.5">'
                                   'Presupuestos · Manual de uso · página <span class="pageNumber"></span> de '
                                   '<span class="totalPages"></span><br><i>' + CREDITO + '</i></div>',
                   margin={"top": "16mm", "bottom": "18mm", "left": "16mm", "right": "16mm"})
            b.close()
    finally:
        tmp.unlink(missing_ok=True)
    (RAIZ / "frontend" / "manual.pdf").write_bytes(PDF.read_bytes())
    print("Escrito", PDF)


if __name__ == "__main__":
    main()
