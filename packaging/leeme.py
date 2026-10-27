# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
"""Escribe el LEEME de la carpeta para distribuir, con la versión del instalador (lo usa build.bat)."""
import sys

version, destino = sys.argv[1], sys.argv[2]
texto = f"""PRESUPUESTOS Y SEGUIMIENTO DE PROYECTOS - versión {version}
=======================================================

En esta carpeta hay:

  1. Presupuestos-Setup-{version}.exe   -> el instalador del programa
  2. Manual de uso - Presupuestos.pdf  -> el manual completo

INSTALAR (5 minutos)
--------------------
1. Doble clic en "Presupuestos-Setup-{version}.exe".
2. Si Windows muestra "Windows protegió su PC", hacé clic en
   "Más información" y después en "Ejecutar de todos modos".
   Es normal: el instalador no tiene firma digital comercial.
3. Siguiente -> Instalar -> Finalizar. No pide contraseña de administrador.
4. Queda el acceso directo "Presupuestos" en el escritorio.

Si ya tenías instalada una versión anterior, instalá esta encima:
se conservan todos tus datos.

USAR
----
- Doble clic en "Presupuestos": se abre una ventana negra y después
  el programa en el navegador.
- NO cierres la ventana negra mientras lo uses. Para salir, cerrala.
- La primera vez abre con DATOS DE EJEMPLO para practicar.
  Cuando quieras cargar los datos reales: Configuración -> Borrar datos de ejemplo.
- En Configuración cargá los datos de tu empresa (nombre, domicilio,
  teléfonos, email, web, CUIT) y, si tenés, el logo: salen en las
  propuestas, informes y dashboards que se envían al cliente.
- Los importes se calculan en pesos (ARS). Para mostrar también dólares
  u otra moneda, cargá la cotización en el menú Cotizaciones.

DÓNDE ESTÁ LA AYUDA
-------------------
- El PDF del manual (también en el menú Inicio -> Presupuestos -> Manual de uso).
- Dentro del programa, en el menú "Ayuda".
- Empezá por las secciones 2 (Instalación), 4 (Puesta en marcha),
  7 (Seguimiento) y 9 (Exportar documentos y dashboards).

TUS DATOS
---------
Se guardan solos en tu computadora (menú Inicio -> Presupuestos ->
Carpeta de datos y respaldos). Cada vez que abrís el programa se hace
un respaldo automático. Desinstalar o actualizar NO borra los datos.

Desarrollo e Implementación: Lic. Eduardo J. Moreno
"""
with open(destino, "w", encoding="utf-8-sig", newline="\r\n") as f:
    f.write(texto)
