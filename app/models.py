# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
"""Modelo de datos (ver sección "Modelo de datos" del documento de diseño).

Convenciones:
- Todo importe se guarda en la moneda base configurada (columnas *_base),
  junto con el importe y la moneda originales y la cotización usada.
- Un presupuesto aprobado congela tarifas y cotización en sus filas.
"""
from datetime import date, datetime
from enum import Enum

from sqlalchemy import (Boolean, Date, DateTime, Enum as SAEnum, Float,
                        ForeignKey, Integer, Numeric, String, Text,
                        UniqueConstraint, func)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

Dinero = Numeric(14, 2)
Tasa = Numeric(20, 10)


class TipoPersona(str, Enum):
    empleado = "empleado"
    autonomo = "autonomo"


class Periodicidad(str, Enum):
    mensual = "mensual"
    anual = "anual"


class EstadoPresupuesto(str, Enum):
    borrador = "borrador"
    enviado = "enviado"
    aprobado = "aprobado"
    rechazado = "rechazado"


class EstadoProyecto(str, Enum):
    en_presupuesto = "en_presupuesto"
    en_curso = "en_curso"
    pausado = "pausado"
    terminado = "terminado"
    cancelado = "cancelado"


class Timestamps:
    creado: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    actualizado: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class Configuracion(Base):
    """Fila única (id=1) con los parámetros globales."""
    __tablename__ = "configuracion"
    id: Mapped[int] = mapped_column(primary_key=True)
    moneda_base: Mapped[str] = mapped_column(String(3), default="ARS")
    horas_anuales: Mapped[float] = mapped_column(Float, default=1760)
    utilizacion: Mapped[float] = mapped_column(Float, default=0.70)
    margen_defecto: Mapped[float] = mapped_column(Float, default=0.35)
    margen_alerta: Mapped[float] = mapped_column(Float, default=0.25)
    impuesto_defecto: Mapped[float] = mapped_column(Float, default=0.0)
    ss_empresa_defecto: Mapped[float] = mapped_column(Float, default=0.284)
    # Horas que se estima facturan los autónomos en el año (las de empleados se calculan)
    horas_autonomos_anuales: Mapped[float] = mapped_column(Float, default=1500)
    zona_horaria: Mapped[str] = mapped_column(String(64), default="America/Argentina/Buenos_Aires")
    # Datos de la empresa para los documentos que se envían al cliente
    empresa_nombre: Mapped[str | None] = mapped_column(String(160))
    empresa_direccion: Mapped[str | None] = mapped_column(String(255))  # domicilio (calle y número)
    empresa_localidad: Mapped[str | None] = mapped_column(String(120))
    empresa_provincia: Mapped[str | None] = mapped_column(String(120))
    empresa_cp: Mapped[str | None] = mapped_column(String(20))
    empresa_pais: Mapped[str | None] = mapped_column(String(80))
    empresa_telefonos: Mapped[str | None] = mapped_column(String(160))
    empresa_email: Mapped[str | None] = mapped_column(String(160))
    empresa_web: Mapped[str | None] = mapped_column(String(160))
    empresa_id_fiscal: Mapped[str | None] = mapped_column(String(60))
    validez_dias: Mapped[int] = mapped_column(Integer, default=30)
    # Aumento mensual previsto de sueldos y tarifas, para proyectar el costo del trabajo pendiente
    aumento_costos_mensual: Mapped[float] = mapped_column(Float, default=0.0)
    condiciones: Mapped[str | None] = mapped_column(Text)
    licencia: Mapped[str | None] = mapped_column(Text)
    # Consultar en GitHub si hay una versión nueva (solo al abrir, si hay internet)
    buscar_actualizaciones: Mapped[bool] = mapped_column(Boolean, default=True)


