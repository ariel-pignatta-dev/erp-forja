from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, Float, Date, DateTime, Boolean, ForeignKey, Text, Enum
from datetime import datetime, date
from typing import Optional
import enum
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./erp_forja.db")
# Para PostgreSQL en prod: postgresql+asyncpg://user:pass@host/dbname

engine = create_async_engine(DATABASE_URL, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

# ── Enums ──────────────────────────────────────────────────────────────────
class EstadoOrden(str, enum.Enum):
    pendiente  = "Pendiente"
    activa     = "Activa"
    pausada    = "Pausada"
    completada = "Completada"

class RolUsuario(str, enum.Enum):
    admin    = "admin"
    operario = "operario"

# ── Modelos ────────────────────────────────────────────────────────────────

class Usuario(Base):
    __tablename__ = "usuarios"
    id:         Mapped[int]           = mapped_column(primary_key=True)
    nombre:     Mapped[str]           = mapped_column(String(100))
    email:      Mapped[str]           = mapped_column(String(150), unique=True, index=True)
    password:   Mapped[str]           = mapped_column(String(200))
    rol:        Mapped[RolUsuario]    = mapped_column(default=RolUsuario.operario)
    activo:     Mapped[bool]          = mapped_column(default=True)
    creado_en:  Mapped[datetime]      = mapped_column(default=datetime.utcnow)

    avances:    Mapped[list["AvanceDiario"]] = relationship(back_populates="usuario")
    logs:       Mapped[list["LogCambio"]]    = relationship(back_populates="usuario")


class Celula(Base):
    __tablename__ = "celulas"
    id:           Mapped[int]   = mapped_column(primary_key=True)
    codigo:       Mapped[str]   = mapped_column(String(20), unique=True, index=True)
    nombre:       Mapped[str]   = mapped_column(String(100))
    turnos_lv:    Mapped[int]   = mapped_column(default=1)
    hs_turno_lv:  Mapped[float] = mapped_column(default=8.0)
    turnos_sab:   Mapped[int]   = mapped_column(default=3)
    hs_turno_sab: Mapped[float] = mapped_column(default=4.0)
    efic_lv:      Mapped[float] = mapped_column(default=85.0)
    efic_sab:     Mapped[float] = mapped_column(default=85.0)
    hs_extra_lv:  Mapped[float] = mapped_column(default=0.0)
    hs_extra_sab: Mapped[float] = mapped_column(default=0.0)
    hs_extra_dom: Mapped[float] = mapped_column(default=0.0)
    hs_extra_fer: Mapped[float] = mapped_column(default=0.0)
    color:        Mapped[str]   = mapped_column(String(10), default="#3B82F6")
    activa:       Mapped[bool]  = mapped_column(default=True)

    ordenes: Mapped[list["Orden"]] = relationship(back_populates="celula")

    @property
    def hs_dia_base(self) -> float:
        return self.turnos_lv * self.hs_turno_lv * (self.efic_lv / 100)

    @property
    def hs_dia_total(self) -> float:
        return self.hs_dia_base + self.hs_extra_lv


class SKU(Base):
    __tablename__ = "skus"
    id:          Mapped[int]   = mapped_column(primary_key=True)
    codigo:      Mapped[str]   = mapped_column(String(50), unique=True, index=True)
    descripcion: Mapped[str]   = mapped_column(String(200))
    material:    Mapped[Optional[str]] = mapped_column(String(100))
    proceso:     Mapped[Optional[str]] = mapped_column(String(100))
    t_unit:      Mapped[float] = mapped_column(default=0.0)   # min/pieza
    activo:      Mapped[bool]  = mapped_column(default=True)
    observaciones: Mapped[Optional[str]] = mapped_column(Text)

    ordenes: Mapped[list["Orden"]] = relationship(back_populates="sku")


class Orden(Base):
    __tablename__ = "ordenes"
    id:           Mapped[int]            = mapped_column(primary_key=True)
    numero:       Mapped[str]            = mapped_column(String(30), unique=True, index=True)
    celula_id:    Mapped[int]            = mapped_column(ForeignKey("celulas.id"))
    sku_id:       Mapped[int]            = mapped_column(ForeignKey("skus.id"))
    cantidad:     Mapped[int]            = mapped_column(default=0)
    estado:       Mapped[EstadoOrden]    = mapped_column(default=EstadoOrden.pendiente)
    fecha_inicio: Mapped[Optional[date]] = mapped_column(Date)
    ot_precede_id: Mapped[Optional[int]] = mapped_column(ForeignKey("ordenes.id"), nullable=True)
    notas:        Mapped[Optional[str]]  = mapped_column(Text)
    archivada:    Mapped[bool]           = mapped_column(default=False)
    creado_en:    Mapped[datetime]       = mapped_column(default=datetime.utcnow)
    archivado_en: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    celula:    Mapped["Celula"]           = relationship(back_populates="ordenes")
    sku:       Mapped["SKU"]              = relationship(back_populates="ordenes")
    precede:   Mapped[Optional["Orden"]]  = relationship("Orden", remote_side="Orden.id", foreign_keys=[ot_precede_id])
    avances:   Mapped[list["AvanceDiario"]] = relationship(back_populates="orden", cascade="all, delete-orphan")
    logs:      Mapped[list["LogCambio"]]    = relationship(back_populates="orden")

    @property
    def piezas_producidas(self) -> int:
        return max((a.total_buenas for a in self.avances), default=0) if self.avances else 0

    @property
    def piezas_restantes(self) -> int:
        return max(0, self.cantidad - self.piezas_producidas)

    @property
    def hs_estimadas(self) -> float:
        if not self.sku or self.sku.t_unit == 0:
            return 0.0
        return round(self.cantidad * self.sku.t_unit / 60, 2)

    @property
    def hs_restantes(self) -> float:
        if not self.sku or self.sku.t_unit == 0:
            return self.hs_estimadas
        return round(self.piezas_restantes * self.sku.t_unit / 60, 2)


class AvanceDiario(Base):
    __tablename__ = "avances"
    id:           Mapped[int]      = mapped_column(primary_key=True)
    orden_id:     Mapped[int]      = mapped_column(ForeignKey("ordenes.id"))
    usuario_id:   Mapped[int]      = mapped_column(ForeignKey("usuarios.id"))
    fecha:        Mapped[date]     = mapped_column(Date, index=True)
    t1_piezas:    Mapped[int]      = mapped_column(default=0)
    t2_piezas:    Mapped[int]      = mapped_column(default=0)
    t3_piezas:    Mapped[int]      = mapped_column(default=0)
    scrap:        Mapped[int]      = mapped_column(default=0)
    notas:        Mapped[Optional[str]] = mapped_column(Text)
    cargado_en:   Mapped[datetime] = mapped_column(default=datetime.utcnow)

    orden:   Mapped["Orden"]   = relationship(back_populates="avances")
    usuario: Mapped["Usuario"] = relationship(back_populates="avances")

    @property
    def total_buenas(self) -> int:
        return self.t1_piezas + self.t2_piezas + self.t3_piezas - self.scrap


class LogCambio(Base):
    __tablename__ = "log_cambios"
    id:         Mapped[int]      = mapped_column(primary_key=True)
    usuario_id: Mapped[int]      = mapped_column(ForeignKey("usuarios.id"))
    orden_id:   Mapped[Optional[int]] = mapped_column(ForeignKey("ordenes.id"), nullable=True)
    accion:     Mapped[str]      = mapped_column(String(50))   # crear_orden, editar_orden, cargar_avance, etc.
    detalle:    Mapped[Optional[str]] = mapped_column(Text)    # JSON con campos cambiados
    fecha:      Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)

    usuario: Mapped["Usuario"]       = relationship(back_populates="logs")
    orden:   Mapped[Optional["Orden"]] = relationship(back_populates="logs")


