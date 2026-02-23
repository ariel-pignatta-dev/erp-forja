from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime, Boolean,
    ForeignKey, Text, Enum as SAEnum, func
)
from sqlalchemy.orm import declarative_base, relationship
import enum

Base = declarative_base()

# ── Enums ──────────────────────────────────────────────────────────────────
class EstadoOrden(str, enum.Enum):
    pendiente  = "Pendiente"
    activa     = "Activa"
    pausada    = "Pausada"
    completada = "Completada"

class RolUsuario(str, enum.Enum):
    admin    = "admin"
    operario = "operario"

# ── Usuarios ───────────────────────────────────────────────────────────────
class Usuario(Base):
    __tablename__ = "usuarios"
    id            = Column(Integer, primary_key=True)
    nombre        = Column(String(100), nullable=False)
    email         = Column(String(150), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    rol           = Column(SAEnum(RolUsuario), default=RolUsuario.operario, nullable=False)
    activo        = Column(Boolean, default=True)
    creado_en     = Column(DateTime, server_default=func.now())

    cargas        = relationship("CargaAvance", back_populates="usuario")
    audit_logs    = relationship("AuditLog", back_populates="usuario")

# ── Células ────────────────────────────────────────────────────────────────
class Celula(Base):
    __tablename__ = "celulas"
    id            = Column(Integer, primary_key=True)
    codigo        = Column(String(20), unique=True, nullable=False)  # C69, C-F01
    nombre        = Column(String(100))
    turnos_lv     = Column(Integer, default=1)
    hs_turno_lv   = Column(Float,   default=8.0)
    turnos_sab    = Column(Integer, default=3)
    hs_turno_sab  = Column(Float,   default=4.0)
    efic_lv       = Column(Float,   default=85.0)   # porcentaje
    efic_sab      = Column(Float,   default=85.0)
    hs_extra_lv   = Column(Float,   default=0.0)
    hs_extra_sab  = Column(Float,   default=0.0)
    hs_extra_dom  = Column(Float,   default=0.0)
    hs_extra_fer  = Column(Float,   default=0.0)
    activa        = Column(Boolean, default=True)
    color_hex     = Column(String(7), default="#94A3B8")  # para GANTT
    creada_en     = Column(DateTime, server_default=func.now())

    ordenes       = relationship("Orden", back_populates="celula")

    @property
    def hs_dia_lv(self):
        return self.turnos_lv * self.hs_turno_lv * (self.efic_lv / 100) + self.hs_extra_lv

    @property
    def hs_dia_sab(self):
        return self.turnos_sab * self.hs_turno_sab * (self.efic_sab / 100) + self.hs_extra_sab

# ── SKUs ───────────────────────────────────────────────────────────────────
class SKU(Base):
    __tablename__ = "skus"
    id            = Column(Integer, primary_key=True)
    codigo        = Column(String(50), unique=True, nullable=False)
    descripcion   = Column(String(200))
    material      = Column(String(100))
    proceso       = Column(String(100))
    t_unit_min    = Column(Float, nullable=False, default=0.0)  # min/pieza
    activo        = Column(Boolean, default=True)
    creado_en     = Column(DateTime, server_default=func.now())

    ordenes       = relationship("Orden", back_populates="sku")

# ── Feriados ───────────────────────────────────────────────────────────────
class Feriado(Base):
    __tablename__ = "feriados"
    id            = Column(Integer, primary_key=True)
    fecha         = Column(Date, unique=True, nullable=False)
    descripcion   = Column(String(100))

# ── Órdenes de Trabajo ─────────────────────────────────────────────────────
class Orden(Base):
    __tablename__ = "ordenes"
    id            = Column(Integer, primary_key=True)
    nro_ot        = Column(String(20), unique=True, nullable=False)  # OT-001
    celula_id     = Column(Integer, ForeignKey("celulas.id"), nullable=False)
    sku_id        = Column(Integer, ForeignKey("skus.id"), nullable=False)
    cantidad      = Column(Integer, nullable=False)
    fecha_inicio  = Column(Date, nullable=True)
    estado        = Column(SAEnum(EstadoOrden), default=EstadoOrden.pendiente)
    ot_precede_id = Column(Integer, ForeignKey("ordenes.id"), nullable=True)
    notas         = Column(Text)
    archivada     = Column(Boolean, default=False)
    archivada_en  = Column(DateTime, nullable=True)
    creada_en     = Column(DateTime, server_default=func.now())
    actualizada_en= Column(DateTime, server_default=func.now(), onupdate=func.now())

    celula        = relationship("Celula", back_populates="ordenes")
    sku           = relationship("SKU", back_populates="ordenes")
    ot_precede    = relationship("Orden", remote_side=[id], foreign_keys=[ot_precede_id])
    cargas        = relationship("CargaAvance", back_populates="orden",
                                 order_by="CargaAvance.fecha")

    @property
    def piezas_producidas(self):
        if not self.cargas: return 0
        return max((c.acumulado for c in self.cargas), default=0)

    @property
    def piezas_restantes(self):
        return max(0, self.cantidad - self.piezas_producidas)

    @property
    def hs_estimadas(self):
        if not self.sku or self.sku.t_unit_min == 0: return 0
        return round(self.cantidad * self.sku.t_unit_min / 60, 2)

    @property
    def hs_restantes(self):
        if not self.sku or self.sku.t_unit_min == 0: return self.hs_estimadas
        return round(self.piezas_restantes * self.sku.t_unit_min / 60, 2)

# ── Carga de Avance ────────────────────────────────────────────────────────
class CargaAvance(Base):
    __tablename__ = "cargas_avance"
    id            = Column(Integer, primary_key=True)
    orden_id      = Column(Integer, ForeignKey("ordenes.id"), nullable=False)
    usuario_id    = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    fecha         = Column(Date, nullable=False)
    turno_1       = Column(Integer, default=0)
    turno_2       = Column(Integer, default=0)
    turno_3       = Column(Integer, default=0)
    scrap         = Column(Integer, default=0)
    notas         = Column(Text)
    cargada_en    = Column(DateTime, server_default=func.now())

    orden         = relationship("Orden", back_populates="cargas")
    usuario       = relationship("Usuario", back_populates="cargas")

    @property
    def total_buenas(self):
        return self.turno_1 + self.turno_2 + self.turno_3 - self.scrap

    @property
    def acumulado(self):
        # Calculado en query, no aquí — este es el campo que se persiste
        return getattr(self, '_acumulado', self.total_buenas)

# ── Audit Log ─────────────────────────────────────────────────────────────
class AuditLog(Base):
    __tablename__ = "audit_logs"
    id            = Column(Integer, primary_key=True)
    usuario_id    = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    tabla         = Column(String(50))
    registro_id   = Column(Integer)
    accion        = Column(String(20))   # CREATE, UPDATE, DELETE, ARCHIVE
    detalle       = Column(Text)         # JSON con cambios
    ip            = Column(String(45))
    timestamp     = Column(DateTime, server_default=func.now())

    usuario       = relationship("Usuario", back_populates="audit_logs")