class Cotizacion(Base):
    """Cuántas unidades de la moneda base vale 1 unidad de `moneda` en `fecha`
    (p. ej. con base ARS: 1 USD = 1.540 ARS -> valor = 1540)."""
    __tablename__ = "cotizaciones"
    __table_args__ = (UniqueConstraint("fecha", "moneda"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    fecha: Mapped[date] = mapped_column(Date, index=True)
    moneda: Mapped[str] = mapped_column(String(3))
    valor: Mapped[float] = mapped_column(Tasa)


class Rol(Base):
    __tablename__ = "roles"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(80), unique=True)
    descripcion: Mapped[str | None] = mapped_column(Text)


class Persona(Timestamps, Base):
    __tablename__ = "personas"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    rol_id: Mapped[int] = mapped_column(ForeignKey("roles.id"))
    tipo: Mapped[TipoPersona] = mapped_column(SAEnum(TipoPersona))
    moneda: Mapped[str] = mapped_column(String(3), default="ARS")
    sueldo_bruto_anual: Mapped[float | None] = mapped_column(Dinero)   # empleados
    tarifa_hora: Mapped[float | None] = mapped_column(Dinero)          # autónomos
    ss_empresa: Mapped[float | None] = mapped_column(Float)            # empleados
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    vigente_desde: Mapped[date | None] = mapped_column(Date)
    vigente_hasta: Mapped[date | None] = mapped_column(Date)
    es_ejemplo: Mapped[bool] = mapped_column(Boolean, default=False)
    rol: Mapped[Rol] = relationship()


class CostoFijo(Timestamps, Base):
    __tablename__ = "costos_fijos"
    id: Mapped[int] = mapped_column(primary_key=True)
    concepto: Mapped[str] = mapped_column(String(120))
    moneda: Mapped[str] = mapped_column(String(3), default="ARS")
    importe: Mapped[float] = mapped_column(Dinero)
    periodicidad: Mapped[Periodicidad] = mapped_column(SAEnum(Periodicidad))
    vigente_desde: Mapped[date | None] = mapped_column(Date)
    vigente_hasta: Mapped[date | None] = mapped_column(Date)
    es_ejemplo: Mapped[bool] = mapped_column(Boolean, default=False)


class Servicio(Timestamps, Base):
    __tablename__ = "servicios"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    descripcion: Mapped[str | None] = mapped_column(Text)
    rol_sugerido_id: Mapped[int | None] = mapped_column(ForeignKey("roles.id"))
    horas_sugeridas: Mapped[float | None] = mapped_column(Float)
    pct_sobre_total: Mapped[float | None] = mapped_column(Float)  # p. ej. gestión = 10%
    etapa_sugerida: Mapped[str | None] = mapped_column(String(120))  # etapa del proyecto donde va
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    es_ejemplo: Mapped[bool] = mapped_column(Boolean, default=False)


class Cliente(Timestamps, Base):
    __tablename__ = "clientes"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(160))
    pais: Mapped[str | None] = mapped_column(String(80))
    contacto: Mapped[str | None] = mapped_column(String(160))
    moneda_mostrar: Mapped[str] = mapped_column(String(3), default="ARS")
    es_ejemplo: Mapped[bool] = mapped_column(Boolean, default=False)


class Proyecto(Timestamps, Base):
    __tablename__ = "proyectos"
    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id"))
    nombre: Mapped[str] = mapped_column(String(160))
    alcance: Mapped[str | None] = mapped_column(Text)
    fecha_inicio: Mapped[date | None] = mapped_column(Date)
    fecha_fin: Mapped[date | None] = mapped_column(Date)
    estado: Mapped[EstadoProyecto] = mapped_column(SAEnum(EstadoProyecto), default=EstadoProyecto.en_presupuesto)
    margen: Mapped[float] = mapped_column(Float, default=0.35)
    impuesto: Mapped[float] = mapped_column(Float, default=0.0)
    # Precio acordado con el cliente (moneda base). Si hay presupuesto aprobado, sale de ahí.
    precio_base: Mapped[float | None] = mapped_column(Dinero)
    # Contrato en otra moneda (p. ej. USD): el precio vale en esa moneda y se reexpresa a la base al día
    moneda_contrato: Mapped[str | None] = mapped_column(String(3))
    precio_contrato: Mapped[float | None] = mapped_column(Dinero)
    # Cláusula de ajuste por inflación del precio en moneda base: "ipc" o None
    ajuste_indice: Mapped[str | None] = mapped_column(String(10))
    ajuste_cada_meses: Mapped[int | None] = mapped_column(Integer)   # 1 mensual, 3 trimestral, 6 semestral
    ajuste_mes_base: Mapped[date | None] = mapped_column(Date)       # primer día del mes base
    es_ejemplo: Mapped[bool] = mapped_column(Boolean, default=False)
    cliente: Mapped[Cliente] = relationship()
    etapas: Mapped[list["Etapa"]] = relationship(back_populates="proyecto", cascade="all, delete-orphan",
                                                 order_by="Etapa.orden")
    presupuestos: Mapped[list["Presupuesto"]] = relationship(back_populates="proyecto", cascade="all, delete-orphan")
    tareas: Mapped[list["Tarea"]] = relationship(back_populates="proyecto", cascade="all, delete-orphan")


