from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime
import json

from database import get_db, Orden, Celula, SKU, Feriado, LogCambio, EstadoOrden, Usuario
from routers.auth import get_current_user, require_admin
from logic import calcular_fecha_fin, detectar_solape, set_feriados

router = APIRouter()

# ── Schemas ────────────────────────────────────────────────────────────────
class OrdenCreate(BaseModel):
    numero: str
    celula_id: int
    sku_id: int
    cantidad: int
    estado: EstadoOrden = EstadoOrden.pendiente
    fecha_inicio: Optional[date] = None
    ot_precede_id: Optional[int] = None
    notas: Optional[str] = None

class OrdenUpdate(BaseModel):
    celula_id: Optional[int] = None
    sku_id: Optional[int] = None
    cantidad: Optional[int] = None
    estado: Optional[EstadoOrden] = None
    fecha_inicio: Optional[date] = None
    ot_precede_id: Optional[int] = None
    notas: Optional[str] = None

# ── Helpers ────────────────────────────────────────────────────────────────
async def load_feriados(db: AsyncSession) -> set:
    r = await db.execute(select(Feriado))
    feriados = {f.fecha for f in r.scalars().all()}
    set_feriados(feriados)
    return feriados

def orden_to_dict(o: Orden, feriados: set = None) -> dict:
    from logic import calcular_fecha_fin, networkdays
    from datetime import date

    pzas_prod = sum(
        (a.t1_piezas + a.t2_piezas + a.t3_piezas - a.scrap)
        for a in o.avances
    ) if o.avances else 0
    # Acumulado real = max acumulado de los avances (SUMIFS equivalente)
    acum_max = 0
    acum = 0
    avances_sorted = sorted(o.avances, key=lambda a: a.fecha) if o.avances else []
    for av in avances_sorted:
        acum += av.total_buenas
        acum_max = max(acum_max, acum)
    pzas_prod = acum_max

    pzas_rest  = max(0, o.cantidad - pzas_prod)
    t_unit     = o.sku.t_unit if o.sku else 0
    hs_estim   = round(o.cantidad * t_unit / 60, 2) if t_unit else 0
    hs_rest    = round(pzas_rest * t_unit / 60, 2) if t_unit else hs_estim

    # Fecha fin calculada
    fecha_fin = None
    if o.fecha_inicio and o.celula:
        if o.estado == EstadoOrden.completada:
            fecha_fin = o.fecha_inicio
        else:
            hs_dia = o.celula.hs_dia_total
            fecha_fin = calcular_fecha_fin(o.fecha_inicio, hs_rest, hs_dia, feriados)

    # Días residuales
    dias_resid = 0
    if fecha_fin and o.estado != EstadoOrden.completada:
        today = date.today()
        if fecha_fin >= today:
            dias_resid = networkdays(today, fecha_fin, feriados) - 1

    return {
        "id":           o.id,
        "numero":       o.numero,
        "celula_id":    o.celula_id,
        "celula_codigo":o.celula.codigo if o.celula else None,
        "celula_color": o.celula.color if o.celula else "#94A3B8",
        "sku_id":       o.sku_id,
        "sku_codigo":   o.sku.codigo if o.sku else None,
        "cantidad":     o.cantidad,
        "estado":       o.estado,
        "fecha_inicio": o.fecha_inicio.isoformat() if o.fecha_inicio else None,
        "fecha_fin":    fecha_fin.isoformat() if fecha_fin else None,
        "ot_precede_id":o.ot_precede_id,
        "ot_precede_numero": o.precede.numero if o.precede else None,
        "notas":        o.notas,
        "pzas_producidas": pzas_prod,
        "pzas_restantes":  pzas_rest,
        "hs_estimadas":    hs_estim,
        "hs_restantes":    hs_rest,
        "dias_residuales": dias_resid,
        "pct_avance":      round(pzas_prod / o.cantidad * 100, 1) if o.cantidad else 0,
        "archivada":    o.archivada,
        "creado_en":    o.creado_en.isoformat(),
    }

# ── Endpoints ──────────────────────────────────────────────────────────────
@router.get("")
async def listar_ordenes(
    celula_id: Optional[int] = None,
    estado: Optional[EstadoOrden] = None,
    archivadas: bool = False,
    db: AsyncSession = Depends(get_db),
    user: Usuario = Depends(get_current_user)
):
    q = select(Orden).options(
        selectinload(Orden.celula),
        selectinload(Orden.sku),
        selectinload(Orden.avances),
        selectinload(Orden.precede),
    ).where(Orden.archivada == archivadas)

    if celula_id:
        q = q.where(Orden.celula_id == celula_id)
    if estado:
        q = q.where(Orden.estado == estado)

    q = q.order_by(Orden.celula_id, Orden.fecha_inicio)
    r = await db.execute(q)
    ordenes = r.scalars().all()
    feriados = await load_feriados(db)
    return [orden_to_dict(o, feriados) for o in ordenes]