class Feriado(Base):
    __tablename__ = "feriados"
    id:     Mapped[int]  = mapped_column(primary_key=True)
    fecha:  Mapped[date] = mapped_column(Date, unique=True, index=True)
    nombre: Mapped[str]  = mapped_column(String(100))


# ── Helpers ────────────────────────────────────────────────────────────────

async def get_db():
    async with SessionLocal() as session:
        yield session

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await seed_initial_data()

async def seed_initial_data():
    """Carga datos iniciales si la DB está vacía."""
    from passlib.context import CryptContext
    from datetime import date as d
    pwd = CryptContext(schemes=["bcrypt"])

    async with SessionLocal() as session:
        from sqlalchemy import select, func

        # Usuario admin
        r = await session.execute(select(func.count()).select_from(Usuario))
        if r.scalar() == 0:
            admin = Usuario(
                nombre="Administrador",
                email="admin@forja.com",
                password=pwd.hash("admin123"),
                rol=RolUsuario.admin,
            )
            session.add(admin)

        # Células
        r = await session.execute(select(func.count()).select_from(Celula))
        if r.scalar() == 0:
            celulas = [
                Celula(codigo="C69",  nombre="Célula Nº69",  color="#3B82F6", turnos_lv=1, hs_turno_lv=8, turnos_sab=3, hs_turno_sab=4, efic_lv=85, efic_sab=85),
                Celula(codigo="C101", nombre="Célula Nº101", color="#10B981", turnos_lv=1, hs_turno_lv=8, turnos_sab=3, hs_turno_sab=4, efic_lv=85, efic_sab=85),
                Celula(codigo="C158", nombre="Célula Nº158", color="#F59E0B", turnos_lv=2, hs_turno_lv=8, turnos_sab=3, hs_turno_sab=4, efic_lv=85, efic_sab=85),
                Celula(codigo="C161", nombre="Célula Nº161", color="#8B5CF6", turnos_lv=1, hs_turno_lv=8, turnos_sab=3, hs_turno_sab=4, efic_lv=85, efic_sab=85),
                Celula(codigo="C165", nombre="Célula Nº165", color="#EF4444", turnos_lv=3, hs_turno_lv=8, turnos_sab=3, hs_turno_sab=4, efic_lv=85, efic_sab=85),
            ]
            session.add_all(celulas)

        # SKUs
        r = await session.execute(select(func.count()).select_from(SKU))
        if r.scalar() == 0:
            skus = [
                SKU(codigo="1001XL", descripcion="Pieza estructural XL",   material="Acero 1045", proceso="Forja+CNC", t_unit=1.710),
                SKU(codigo="1049",   descripcion="Componente hidráulico",   material="Acero 4140", proceso="Forja",     t_unit=1.760),
                SKU(codigo="1002",   descripcion="Pieza base serie 1002",   material="Acero 1020", proceso="Forja",     t_unit=1.330),
                SKU(codigo="MOD-44", descripcion="Módulo ensamble 44",      material="Acero 4340", proceso="Forja+TT",  t_unit=1.750),
                SKU(codigo="2002",   descripcion="Pieza dinámica 2002",     material="Acero 1045", proceso="Forja+CNC", t_unit=1.950),
            ]
            session.add_all(skus)

        # Feriados 2026
        r = await session.execute(select(func.count()).select_from(Feriado))
        if r.scalar() == 0:
            feriados = [
                Feriado(fecha=d(2026,1,1),  nombre="Año Nuevo"),
                Feriado(fecha=d(2026,2,16), nombre="Carnaval"),
                Feriado(fecha=d(2026,2,17), nombre="Carnaval"),
                Feriado(fecha=d(2026,3,24), nombre="Día de la Memoria"),
                Feriado(fecha=d(2026,4,2),  nombre="Veteranos de Malvinas"),
                Feriado(fecha=d(2026,4,3),  nombre="Viernes Santo"),
                Feriado(fecha=d(2026,5,1),  nombre="Día del Trabajador"),
                Feriado(fecha=d(2026,5,25), nombre="Revolución de Mayo"),
                Feriado(fecha=d(2026,6,20), nombre="Paso a la Inmortalidad de Belgrano"),
                Feriado(fecha=d(2026,7,9),  nombre="Día de la Independencia"),
                Feriado(fecha=d(2026,8,17), nombre="Paso a la Inmortalidad de San Martín"),
                Feriado(fecha=d(2026,10,12),nombre="Día del Respeto a la Diversidad Cultural"),
                Feriado(fecha=d(2026,11,20),nombre="Día de la Soberanía Nacional"),
                Feriado(fecha=d(2026,12,8), nombre="Inmaculada Concepción de María"),
                Feriado(fecha=d(2026,12,25),nombre="Navidad"),
            ]
            session.add_all(feriados)

        await session.commit()
