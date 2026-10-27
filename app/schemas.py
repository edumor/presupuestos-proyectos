# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
"""Esquemas Pydantic de entrada y salida de la API."""
from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .models import EstadoProyecto, Periodicidad, TipoPersona

# Monedas admitidas (la base es una de ellas; el resto se convierte con Cotizaciones)
MONEDAS = {"ARS": "Peso argentino", "USD": "Dólar estadounidense", "EUR": "Euro",
           "GBP": "Libra esterlina", "BRL": "Real brasileño", "CLP": "Peso chileno",
           "UYU": "Peso uruguayo", "MXN": "Peso mexicano"}
ERROR_MONEDA = "Moneda no admitida (use " + ", ".join(MONEDAS) + ")"


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Configuración ---
class ConfigIn(BaseModel):
    horas_anuales: float = Field(gt=0, le=3000)
    utilizacion: float = Field(gt=0, le=1)
    margen_defecto: float = Field(ge=0, lt=1)
    margen_alerta: float = Field(ge=0, lt=1)
    impuesto_defecto: float = Field(ge=0, le=1)
    ss_empresa_defecto: float = Field(ge=0, le=1)
    horas_autonomos_anuales: float = Field(ge=0)
    zona_horaria: str = "America/Argentina/Buenos_Aires"
    moneda_base: str | None = None  # solo se puede cambiar mientras no haya datos cargados
    empresa_nombre: str | None = Field(default=None, max_length=160)
    empresa_direccion: str | None = Field(default=None, max_length=255)
    empresa_localidad: str | None = Field(default=None, max_length=120)
    empresa_provincia: str | None = Field(default=None, max_length=120)
    empresa_cp: str | None = Field(default=None, max_length=20)
    empresa_pais: str | None = Field(default=None, max_length=80)
    empresa_telefonos: str | None = Field(default=None, max_length=160)
    empresa_email: str | None = Field(default=None, max_length=160)
    empresa_web: str | None = Field(default=None, max_length=160)
    empresa_id_fiscal: str | None = Field(default=None, max_length=60)
    validez_dias: int = Field(default=30, ge=1, le=365)
    condiciones: str | None = None
    aumento_costos_mensual: float = Field(default=0.0, ge=0, le=1)


class ConfigOut(ConfigIn, ORM):
    moneda_base: str
    tiene_logo: bool = False
    puede_cambiar_base: bool = False
    monedas: dict[str, str] = MONEDAS


# --- Cotizaciones ---
class CotizacionIn(BaseModel):
    fecha: date
    moneda: str
    valor: float = Field(gt=0, description="Unidades de la moneda base que vale 1 unidad de la moneda")

    @model_validator(mode="after")
    def _moneda(self):
        self.moneda = self.moneda.upper()
        if self.moneda not in MONEDAS:
            raise ValueError(ERROR_MONEDA)
        return self


class CotizacionOut(CotizacionIn, ORM):
    id: int
    inversa: float  # unidades de la moneda que vale 1 unidad de la base


# --- Roles ---
class RolIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=80)
    descripcion: str | None = None


class RolOut(RolIn, ORM):
    id: int


# --- Personas ---
class PersonaIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    rol_id: int
    tipo: TipoPersona
    moneda: str = "ARS"
    sueldo_bruto_anual: float | None = Field(default=None, gt=0)
    tarifa_hora: float | None = Field(default=None, gt=0)
    ss_empresa: float | None = Field(default=None, ge=0, le=1)
    activo: bool = True

    @model_validator(mode="after")
    def _coherencia(self):
        self.moneda = self.moneda.upper()
        if self.moneda not in MONEDAS:
            raise ValueError(ERROR_MONEDA)
        if self.tipo == TipoPersona.empleado and not self.sueldo_bruto_anual:
            raise ValueError("Un empleado necesita sueldo bruto anual")
        if self.tipo == TipoPersona.autonomo and not self.tarifa_hora:
            raise ValueError("Un autónomo necesita tarifa por hora")
        return self


class PersonaOut(PersonaIn, ORM):
    id: int
    es_ejemplo: bool
    rol_nombre: str | None = None


class CostoHoraOut(BaseModel):
    persona_id: int
    nombre: str
    tipo: TipoPersona
    moneda: str
    base_por_unidad: float
    costo_directo_base: float
    tasa_estructura_base: float
    costo_total_base: float
    detalle: str


# --- Costos fijos ---
class CostoFijoIn(BaseModel):
    concepto: str = Field(min_length=1, max_length=120)
    moneda: str = "ARS"
    importe: float = Field(gt=0)
    periodicidad: Periodicidad
    vigente_desde: date | None = None
    vigente_hasta: date | None = None

    @model_validator(mode="after")
    def _moneda(self):
        self.moneda = self.moneda.upper()
        if self.moneda not in MONEDAS:
            raise ValueError(ERROR_MONEDA)
        return self


