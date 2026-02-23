# ── gantt.py ────────────────────────────────────────────────────────────────
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import Optional
from datetime import date

from database import get_db, Orden, Feriado, Celula, Usuario, EstadoOrden
from routers.auth import get_current_user
from logic import calcular_fecha_fin, set_feriados

router = APIRouter()

@router.get("")
async def gantt_data(
    celula_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    user: Usuario = Depends(get_current_user)
):
    # Feriados
    r = await db.execute(select(Feriado))
    feriados = {f.fecha for f in r.scalars().all()}
    set_feriados(feriados)

    # Órdenes activas + pendientes + pausadas (no archivadas)
    q = select(Orden).options(
        selectinload(Orden.celula),
        selectinload(Orden.sku),
        selectinload(Orden.avances),
        selectinload(Orden.precede),
    ).where(
        Orden.archivada == False,
        Orden.estado != EstadoOrden.completada,
        Orden.fecha_inicio != None,
    )
    if celula_id:
        q = q.where(Orden.celula_id == celula_id)
    q = q.order_by(Orden.celula_id, Orden.fecha_inicio)

    r = await db.execute(q)
    ordenes = r.scalars().all()

    tareas = []
    for o in ordenes:
        pzas_prod = 0
        acum = 0
        for av in sorted(o.avances, key=lambda a: a.fecha):
            acum += av.total_buenas
        pzas_prod = acum

        pzas_rest = max(0, o.cantidad - pzas_prod)
        t_unit = o.sku.t_unit if o.sku else 0
        hs_rest = round(pzas_rest * t_unit / 60, 2) if t_unit else 0
        hs_dia = o.celula.hs_dia_total if o.celula else 6.8

        fecha_fin = calcular_fecha_fin(o.fecha_inicio, hs_rest, hs_dia, feriados)
        pct = round(pzas_prod / o.cantidad * 100, 1) if o.cantidad else 0

        # Fecha de avance real: última fecha con carga
        ultima_fecha_avance = max((a.fecha for a in o.avances), default=None) if o.avances else None

        tareas.append({
            "id":             o.id,
            "numero":         o.numero,
            "celula_id":      o.celula_id,
            "celula_codigo":  o.celula.codigo if o.celula else "",
            "celula_color":   o.celula.color if o.celula else "#94A3B8",
            "sku_codigo":     o.sku.codigo if o.sku else "",
            "cantidad":       o.cantidad,
            "estado":         o.estado,
            "fecha_inicio":   o.fecha_inicio.isoformat(),
            "fecha_fin":      fecha_fin.isoformat(),
            "pct_avance":     pct,
            "pzas_producidas":pzas_prod,
            "hs_restantes":   hs_rest,
            "ultima_carga":   ultima_fecha_avance.isoformat() if ultima_fecha_avance else None,
            "ot_precede":     o.precede.numero if o.precede else None,
            "notas":          o.notas,
        })

    return {
        "tareas": tareas,
        "feriados": [f.isoformat() for f in feriados],
    }


# ── dashboard.py ────────────────────────────────────────────────────────────
from fastapi import APIRouter as DashRouter
from sqlalchemy import func, and_

dashboard_router_module = DashRouter()

@dashboard_router_module.get("")
async def dashboard_data(db: AsyncSession = Depends(get_db),
                         user: Usuario = Depends(get_current_user)):
    from datetime import date, timedelta

    today = date.today()
    r_cel = await db.execute(select(Celula).where(Celula.activa == True))
    celulas = r_cel.scalars().all()

    r_ord = await db.execute(
        select(Orden).options(
            selectinload(Orden.celula), selectinload(Orden.sku), selectinload(Orden.avances)
        ).where(Orden.archivada == False)
    )
    ordenes = r_ord.scalars().all()

    # Feriados
    r_fer = await db.execute(select(Feriado))
    feriados = {f.fecha for f in r_fer.scalars().all()}
    set_feriados(feriados)

    stats = {
        "total_ordenes":      len(ordenes),
        "activas":            sum(1 for o in ordenes if o.estado == EstadoOrden.activa),
        "pendientes":         sum(1 for o in ordenes if o.estado == EstadoOrden.pendiente),
        "pausadas":           sum(1 for o in ordenes if o.estado == EstadoOrden.pausada),
        "vencen_hoy":         0,
        "vencen_2_dias":      0,
        "sin_carga_hoy":      [],
    }

    por_celula = []
    for cel in celulas:
        ords_cel = [o for o in ordenes if o.celula_id == cel.id and o.estado == EstadoOrden.activa]
        pzas_hoy = 0
        for o in ords_cel:
            pzas_hoy += sum(a.total_buenas for a in o.avances if a.fecha == today)

        # Última carga de esta célula
        ultima = None
        for o in ords_cel:
            for a in o.avances:
                if ultima is None or a.fecha > ultima:
                    ultima = a.fecha

        sin_carga = ultima is None or ultima < today
        if sin_carga and ords_cel:
            stats["sin_carga_hoy"].append(cel.codigo)

        # Órdenes por vencer
        for o in ords_cel:
            if not o.fecha_inicio: continue
            t_unit = o.sku.t_unit if o.sku else 0
            pzas_rest = max(0, o.cantidad - sum(a.total_buenas for a in o.avances))
            hs_rest = round(pzas_rest * t_unit / 60, 2) if t_unit else 0
            hs_dia = cel.hs_dia_total
            fecha_fin = calcular_fecha_fin(o.fecha_inicio, hs_rest, hs_dia, feriados)
            dias_rest = (fecha_fin - today).days
            if dias_rest == 0: stats["vencen_hoy"] += 1
            elif dias_rest <= 2: stats["vencen_2_dias"] += 1

        por_celula.append({
            "celula_id":    cel.id,
            "codigo":       cel.codigo,
            "color":        cel.color,
            "ordenes_activas": len(ords_cel),
            "pzas_hoy":     pzas_hoy,
            "sin_carga":    sin_carga,
            "ultima_carga": ultima.isoformat() if ultima else None,
        })

    return {**stats, "por_celula": por_celula, "fecha": today.isoformat()}
