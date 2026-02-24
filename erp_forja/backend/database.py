print("DATABASE_URL REAL:", os.getenv("DATABASE_URL"))
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
from sqlalchemy import String, Integer, Float, Date, DateTime, Boolean, ForeignKey, Text
from datetime import datetime, date
from typing import Optional
import enum
import os

# ─────────────────────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────────────────────

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL, echo=False)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False
)

class Base(DeclarativeBase):
    pass

# ─────────────────────────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────────────────────────

class EstadoOrden(str, enum.Enum):
    pendiente  = "Pendiente"
    activa     = "Activa"
    pausada    = "Pausada"
    completada = "Completada"

class RolUsuario(str, enum.Enum):
    admin    = "admin"
    operario = "operario"

# ─────────────────────────────────────────────────────────────
# MODELOS
# ─────────────────────────────────────────────────────────────

class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    password: Mapped[str] = mapped_column(String(200))
    rol: Mapped[RolUsuario] = mapped_column(default=RolUsuario.operario)
    activo: Mapped[bool] = mapped_column(default=True)
    creado_en: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    avances: Mapped[list["AvanceDiario"]] = relationship(back_populates="usuario")
    logs: Mapped[list["LogCambio"]] = relationship(back_populates="usuario")


class Celula(Base):
    __tablename__ = "celulas"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    nombre: Mapped[str] = mapped_column(String(100))
    turnos_lv: Mapped[int] = mapped_column(default=1)
    hs_turno_lv: Mapped[float] = mapped_column(default=8.0)
    turnos_sab: Mapped[int] = mapped_column(default=3)
    hs_turno_sab: Mapped[float] = mapped_column(default=4.0)
    efic_lv: Mapped[float] = mapped_column(default=85.0)
    efic_sab: Mapped[float] = mapped_column(default=85.0)
    hs_extra_lv: Mapped[float] = mapped_column(default=0.0)
    hs_extra_sab: Mapped[float] = mapped_column(default=0.0)
    hs_extra_dom: Mapped[float] = mapped_column(default=0.0)
    hs_extra_fer: Mapped[float] = mapped_column(default=0.0)
    color: Mapped[str] = mapped_column(String(10), default="#3B82F6")
    activa: Mapped[bool] = mapped_column(default=True)

    ordenes: Mapped[list["Orden"]] = relationship(back_populates="celula")


class SKU(Base):
    __tablename__ = "skus"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    descripcion: Mapped[str] = mapped_column(String(200))
    material: Mapped[Optional[str]] = mapped_column(String(100))
    proceso: Mapped[Optional[str]] = mapped_column(String(100))
    t_unit: Mapped[float] = mapped_column(default=0.0)
    activo: Mapped[bool] = mapped_column(default=True)
    observaciones: Mapped[Optional[str]] = mapped_column(Text)

    ordenes: Mapped[list["Orden"]] = relationship(back_populates="sku")


class Orden(Base):
    __tablename__ = "ordenes"

    id: Mapped[int] = mapped_column(primary_key=True)
    numero: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    celula_id: Mapped[int] = mapped_column(ForeignKey("celulas.id"))
    sku_id: Mapped[int] = mapped_column(ForeignKey("skus.id"))
    cantidad: Mapped[int] = mapped_column(default=0)
    estado: Mapped[EstadoOrden] = mapped_column(default=EstadoOrden.pendiente)
    fecha_inicio: Mapped[Optional[date]] = mapped_column(Date)
    notas: Mapped[Optional[str]] = mapped_column(Text)
    archivada: Mapped[bool] = mapped_column(default=False)
    creado_en: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    celula: Mapped["Celula"] = relationship(back_populates="ordenes")
    sku: Mapped["SKU"] = relationship(back_populates="ordenes")
    avances: Mapped[list["AvanceDiario"]] = relationship(back_populates="orden")
    logs: Mapped[list["LogCambio"]] = relationship(back_populates="orden")


class AvanceDiario(Base):
    __tablename__ = "avances"

    id: Mapped[int] = mapped_column(primary_key=True)
    orden_id: Mapped[int] = mapped_column(ForeignKey("ordenes.id"))
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    fecha: Mapped[date] = mapped_column(Date, index=True)
    t1_piezas: Mapped[int] = mapped_column(default=0)
    t2_piezas: Mapped[int] = mapped_column(default=0)
    t3_piezas: Mapped[int] = mapped_column(default=0)
    scrap: Mapped[int] = mapped_column(default=0)
    notas: Mapped[Optional[str]] = mapped_column(Text)
    cargado_en: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    orden: Mapped["Orden"] = relationship(back_populates="avances")
    usuario: Mapped["Usuario"] = relationship(back_populates="avances")


class LogCambio(Base):
    __tablename__ = "log_cambios"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    orden_id: Mapped[Optional[int]] = mapped_column(ForeignKey("ordenes.id"), nullable=True)
    accion: Mapped[str] = mapped_column(String(50))
    detalle: Mapped[Optional[str]] = mapped_column(Text)
    fecha: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)

    usuario: Mapped["Usuario"] = relationship(back_populates="logs")
    orden: Mapped[Optional["Orden"]] = relationship(back_populates="logs")


class Feriado(Base):
    __tablename__ = "feriados"

    id: Mapped[int] = mapped_column(primary_key=True)
    fecha: Mapped[date] = mapped_column(Date, unique=True, index=True)
    nombre: Mapped[str] = mapped_column(String(100))


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
