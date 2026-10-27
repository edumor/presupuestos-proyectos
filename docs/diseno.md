# Decisiones de diseño

- Moneda base configurable (ARS por defecto). Las demás monedas se convierten con cotizaciones
  cargadas a mano ("1 unidad = X moneda base"); cada hora, tarea y gasto guarda el valor que usó.
- Equipo mixto: empleados en relación de dependencia (sueldo anual con aguinaldo y contribuciones
  patronales) y autónomos con tarifa por hora.
- Catálogo de servicios; cotización por hora; alcance cerrado.
- Impuestos: campo % opcional, sin lógica fiscal (lo define el contador de cada empresa).
- Tasa de estructura única: costos fijos anuales ÷ horas facturables del año.
- Precio = costo ÷ (1 − margen).
- Seguimiento con valor ganado (PV, EV, AC, CPI, SPI, EAC) y avance ponderado por etapas.
- % de avance sugerido automático (horas reales / previstas), editable, con historial.
- Documentos para el cliente en español o inglés, sin costos internos; precio por etapa repartido
  según el costo previsto de cada etapa; opción de mostrar el equivalente en otra moneda (USD).
- Datos de la empresa y logo opcionales, configurables por cada instalación.
- Todo local: FastAPI + SQLite en la PC del usuario; instalador de Windows construido con
  `packaging/build.bat` (PyInstaller + Inno Setup), sin requerir Python instalado.