@router.get("/{orden_id}")
async def get_orden(orden_id: int, db: AsyncSession = Depends(get_db),
                    user: Usuario = Depends(get_current_user)):
    r = await db.execute(
        select(Orden).options(
            selectinload(Orden.celula), selectinload(Orden.sku),
            selectinload(Orden.avances), selectinload(Orden.precede),
        ).where(Orden.id == orden_id)
    )
    o = r.scalar_one_or_none()
    if not o:
        raise HTTPException(404, "Orden no encontrada")
    feriados = await load_feriados(db)
    return orden_to_dict(o, feriados)


@router.post("", response_model=dict)
async def crear_orden(data: OrdenCreate, db: AsyncSession = Depends(get_db),
                      user: Usuario = Depends(require_admin)):
    # Verificar número único
    r = await db.execute(select(Orden).where(Orden.numero == data.numero))
    if r.scalar_one_or_none():
        raise HTTPException(400, f"Ya existe la orden {data.numero}")

    # Si tiene OT precede, calcular fecha inicio
    fecha_ini = data.fecha_inicio
    if data.ot_precede_id and not fecha_ini:
        feriados = await load_feriados(db)
        r_prec = await db.execute(
            select(Orden).options(selectinload(Orden.celula), selectinload(Orden.sku), selectinload(Orden.avances))
            .where(Orden.id == data.ot_precede_id)
        )
        prec = r_prec.scalar_one_or_none()
        if prec and prec.fecha_inicio:
            hs_dia = prec.celula.hs_dia_total if prec.celula else 6.8
            t_unit = prec.sku.t_unit if prec.sku else 0
            pzas_rest = max(0, prec.cantidad - sum(a.total_buenas for a in prec.avances))
            hs_rest = round(pzas_rest * t_unit / 60, 2) if t_unit else 0
            fecha_fin_prec = calcular_fecha_fin(prec.fecha_inicio, hs_rest, hs_dia, feriados)
            from logic import workday
            fecha_ini = workday(fecha_fin_prec, 1, feriados)

    orden = Orden(**data.model_dump(exclude={"fecha_inicio"}), fecha_inicio=fecha_ini)
    db.add(orden)

    # Log
    log = LogCambio(usuario_id=user.id, accion="crear_orden",
                    detalle=json.dumps({"numero": data.numero, "celula_id": data.celula_id}))
    db.add(log)
    await db.commit()
    await db.refresh(orden)

    r2 = await db.execute(
        select(Orden).options(selectinload(Orden.celula), selectinload(Orden.sku),
                              selectinload(Orden.avances), selectinload(Orden.precede))
        .where(Orden.id == orden.id)
    )
    o = r2.scalar_one()
    feriados = await load_feriados(db)
    return orden_to_dict(o, feriados)


@router.patch("/{orden_id}", response_model=dict)
async def editar_orden(orden_id: int, data: OrdenUpdate,
                       db: AsyncSession = Depends(get_db),
                       user: Usuario = Depends(require_admin)):
    r = await db.execute(
        select(Orden).options(selectinload(Orden.celula), selectinload(Orden.sku),
                              selectinload(Orden.avances), selectinload(Orden.precede))
        .where(Orden.id == orden_id)
    )
    o = r.scalar_one_or_none()
    if not o:
        raise HTTPException(404, "Orden no encontrada")

    cambios = {}
    for field, val in data.model_dump(exclude_none=True).items():
        old = getattr(o, field)
        if old != val:
            cambios[field] = {"de": str(old), "a": str(val)}
            setattr(o, field, val)

    # Si cambia a Completada, archivar automáticamente
    if data.estado == EstadoOrden.completada:
        o.archivada = True
        o.archivado_en = datetime.utcnow()

    if cambios:
        log = LogCambio(usuario_id=user.id, orden_id=orden_id, accion="editar_orden",
                        detalle=json.dumps(cambios, ensure_ascii=False))
        db.add(log)

    await db.commit()
    feriados = await load_feriados(db)
    return orden_to_dict(o, feriados)


@router.delete("/{orden_id}")
async def eliminar_orden(orden_id: int, db: AsyncSession = Depends(get_db),
                         user: Usuario = Depends(require_admin)):
    r = await db.execute(select(Orden).where(Orden.id == orden_id))
    o = r.scalar_one_or_none()
    if not o:
        raise HTTPException(404, "Orden no encontrada")
    log = LogCambio(usuario_id=user.id, orden_id=orden_id, accion="eliminar_orden",
                    detalle=json.dumps({"numero": o.numero}))
    db.add(log)
    await db.delete(o)
    await db.commit()
    return {"ok": True}