class CostoFijoOut(CostoFijoIn, ORM):
    id: int
    es_ejemplo: bool
    anual_base: float | None = None


class TasaEstructuraOut(BaseModel):
    costos_fijos_anuales_base: float
    horas_empleados: float
    horas_autonomos: float
    horas_facturables_anuales: float
    tasa_estructura_base: float


# --- Clientes ---
class ClienteIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=160)
    pais: str | None = None
    contacto: str | None = None
    moneda_mostrar: str = "ARS"


class ClienteOut(ClienteIn, ORM):
    id: int
    es_ejemplo: bool


# --- Proyectos ---
class ProyectoIn(BaseModel):
    cliente_id: int
    nombre: str = Field(min_length=1, max_length=160)
    alcance: str | None = None
    fecha_inicio: date
    fecha_fin: date
    estado: EstadoProyecto = EstadoProyecto.en_curso
    margen: float = Field(default=0.35, ge=0, lt=1)
    impuesto: float = Field(default=0.0, ge=0, le=1)
    precio_base: float | None = Field(default=None, ge=0)
    moneda_contrato: str | None = None   # vacío = moneda base
    precio_contrato: float | None = Field(default=None, ge=0)
    ajuste_indice: Literal["ipc"] | None = None
    ajuste_cada_meses: int | None = Field(default=None, ge=1, le=12)
    ajuste_mes_base: date | None = None

    @model_validator(mode="after")
    def _fechas(self):
        if self.fecha_fin < self.fecha_inicio:
            raise ValueError("La fecha de fin no puede ser anterior a la de inicio")
        if self.moneda_contrato:
            self.moneda_contrato = self.moneda_contrato.upper()
            if self.moneda_contrato not in MONEDAS:
                raise ValueError(ERROR_MONEDA)
        if self.ajuste_indice:
            self.ajuste_cada_meses = self.ajuste_cada_meses or 3
            # por defecto, el mes anterior al inicio (último índice conocido al firmar)
            self.ajuste_mes_base = (self.ajuste_mes_base or
                                    (self.fecha_inicio.replace(day=1) - timedelta(days=1))).replace(day=1)
        return self


class ProyectoCrear(ProyectoIn):
    usar_plantilla: bool = True


class ProyectoOut(ProyectoIn, ORM):
    id: int
    es_ejemplo: bool
    cliente_nombre: str | None = None


# --- Etapas ---
class EtapaIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    orden: int = 0
    peso: float | None = Field(default=None, ge=0, le=1)
    inicio_previsto: date | None = None
    fin_previsto: date | None = None
    inicio_real: date | None = None
    fin_real: date | None = None
    hito: str | None = None
    hito_cumplido: date | None = None
    aprobada_cliente: bool = False
    fecha_aprobacion: date | None = None
    notas: str | None = None


class EtapaOut(EtapaIn, ORM):
    id: int
    proyecto_id: int


class PlantillaEtapaIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    orden: int = 0
    peso: float | None = Field(default=None, ge=0, le=1)
    pct_duracion: float | None = Field(default=None, ge=0, le=1)
    hito: str | None = None


class PlantillaEtapaOut(PlantillaEtapaIn, ORM):
    id: int


# --- Tareas ---
class TareaIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=160)
    etapa_id: int | None = None
    persona_id: int | None = None
    fecha_inicio: date
    fecha_fin: date
    inicio_real: date | None = None
    fin_real: date | None = None
    horas_previstas: float = Field(gt=0)
    costo_hora_base: float | None = Field(default=None, gt=0,
                                         description="Si se omite, se toma el costo/hora actual del responsable")
    avance: float | None = Field(default=None, ge=0, le=1)
    orden: int = 0

    @model_validator(mode="after")
    def _fechas(self):
        if self.fecha_fin < self.fecha_inicio:
            raise ValueError("La fecha de fin no puede ser anterior a la de inicio")
        return self


class TareaOut(ORM):
    id: int
    proyecto_id: int
    etapa_id: int | None
    persona_id: int | None
    persona_nombre: str | None = None
    nombre: str
    fecha_inicio: date
    fecha_fin: date
    inicio_real: date | None
    fin_real: date | None
    horas_previstas: float
    costo_hora_base: float | None
    costo_previsto_base: float
    avance: float | None
    avance_efectivo: float = 0
    horas_reales: float = 0
    costo_real_base: float = 0
    orden: int


# --- Horas ---
class HoraIn(BaseModel):
    tarea_id: int
    persona_id: int
    fecha: date
    horas: float = Field(gt=0, le=24)
    nota: str | None = None


class HoraOut(HoraIn, ORM):
    id: int
    costo_hora_base: float
    persona_nombre: str | None = None
    tarea_nombre: str | None = None
    proyecto_id: int | None = None
    proyecto_nombre: str | None = None