class Presupuesto(Timestamps, Base):
    __tablename__ = "presupuestos"
    __table_args__ = (UniqueConstraint("proyecto_id", "version"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    proyecto_id: Mapped[int] = mapped_column(ForeignKey("proyectos.id"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    estado: Mapped[EstadoPresupuesto] = mapped_column(SAEnum(EstadoPresupuesto), default=EstadoPresupuesto.borrador)
    tasa_estructura_base: Mapped[float | None] = mapped_column(Dinero)
    margen: Mapped[float] = mapped_column(Float)
    impuesto: Mapped[float] = mapped_column(Float, default=0.0)
    costo_base: Mapped[float | None] = mapped_column(Dinero)
    precio_base: Mapped[float | None] = mapped_column(Dinero)
    moneda_contrato: Mapped[str | None] = mapped_column(String(3))  # None = moneda base
    fecha_envio: Mapped[date | None] = mapped_column(Date)
    fecha_aprobacion: Mapped[date | None] = mapped_column(Date)
    notas: Mapped[str | None] = mapped_column(Text)
    proyecto: Mapped[Proyecto] = relationship(back_populates="presupuestos")
    items: Mapped[list["PresupuestoItem"]] = relationship(back_populates="presupuesto", cascade="all, delete-orphan",
                                                          order_by="PresupuestoItem.orden")
    costos_externos: Mapped[list["CostoExterno"]] = relationship(back_populates="presupuesto", cascade="all, delete-orphan")


class PresupuestoItem(Base):
    __tablename__ = "presupuesto_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    presupuesto_id: Mapped[int] = mapped_column(ForeignKey("presupuestos.id"))
    servicio_id: Mapped[int | None] = mapped_column(ForeignKey("servicios.id"))
    tarea: Mapped[str] = mapped_column(String(160))
    etapa: Mapped[str | None] = mapped_column(String(120))        # nombre de la etapa del proyecto
    pct_sobre_total: Mapped[float | None] = mapped_column(Float)  # horas = % de las demás horas
    rol_id: Mapped[int | None] = mapped_column(ForeignKey("roles.id"))
    persona_id: Mapped[int | None] = mapped_column(ForeignKey("personas.id"))
    horas: Mapped[float] = mapped_column(Float, default=0)
    costo_hora_base: Mapped[float | None] = mapped_column(Dinero)  # manual, o congelado al aprobar
    fecha_inicio: Mapped[date | None] = mapped_column(Date)
    fecha_fin: Mapped[date | None] = mapped_column(Date)
    orden: Mapped[int] = mapped_column(Integer, default=0)
    presupuesto: Mapped[Presupuesto] = relationship(back_populates="items")
    servicio: Mapped["Servicio | None"] = relationship()
    rol: Mapped["Rol | None"] = relationship()
    persona: Mapped["Persona | None"] = relationship()


class CostoExterno(Base):
    __tablename__ = "costos_externos"
    id: Mapped[int] = mapped_column(primary_key=True)
    presupuesto_id: Mapped[int | None] = mapped_column(ForeignKey("presupuestos.id"))
    proyecto_id: Mapped[int | None] = mapped_column(ForeignKey("proyectos.id"))
    concepto: Mapped[str] = mapped_column(String(160))
    es_real: Mapped[bool] = mapped_column(Boolean, default=False)  # False = previsto
    moneda: Mapped[str] = mapped_column(String(3), default="ARS")
    importe: Mapped[float] = mapped_column(Dinero)
    cotizacion: Mapped[float] = mapped_column(Tasa, default=1)
    importe_base: Mapped[float] = mapped_column(Dinero)
    fecha: Mapped[date | None] = mapped_column(Date)
    presupuesto: Mapped[Presupuesto | None] = relationship(back_populates="costos_externos")


class PlantillaEtapa(Base):
    """Etapas sugeridas al crear un proyecto (editables en cada proyecto)."""
    __tablename__ = "plantilla_etapas"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    orden: Mapped[int] = mapped_column(Integer, default=0)
    peso: Mapped[float | None] = mapped_column(Float)          # 0..1
    hito: Mapped[str | None] = mapped_column(String(200))
    pct_duracion: Mapped[float | None] = mapped_column(Float)  # parte del plazo total, para fechas sugeridas


class Etapa(Timestamps, Base):
    __tablename__ = "etapas"
    id: Mapped[int] = mapped_column(primary_key=True)
    proyecto_id: Mapped[int] = mapped_column(ForeignKey("proyectos.id"))
    nombre: Mapped[str] = mapped_column(String(120))
    orden: Mapped[int] = mapped_column(Integer, default=0)
    peso: Mapped[float | None] = mapped_column(Float)  # 0..1; None = proporcional al costo previsto
    inicio_previsto: Mapped[date | None] = mapped_column(Date)
    fin_previsto: Mapped[date | None] = mapped_column(Date)
    inicio_real: Mapped[date | None] = mapped_column(Date)
    fin_real: Mapped[date | None] = mapped_column(Date)
    hito: Mapped[str | None] = mapped_column(String(200))
    hito_cumplido: Mapped[date | None] = mapped_column(Date)
    aprobada_cliente: Mapped[bool] = mapped_column(Boolean, default=False)
    fecha_aprobacion: Mapped[date | None] = mapped_column(Date)
    notas: Mapped[str | None] = mapped_column(Text)
    proyecto: Mapped[Proyecto] = relationship(back_populates="etapas")
    tareas: Mapped[list["Tarea"]] = relationship(back_populates="etapa")


class Tarea(Base):
    __tablename__ = "tareas"
    id: Mapped[int] = mapped_column(primary_key=True)
    proyecto_id: Mapped[int] = mapped_column(ForeignKey("proyectos.id"))
    etapa_id: Mapped[int | None] = mapped_column(ForeignKey("etapas.id", ondelete="SET NULL"))
    item_id: Mapped[int | None] = mapped_column(ForeignKey("presupuesto_items.id"))
    nombre: Mapped[str] = mapped_column(String(160))
    persona_id: Mapped[int | None] = mapped_column(ForeignKey("personas.id"))  # responsable
    fecha_inicio: Mapped[date] = mapped_column(Date)
    fecha_fin: Mapped[date] = mapped_column(Date)
    inicio_real: Mapped[date | None] = mapped_column(Date)
    fin_real: Mapped[date | None] = mapped_column(Date)
    horas_previstas: Mapped[float] = mapped_column(Float)
    costo_hora_base: Mapped[float | None] = mapped_column(Dinero)  # congelado al crear la tarea
    costo_previsto_base: Mapped[float] = mapped_column(Dinero)
    avance: Mapped[float | None] = mapped_column(Float)  # 0..1; None = usar sugerido
    depende_de_id: Mapped[int | None] = mapped_column(ForeignKey("tareas.id"))
    orden: Mapped[int] = mapped_column(Integer, default=0)
    proyecto: Mapped[Proyecto] = relationship(back_populates="tareas")
    etapa: Mapped[Etapa | None] = relationship(back_populates="tareas")
    persona: Mapped["Persona | None"] = relationship()
    horas: Mapped[list["HoraReal"]] = relationship(back_populates="tarea", cascade="all, delete-orphan")
    avances: Mapped[list["AvanceRegistro"]] = relationship(cascade="all, delete-orphan",
                                                          order_by="AvanceRegistro.fecha")


class AvanceRegistro(Base):
    """Historial del % de avance de cada tarea (para la curva de valor ganado)."""
    __tablename__ = "avance_registros"
    id: Mapped[int] = mapped_column(primary_key=True)
    tarea_id: Mapped[int] = mapped_column(ForeignKey("tareas.id", ondelete="CASCADE"), index=True)
    fecha: Mapped[date] = mapped_column(Date)
    avance: Mapped[float] = mapped_column(Float)


class HoraReal(Timestamps, Base):
    __tablename__ = "horas_reales"
    id: Mapped[int] = mapped_column(primary_key=True)
    tarea_id: Mapped[int] = mapped_column(ForeignKey("tareas.id"))
    persona_id: Mapped[int] = mapped_column(ForeignKey("personas.id"))
    fecha: Mapped[date] = mapped_column(Date, index=True)
    horas: Mapped[float] = mapped_column(Float)
    costo_hora_base: Mapped[float] = mapped_column(Dinero)
    nota: Mapped[str | None] = mapped_column(Text)
    tarea: Mapped[Tarea] = relationship(back_populates="horas")


class Factura(Timestamps, Base):
    """Registro interno de una factura emitida (el comprobante fiscal se emite por fuera)."""
    __tablename__ = "facturas"
    id: Mapped[int] = mapped_column(primary_key=True)
    proyecto_id: Mapped[int] = mapped_column(ForeignKey("proyectos.id"), index=True)
    etapa_id: Mapped[int | None] = mapped_column(ForeignKey("etapas.id", ondelete="SET NULL"))
    numero: Mapped[str | None] = mapped_column(String(40))
    concepto: Mapped[str | None] = mapped_column(String(200))
    fecha: Mapped[date] = mapped_column(Date, index=True)
    vencimiento: Mapped[date | None] = mapped_column(Date)
    moneda: Mapped[str] = mapped_column(String(3))
    importe_neto: Mapped[float] = mapped_column(Dinero)       # en `moneda`, sin impuestos
    impuesto: Mapped[float] = mapped_column(Dinero, default=0)  # en `moneda`
    cotizacion: Mapped[float] = mapped_column(Tasa, default=1)  # moneda base por unidad, a la fecha
    neto_base: Mapped[float] = mapped_column(Dinero)
    anulada: Mapped[bool] = mapped_column(Boolean, default=False)
    notas: Mapped[str | None] = mapped_column(Text)
    es_ejemplo: Mapped[bool] = mapped_column(Boolean, default=False)
    proyecto: Mapped[Proyecto] = relationship()
    cobros: Mapped[list["Cobro"]] = relationship(back_populates="factura", cascade="all, delete-orphan",
                                                 order_by="Cobro.fecha")


class Cobro(Base):
    __tablename__ = "cobros"
    id: Mapped[int] = mapped_column(primary_key=True)
    factura_id: Mapped[int] = mapped_column(ForeignKey("facturas.id", ondelete="CASCADE"), index=True)
    fecha: Mapped[date] = mapped_column(Date, index=True)
    importe: Mapped[float] = mapped_column(Dinero)             # en la moneda de la factura (total con impuestos)
    cotizacion: Mapped[float] = mapped_column(Tasa, default=1)  # moneda base por unidad, a la fecha del cobro
    importe_base: Mapped[float] = mapped_column(Dinero)
    notas: Mapped[str | None] = mapped_column(Text)
    factura: Mapped[Factura] = relationship(back_populates="cobros")


class IndiceIPC(Base):
    """Variación mensual del IPC (INDEC), en %: 1,9 = 1,9 % en ese mes."""
    __tablename__ = "indices_ipc"
    id: Mapped[int] = mapped_column(primary_key=True)
    mes: Mapped[date] = mapped_column(Date, unique=True)  # primer día del mes
    variacion: Mapped[float] = mapped_column(Float)
    fuente: Mapped[str | None] = mapped_column(String(40))


class Historial(Base):
    __tablename__ = "historial"
    id: Mapped[int] = mapped_column(primary_key=True)
    tabla: Mapped[str] = mapped_column(String(64))
    registro_id: Mapped[int] = mapped_column(Integer)
    cambio: Mapped[str] = mapped_column(Text)  # JSON con antes/después
    fecha: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