# --- Gastos externos ---
class GastoIn(BaseModel):
    concepto: str = Field(min_length=1, max_length=160)
    es_real: bool = False
    moneda: str = "ARS"
    importe: float = Field(gt=0)
    fecha: date | None = None

    @model_validator(mode="after")
    def _moneda(self):
        self.moneda = self.moneda.upper()
        if self.moneda not in MONEDAS:
            raise ValueError(ERROR_MONEDA)
        return self


class GastoOut(GastoIn, ORM):
    id: int
    proyecto_id: int | None
    cotizacion: float
    importe_base: float


# --- Servicios (catálogo) ---
class ServicioIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    descripcion: str | None = None
    rol_sugerido_id: int | None = None
    horas_sugeridas: float | None = Field(default=None, ge=0)
    pct_sobre_total: float | None = Field(default=None, ge=0, le=1)
    etapa_sugerida: str | None = Field(default=None, max_length=120)
    activo: bool = True


class ServicioOut(ServicioIn, ORM):
    id: int
    es_ejemplo: bool
    rol_nombre: str | None = None


# --- Presupuestos ---
class PresupuestoItemIn(BaseModel):
    tarea: str = Field(min_length=1, max_length=160)
    etapa: str | None = Field(default=None, max_length=120)
    servicio_id: int | None = None
    rol_id: int | None = None
    persona_id: int | None = None
    horas: float = Field(default=0, ge=0)
    pct_sobre_total: float | None = Field(default=None, gt=0, le=1)
    costo_hora_base: float | None = Field(default=None, gt=0, description="Manual; vacío = según persona o rol")
    fecha_inicio: date | None = None
    fecha_fin: date | None = None


class PresupuestoExternoIn(BaseModel):
    concepto: str = Field(min_length=1, max_length=160)
    moneda: str = "ARS"
    importe: float = Field(gt=0)

    @model_validator(mode="after")
    def _moneda(self):
        self.moneda = self.moneda.upper()
        if self.moneda not in MONEDAS:
            raise ValueError(ERROR_MONEDA)
        return self


class PresupuestoIn(BaseModel):
    margen: float = Field(ge=0, lt=1)
    impuesto: float = Field(default=0, ge=0, le=1)
    precio_base: float | None = Field(default=None, ge=0, description="Precio final manual; vacío = sugerido")
    moneda_contrato: str | None = None
    notas: str | None = None
    items: list[PresupuestoItemIn] = []
    externos: list[PresupuestoExternoIn] = []


class PresupuestoNuevo(BaseModel):
    copiar_de: int | None = None


# --- Índice de inflación ---
class IPCIn(BaseModel):
    mes: date
    variacion: float = Field(ge=-50, le=100, description="Variación mensual en %, p. ej. 1.9")


class IPCOut(ORM):
    id: int
    mes: date
    variacion: float
    fuente: str | None = None


# --- Facturación (registro interno) ---
class FacturaIn(BaseModel):
    etapa_id: int | None = None
    numero: str | None = Field(default=None, max_length=40)
    concepto: str | None = Field(default=None, max_length=200)
    fecha: date
    vencimiento: date | None = None
    moneda: str | None = None          # None = moneda del contrato del proyecto
    importe_neto: float = Field(gt=0)
    impuesto: float = Field(default=0, ge=0)
    cotizacion: float | None = Field(default=None, gt=0)  # None = la vigente a la fecha
    anulada: bool = False
    notas: str | None = None

    @model_validator(mode="after")
    def _validar(self):
        if self.moneda:
            self.moneda = self.moneda.upper()
            if self.moneda not in MONEDAS:
                raise ValueError(ERROR_MONEDA)
        if self.vencimiento and self.vencimiento < self.fecha:
            raise ValueError("El vencimiento no puede ser anterior a la fecha de la factura")
        return self


class CobroIn(BaseModel):
    fecha: date
    importe: float = Field(gt=0)        # en la moneda de la factura
    cotizacion: float | None = Field(default=None, gt=0)
    notas: str | None = None


class CobroOut(ORM):
    id: int
    factura_id: int
    fecha: date
    importe: float
    cotizacion: float
    importe_base: float
    notas: str | None
    diferencia_cambio: float = 0


class FacturaOut(ORM):
    id: int
    proyecto_id: int
    etapa_id: int | None
    etapa_nombre: str | None = None
    proyecto_nombre: str | None = None
    cliente_nombre: str | None = None
    numero: str | None
    concepto: str | None
    fecha: date
    vencimiento: date | None
    moneda: str
    importe_neto: float
    impuesto: float
    total: float = 0
    cotizacion: float
    neto_base: float
    anulada: bool
    notas: str | None
    cobrado: float = 0
    saldo: float = 0
    saldo_base: float = 0
    diferencia_cambio: float = 0
    estado: str = "pendiente"
    dias_vencida: int | None = None
    cobros: list[CobroOut] = []
